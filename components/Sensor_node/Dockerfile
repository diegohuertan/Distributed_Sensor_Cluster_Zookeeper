# Usamos una imagen ligera de Python
FROM python:3.10-slim

# Evita que Python escriba archivos .pyc y burocratiza la salida
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copiar el código fuente
# Copiamos 'src' completo dentro de '/app/src'
COPY src/ ./src/

# 3. Configurar el entrypoint
# Usamos el path absoluto para evitar problemas de imports
ENV PYTHONPATH="${PYTHONPATH}:/app"

# El comando por defecto (se sobrescribe en el docker-compose con el ID)
ENTRYPOINT ["python", "src/main.py"]