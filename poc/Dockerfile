FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# El comando concreto (orquestador o mock-api) lo define docker-compose.
CMD ["uvicorn", "app.orchestrator:app", "--host", "0.0.0.0", "--port", "8000"]
