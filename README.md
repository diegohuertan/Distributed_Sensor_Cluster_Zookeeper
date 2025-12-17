# 🛡️ AeroGuard: Distributed Critical Monitoring System

> **Arquitectura distribuida tolerante a fallos para la monitorización de sistemas críticos en tiempo real.**

![Architecture Diagram](Descripcion_Arquitectura.png) **

## 📋 Project Overview
AeroGuard es una solución de ingeniería de software diseñada bajo principios de **Sistemas Críticos**. El sistema simula una red de sensores redundantes que operan bajo un modelo de **Consenso Distribuido** para garantizar la integridad de los datos incluso ante particiones de red o caídas de nodos (Crash Failures).

A diferencia de sistemas tradicionales, AeroGuard no tiene un punto único de fallo (SPOF) en su capa de recolección. Utiliza **Apache ZooKeeper** para la coordinación de clústeres y **algoritmos de elección de líder** para asegurar que siempre exista una fuente de verdad única reportando a la central de análisis.

## 🚀 Key Features (Arquitectura & Diseño)

### 🧠 Distributed Coordination (Control Plane)
- **Leader Election:** Algoritmo dinámico donde los nodos eligen un coordinador automáticamente. Si el líder cae, el sistema se recupera en milisegundos (Failover automático).
- **Service Discovery:** Registro efímero de nodos activos mediante ZNodes.
- **Hot-Reconfiguration:** Capacidad de actualizar parámetros críticos (frecuencia de muestreo, endpoints) en tiempo real sin detener el servicio, usando *Data Watchers*.

### 📡 Data Aggregation (Data Plane)
- **Distributed Queues:** Implementación del patrón Productor-Consumidor distribuido. Todos los nodos miden (Redundancia), pero solo el líder agrega y transmite.
- **Sensor Fusion Strategy:** Cálculo de medias agregadas para mitigación de ruido en sensores individuales.

### 🛡️ Analysis & Persistence (Legacy Integration)
- **Anomaly Detection:** API REST dedicada que ingesta los datos agregados y detecta desviaciones críticas en tiempo real.
- **Resilient Storage:** Capa de persistencia basada en Redis para el histórico de métricas.

## 🛠️ Tech Stack
- **Lenguaje:** Python 3.10+ (Kazoo, Requests, Flask).
- **Orquestación:** Docker & Docker Compose (Simulación de Cluster).
- **Coordinación:** Apache ZooKeeper (Ensemble de 3 nodos).
- **Persistencia:** Redis.