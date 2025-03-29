FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar todo el proyecto de una sola vez
COPY . .

# Instalar dependencias
RUN pip install -r requirements.txt

EXPOSE 5000

ENV FLASK_ENV=production

CMD ["python", "front/WebPharmaGo.py"]