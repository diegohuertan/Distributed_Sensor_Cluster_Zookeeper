import logging
import requests
import time
from requests.exceptions import RequestException

from ..domain.ports import IHttpApiAdapter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HttpApiAdapter(IHttpApiAdapter):
    """
    Implementación del adaptador HTTP para comunicarse con la API externa (Legacy).
    Utiliza la librería `requests` para realizar llamadas POST.
    """

    def __init__(self, api_url: str):
        if not api_url or not api_url.startswith("http"):
            raise ValueError("La URL de la API es inválida.")
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "SensorNodeClient/1.0"
        })

    def send_average(self, average: float) -> bool:
        """
        Envía el valor promedio de las mediciones a la API configurada.
        """
        # --- CORRECCIÓN AQUÍ ---
        # El payload DEBE coincidir con el modelo Pydantic de tu API:
        # sensor_id (str), valor (float), timestamp (opcional)
        payload = {
            "sensor_id": "CLUSTER_AGGREGATE", # Identificador para diferenciar que es una media del clúster
            "valor": average,                 # La clave exacta que pide tu Pydantic
            "timestamp": time.time()          # Opcional, pero recomendado
        }
        
        logging.info(f"Enviando media {average:.2f} a la API en {self.api_url}")

        try:
            # Timeout crítico de 5s
            response = self.session.post(self.api_url, json=payload, timeout=5.0)
            
            # Si la API devuelve 422 (Validation Error), esto nos lo dirá en el log
            if response.status_code == 422:
                logging.error(f"❌ Error de Validación de Datos (422): {response.text}")
                return False

            response.raise_for_status()
            
            logging.info(f"Media enviada correctamente. Respuesta de la API: {response.status_code}")
            return True
            
        except RequestException as e:
            logging.error(f"Error de red al contactar la API: {e}")
            return False
        except Exception as e:
            logging.error(f"Error inesperado al enviar datos a la API: {e}")
            return False