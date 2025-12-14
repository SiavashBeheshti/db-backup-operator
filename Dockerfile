FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY operator/ ./operator/

CMD ["kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "operator/handlers.py"]