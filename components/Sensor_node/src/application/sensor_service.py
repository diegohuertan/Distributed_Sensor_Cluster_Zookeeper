import logging
import random
import time
import threading

from src.domain.ports import IZooKeeperAdapter, IHttpApiAdapter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')

class SensorService:
    """
    Capa de aplicación: orquesta la lógica del nodo sensor.
    No contiene lógica de bajo nivel (sockets, http), solo coordina los adaptadores.
    """
    _LEADER_ROUND_INTERVAL_SECONDS = 15
    _LEADER_TIMEBOX_SECONDS = 5

    def __init__(
        self, 
        sensor_id: str, 
        zk_adapter: IZooKeeperAdapter, 
        http_adapter: IHttpApiAdapter
    ):
        self.sensor_id = sensor_id
        self.zk_adapter = zk_adapter
        self.http_adapter = http_adapter
        self._stop_event = threading.Event()

    def run(self):
        logging.info(f"Iniciando servicio para sensor '{self.sensor_id}'.")
        self.zk_adapter.run_for_leader(self._leader_main_loop)
        self.zk_adapter.watch_measurement_round(self._follower_measure_and_publish)
        logging.info(f"Sensor '{self.sensor_id}' funcionando en modo seguidor. Esperando para ser líder o recibir triggers.")
        
        try:
            self._stop_event.wait()
        except KeyboardInterrupt:
            logging.info("Señal de interrupción recibida.")
        finally:
            self.stop()

    def _leader_main_loop(self):
        while not self._stop_event.is_set():
            try:
                logging.info("--- [LÍDER] Iniciando nueva ronda de monitorización ---")
                self.zk_adapter.clear_measurements()
                own_measurement = self._take_measurement()
                self.zk_adapter.publish_measurement(own_measurement)
                logging.info(f"[LÍDER] Medición propia publicada: {own_measurement:.2f}")

                self.zk_adapter.trigger_measurement_round()
                logging.info(f"[LÍDER] Esperando {self._LEADER_TIMEBOX_SECONDS}s a que los seguidores midan...")
                time.sleep(self._LEADER_TIMEBOX_SECONDS)

                all_measurements = self.zk_adapter.get_all_measurements()
                if not all_measurements:
                    logging.warning("[LÍDER] No se recibieron mediciones en esta ronda.")
                    time.sleep(self._LEADER_ROUND_INTERVAL_SECONDS)
                    continue

                average = sum(m.valor for m in all_measurements) / len(all_measurements)
                logging.info(f"[LÍDER] Media calculada: {average:.2f} (de {len(all_measurements)} mediciones).")

                self.http_adapter.send_average(average)
                logging.info(f"--- [LÍDER] Ronda finalizada. Próxima ronda en {self._LEADER_ROUND_INTERVAL_SECONDS}s. ---")
                time.sleep(self._LEADER_ROUND_INTERVAL_SECONDS)

            except Exception as e:
                logging.error(f"[LÍDER] Error inesperado en el bucle principal: {e}", exc_info=True)
                time.sleep(5)
        
        logging.info(f"[LÍDER] Bucle principal detenido para el sensor {self.sensor_id}.")

    def _follower_measure_and_publish(self):
        if not self.zk_adapter.am_i_leader():
            logging.info(f"[SEGUIDOR] {self.sensor_id} recibió trigger. Tomando medición.")
            measurement = self._take_measurement()
            self.zk_adapter.publish_measurement(measurement)

    def _take_measurement(self) -> float:
        return random.uniform(80.0, 120.0)

    def stop(self):
        if not self._stop_event.is_set():
            logging.info(f"Deteniendo servicio del sensor {self.sensor_id}...")
            self._stop_event.set()
            if self.zk_adapter:
                self.zk_adapter.stop()
            logging.info("Servicio detenido.")