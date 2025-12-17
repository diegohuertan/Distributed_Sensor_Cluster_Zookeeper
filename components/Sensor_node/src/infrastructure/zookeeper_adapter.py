import logging
import threading
import time
from datetime import datetime
from typing import List, Callable, Optional

# --- CORRECCIÓN 1: Importamos las excepciones y estados necesarios de Kazoo ---
from kazoo.client import KazooClient, KazooState
from kazoo.exceptions import NodeExistsError 
from kazoo.recipe.election import Election
from kazoo.recipe.watchers import DataWatch

# --- Importamos las interfaces del dominio ---
from src.domain.ports import IZooKeeperAdapter
from src.domain.models import Medicion

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')

class ZooKeeperAdapter(IZooKeeperAdapter):
    """
    Implementación concreta de la interfaz de ZooKeeper usando la librería Kazoo.
    Maneja la lógica de elección de líder, publicación y lectura de mediciones.
    """
    _ELECTION_PATH = "/election"
    _TRIGGER_PATH = "/config/ronda_trigger"
    _MEASUREMENTS_PATH = "/mediciones"

    def __init__(self, hosts: str, sensor_id: str):
        self.sensor_id = sensor_id
        self.zk_client = KazooClient(hosts=hosts)
        self.election: Optional[Election] = None
        self._is_leader = False
        self._leader_election_thread: Optional[threading.Thread] = None

        self.zk_client.add_listener(self._state_listener)
        self.zk_client.start()

        # Aseguramos que las rutas base persistentes existan
        self.zk_client.ensure_path(self._ELECTION_PATH)
        self.zk_client.ensure_path(self._TRIGGER_PATH)
        self.zk_client.ensure_path(self._MEASUREMENTS_PATH)

    def _state_listener(self, state):
        if state == KazooState.LOST:
            logging.warning("Conexión con ZooKeeper perdida. Kazoo intentará reconectar.")
        elif state == KazooState.SUSPENDED:
            logging.warning("Conexión con ZooKeeper suspendida. No se pueden realizar operaciones.")
        elif state == KazooState.CONNECTED:
            logging.info(f"Estado de la conexión con ZooKeeper: {state}")

    def run_for_leader(self, on_become_leader_callback: Callable[[], None]):
        self.election = Election(self.zk_client, self._ELECTION_PATH, identifier=self.sensor_id)

        def election_task():
            def leader_logic_wrapper():
                self._is_leader = True
                logging.info(f"¡¡¡Sensor {self.sensor_id} es ahora LÍDER!!!")
                try:
                    on_become_leader_callback()
                finally:
                    self._is_leader = False
                    logging.info(f"Sensor {self.sensor_id} ha cedido el liderazgo.")
            
            # El método run() es bloqueante.
            self.election.run(leader_logic_wrapper)

        self._leader_election_thread = threading.Thread(target=election_task, daemon=True, name="LeaderElectionThread")
        self._leader_election_thread.start()
        logging.info(f"Sensor {self.sensor_id} se ha unido a la elección.")

    def am_i_leader(self) -> bool:
        return self._is_leader

    def trigger_measurement_round(self) -> None:
        logging.info("Líder iniciando nueva ronda de medición.")
        try:
            self.zk_client.set(self._TRIGGER_PATH, str(time.time()).encode('utf-8'))
        except Exception as e:
            logging.error(f"Líder falló al iniciar la ronda: {e}")

    def watch_measurement_round(self, on_trigger_callback: Callable[[], None]) -> None:
        # --- CORRECCIÓN 2: DataWatch espera recibir (data, stat, event) ---
        @self.zk_client.DataWatch(self._TRIGGER_PATH)
        def on_round_triggered(data, stat, event=None):
            # Solo reaccionar si hay datos y no somos el líder
            if data is not None and not self.am_i_leader():
                logging.info(f"Seguidor {self.sensor_id} detectó trigger para nueva ronda.")
                on_trigger_callback()

    def publish_measurement(self, valor: float) -> None:
        path = f"{self._MEASUREMENTS_PATH}/{self.sensor_id}"
        data = str(valor).encode('utf-8')
        try:
            # Creamos un nodo efímero.
            self.zk_client.create(path, data, ephemeral=True)
            logging.info(f"Sensor {self.sensor_id} publicó medición: {valor}")
        except NodeExistsError:
            # --- CORRECCIÓN 3: Manejo de NodeExistsError (ahora importado arriba) ---
            try:
                self.zk_client.set(path, data)
                logging.info(f"Sensor {self.sensor_id} actualizó medición: {valor}")
            except Exception as e:
                logging.error(f"No se pudo actualizar la medición para {self.sensor_id}: {e}")
        except Exception as e:
            logging.error(f"No se pudo crear la medición para {self.sensor_id}: {e}")

    def get_all_measurements(self) -> List[Medicion]:
        measurements = []
        try:
            children = self.zk_client.get_children(self._MEASUREMENTS_PATH)
            logging.info(f"Líder recuperando mediciones de {len(children)} nodos.")
            for sensor_id in children:
                try:
                    data, stat = self.zk_client.get(f"{self._MEASUREMENTS_PATH}/{sensor_id}")
                    valor = float(data.decode('utf-8'))
                    measurements.append(Medicion(sensor_id=sensor_id, valor=valor, timestamp=datetime.now()))
                except Exception as e:
                    logging.error(f"No se pudo leer la medición de {sensor_id}: {e}")
        except Exception as e:
            logging.error(f"Error al obtener la lista de mediciones: {e}")
        return measurements

    def clear_measurements(self) -> None:
        logging.info("Líder limpiando mediciones de la ronda anterior.")
        try:
            children = self.zk_client.get_children(self._MEASUREMENTS_PATH)
            for child in children:
                try:
                    self.zk_client.delete(f"{self._MEASUREMENTS_PATH}/{child}")
                except Exception as e:
                    logging.warning(f"No se pudo limpiar la medición {child}: {e}")
        except Exception as e:
            logging.error(f"Error al obtener la lista de mediciones para limpiar: {e}")

    def stop(self) -> None:
        logging.info(f"Deteniendo adaptador de ZooKeeper para {self.sensor_id}.")
        if self.election:
            try:
                self.election.cancel()
            except Exception as e:
                logging.warning(f"Error al cancelar la elección: {e}")
        
        if self.zk_client.state != 'CLOSED':
            self.zk_client.stop()
            self.zk_client.close()
        logging.info("Adaptador de ZooKeeper detenido.")