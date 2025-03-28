FROM python:3.9-slim

# Instalar herramientas del sistema necesarias para compilar e instalar dependencias
RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear carpeta de trabajo
WORKDIR /app

# Copiar todo el contenido del proyecto al contenedor
COPY . .

# Instalar dependencias desde requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Exponer el puerto que usa Flask
EXPOSE 5000

# Variable de entorno para producción
ENV FLASK_ENV=production

# Comando para ejecutar tu app
CMD ["python", "front/WebPharmaGo.py"]