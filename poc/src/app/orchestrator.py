"""Orquestador: recibe el disparador (webhook), corre la saga y responde.

Wiring de la versión con infraestructura: ApiAdapter -> mock API, Redis para DLQ
e idempotencia, tracer estructurado. El mismo motor y flujo de los tests.
"""
from __future__ import annotations

import os
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

from adapters.api_adapter import ApiAdapter
from flow import construir_flujo
from infra.memory import InMemoryTracer, RealSleeper
from infra.redis_infra import RedisDLQ, RedisIdempotencyStore, connect
from saga.engine import SagaEngine

API_URL = os.getenv("MOCK_API_URL", "http://mock-api:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = FastAPI(title="Orquestador de Procesos (PoC)")
_redis = connect(REDIS_URL)
_dlq = RedisDLQ(_redis)
_idem = RedisIdempotencyStore(_redis)


class WebhookPayload(BaseModel):
    cuenta: str
    monto: float
    modo: str = "ok"  # ok | transitorio | permanente


@app.post("/webhook")
def webhook(body: WebhookPayload):
    cid = str(uuid.uuid4())
    adapter = ApiAdapter(API_URL)
    tracer = InMemoryTracer(echo=True)  # imprime JSON estructurado a stderr
    engine = SagaEngine(tracer, _dlq, _idem, RealSleeper(), max_retries=3, base_delay=0.3)

    steps = construir_flujo(
        ejecutar_pago=adapter.ejecutar_pago,
        reversar_pago=adapter.reversar_pago,
    )
    ctx = {"correlationId": cid, "payload": body.model_dump()}
    result = engine.run("procesar_pago", steps, ctx)

    return {
        "correlationId": result.correlation_id,
        "status": result.status,
        "deadLettered": result.dead_lettered,
        "compensados": result.compensated_steps,
        "error": result.error,
        "referencia": ctx.get("referencia_ejecucion"),
        "trace": tracer.events,
    }


@app.get("/dlq")
def ver_dlq():
    return {"size": _dlq.size(), "items": _dlq.items()}


@app.get("/health")
def health():
    return {"status": "ok"}
