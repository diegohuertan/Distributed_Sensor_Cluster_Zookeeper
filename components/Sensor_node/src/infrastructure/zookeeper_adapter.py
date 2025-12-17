import logging
import threading
import time
from datetime import datetime
from typing import List, Callable, Optional

# Importamos las excepciones y estados necesarios de Kazoo
from kazoo.client import KazooClient, KazooState
from kazoo.exceptions import NodeExistsError 
from kazoo.recipe.election import Election
from kazoo.recipe.watchers import DataWatch, ChildrenWatch

# Importamos las interfaces del dominio
from src.domain.ports import IZooKeeperAdapter
from src.domain.models import Medicion

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')

class ZooKeeperAdapter(IZooKeeperAdapter):
    """
    Implementación concreta para Software Crítico (UMA).
    Maneja elección de líder, configuración distribuida y monitoreo de nodos.
    """
    _ELECTION_PATH = "/election"
    _TRIGGER_PATH = "/config/ronda_trigger"
    _MEASUREMENTS_PATH = "/mediciones"
    
    # Rutas para configuración distribuida [cite: 60]
    _CONFIG_URL_PATH = "/config/api_url"
    _CONFIG_PERIOD_PATH = "/config/sampling_period"

    def __init__(self, hosts: str, sensor_id: str):
        self.sensor_id = sensor_id
        self.zk_client = KazooClient(hosts=hosts)
        self.election: Optional[Election] = None
        self._is_leader = False
        self._leader_election_thread: Optional[threading.Thread] = None

        self.zk_client.add_listener(self._state_listener)
        self.zk_client.start()

        # Aseguramos rutas base persistentes [cite: 12]
        self.zk_client.ensure_path(self._ELECTION_PATH)
        self.zk_client.ensure_path(self._TRIGGER_PATH)
        self.zk_client.ensure_path(self._MEASUREMENTS_PATH)
        self.zk_client.ensure_path(self._CONFIG_URL_PATH)
        self.zk_client.ensure_path(self._CONFIG_PERIOD_PATH)

        # Inicializamos los Watchers obligatorios [cite: 58]
        self._setup_watchers()

    def _setup_watchers(self):
        """Configuración de DataWatch y ChildrenWatch [cite: 59, 61]"""
        
        # 1. DataWatch para URL de la API 
        @self.zk_client.DataWatch(self._CONFIG_URL_PATH)
        def watch_api_url(data, stat, event=None):
            if data:
                logging.info(f"[WATCHER] Configuración Distribuida - Nueva URL: {data.decode('utf-8')}")

        # 2. DataWatch para Periodo de Muestreo 
        @self.zk_client.DataWatch(self._CONFIG_PERIOD_PATH)
        def watch_sampling_period(data, stat, event=None):
            if data:
                logging.info(f"[WATCHER] Configuración Distribuida - Nuevo Periodo: {data.decode('utf-8')}s")

        # 3. ChildrenWatch para presencia de dispositivos 
        @self.zk_client.ChildrenWatch(self._MEASUREMENTS_PATH)
        def watch_sensors(children):
            # El líder debe mostrar mensajes cuando se conecten/desconecten dispositivos 
            if self.am_i_leader():
                logging.info(f"[LÍDER] Watcher detectó cambio en sensores. Conectados: {children}")

    def _state_listener(self, state):
        if state == KazooState.LOST:
            logging.warning("Conexión con ZooKeeper perdida.")
        elif state == KazooState.SUSPENDED:
            logging.warning("Conexión con ZooKeeper suspendida.")
        elif state == KazooState.CONNECTED:
            logging.info(f"Estado de la conexión con ZooKeeper: {state}")

    def run_for_leader(self, on_become_leader_callback: Callable[[], None]):
        """Elección de líder usando la receta Election de Kazoo [cite: 30]"""
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
            
            self.election.run(leader_logic_wrapper)

        self._leader_election_thread = threading.Thread(target=election_task, daemon=True, name="LeaderElectionThread")
        self._leader_election_thread.start()
        logging.info(f"Sensor {self.sensor_id} unido a la elección.")

    def am_i_leader(self) -> bool:
        return self._is_leader

    def trigger_measurement_round(self) -> None:
        """Inicia ronda notificando a seguidores vía DataWatch [cite: 84, 100]"""
        logging.info("Líder iniciando nueva ronda de medición.")
        try:
            self.zk_client.set(self._TRIGGER_PATH, str(time.time()).encode('utf-8'))
        except Exception as e:
            logging.error(f"Error al iniciar ronda: {e}")

    def watch_measurement_round(self, on_trigger_callback: Callable[[], None]) -> None:
        """Seguidores escuchan el trigger para medir [cite: 100, 101]"""
        @self.zk_client.DataWatch(self._TRIGGER_PATH)
        def on_round_triggered(data, stat, event=None):
            if data is not None and not self.am_i_leader():
                logging.info(f"Seguidor {self.sensor_id} recibió trigger.")
                on_trigger_callback()

    def publish_measurement(self, valor: float) -> None:
        """Publica en znodo efímero /mediciones/{id} [cite: 12, 43]"""
        path = f"{self._MEASUREMENTS_PATH}/{self.sensor_id}"
        data = str(valor).encode('utf-8')
        try:
            # Crear nodo efímero (se borra si el sensor cae) 
            self.zk_client.create(path, data, ephemeral=True)
            logging.info(f"Sensor {self.sensor_id} publicó medición: {valor}")
        except NodeExistsError:
            try:
                self.zk_client.set(path, data)
                logging.info(f"Sensor {self.sensor_id} actualizó medición: {valor}")
            except Exception as e:
                logging.error(f"Error al actualizar {self.sensor_id}: {e}")

    def get_all_measurements(self) -> List[Medicion]:
        """El líder recupera valores de todos los nodos activos [cite: 44, 59]"""
        measurements = []
        try:
            children = self.zk_client.get_children(self._MEASUREMENTS_PATH)
            for sensor_id in children:
                try:
                    data, stat = self.zk_client.get(f"{self._MEASUREMENTS_PATH}/{sensor_id}")
                    valor = float(data.decode('utf-8'))
                    measurements.append(Medicion(sensor_id=sensor_id, valor=valor, timestamp=datetime.now()))
                except Exception: continue
        except Exception as e:
            logging.error(f"Error al obtener mediciones: {e}")
        return measurements

    def clear_measurements(self) -> None:
        """Limpia los znodos antes de una nueva ronda [cite: 44]"""
        try:
            children = self.zk_client.get_children(self._MEASUREMENTS_PATH)
            for child in children:
                try: self.zk_client.delete(f"{self._MEASUREMENTS_PATH}/{child}")
                except Exception: pass
        except Exception: pass

    def stop(self) -> None:
        if self.election:
            try: self.election.cancel()
            except Exception: pass
        if self.zk_client.state != 'CLOSED':
            self.zk_client.stop()
            self.zk_client.close()