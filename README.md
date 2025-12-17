# 🛡️ AeroGuard: Full-Stack Critical Monitoring & Anomaly Detection System

> **Ecosistema distribuido de extremo a extremo para la monitorización industrial, coordinación de sensores por consenso y detección de anomalías mediante IA robusta.**

![Architecture Diagram](Descripcion_Arquitectura.png)

## 📋 Resumen del Proyecto

AeroGuard es una plataforma integral de **Software Crítico** que fusiona la coordinación distribuida de bajo nivel con el análisis avanzado de datos. El sistema está diseñado para operar en entornos SCADA/IoT donde la pérdida de un solo mensaje o una falsa alarma pueden tener consecuencias operativas graves.

La arquitectura se divide en dos grandes capas funcionales:

1. **Distributed Edge Cluster (ZooKeeper Control Plane):** Una red de sensores inteligentes coordinados por un ensamble de ZooKeeper para garantizar alta disponibilidad, sincronización y resiliencia ante fallos de nodos.
2. **Analysis Sentinel (AI & Persistence Layer):** Una infraestructura híbrida (Sentinel/Cluster) que ingesta los datos agregados y utiliza un motor de inteligencia artificial basado en la diversidad de diseño para la detección de anomalías.

---

## 🏗️ Arquitectura del Sistema

### 📡 1. Capa de Sensores Distribuidos (Edge Computing)

Utiliza **Apache ZooKeeper** como orquestador para eliminar cualquier punto único de fallo (SPOF) y gestionar el estado del clúster.

* **Elección de Líder (Fault-Tolerance):** Mediante la receta `Election` de Kazoo, los sensores eligen dinámicamente un coordinador. Si el líder falla, el sistema realiza un failover automático detectando la expiración del **Znode efímero**, permitiendo que otro nodo asuma el mando sin interrupción.
* **Sincronización y Agregación (Opción B):** Implementa un patrón de disparo secuencial. El líder genera un trigger en `/sequence_trigger` y los seguidores, al detectar el cambio mediante un *Watcher*, depositan sus mediciones en una **cola distribuida** para un procesamiento ordenado.
* **Configuración Distribuida en Caliente:** Uso de `DataWatch` para actualizar parámetros críticos (períodos de muestreo y URLs de API) en tiempo real en todo el clúster sin necesidad de reinicios.

### 🧠 2. Sentinel: Detección de Anomalías e IA Robusta

Para garantizar la fiabilidad de las alertas, el sistema aplica la técnica de **Diversidad de Diseño** (Ensemble Prediction).

* **Modelos Ortogonales:** El sistema evalúa los datos mediante cuatro modelos disjuntos: una Regla Física (determinista), Isolation Forest (estadístico), Autoencoder (reconstrucción) y LSTM (secuencial).
* **Voto por Consenso M-of-N:** Se requiere un quórum de al menos **3 de los 4 modelos** para declarar una anomalía como crítica. Esta estrategia de "Ensemble" reduce drásticamente los falsos positivos causados por el ruido del sensor o alucinaciones de modelos individuales.

### 🗄️ 3. Capa de Datos

La persistencia se gestiona mediante una Arquitectura que permite cumplir el comportamiento del sistema según el Teorema CAP:

* **Modo CP (Redis Sentinel):** Prioriza la **Consistencia Estricta** e integridad del dato, garantizando un único punto de escritura activo para mantener la ordenación total de las series temporales.

---

## 🚀 Despliegue e Infraestructura

### Stack Tecnológico

* **Coordinación:** Apache ZooKeeper (Clúster de 3 nodos para garantizar quórum).
* **Persistencia:** Redis Stack Server con soporte para `RedisTimeSeries`.
* **IA & Backend:** Python 3.10+, Kazoo, TensorFlow, Scikit-learn, FastAPI.
* **Observabilidad:** Grafana para el análisis forense y trazabilidad de las decisiones de la IA.

### Instrucciones de Ejecución

1. **Levantar el Clúster:** Despliegue del stack completo (Zookeeper Ensemble + Sensores + Sentinel API + Redis).
   ```bash
   docker-compose up -d --build