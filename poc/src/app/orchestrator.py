"""Orquestador: recibe el disparador (webhook), corre la saga y responde.

Wiring de la versión con infraestructura: ApiAdapter -> mock API, Redis para DLQ
e idempotencia, tracer estructurado. El mismo motor y flujo de los tests.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import uuid

from fastapi import Depends, FastAPI, HTTPException, Header
from pydantic import BaseModel

from adapters.api_adapter import ApiAdapter
from flow import construir_flujo
from infra.memory import InMemoryTracer, RealSleeper
from infra.redis_infra import RedisDLQ, RedisIdempotencyStore, connect
from saga.engine import SagaEngine

API_URL = os.getenv("MOCK_API_URL", "http://mock-api:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
# Stand-in de autenticación para la PoC. En producción: OAuth2/mTLS servicio a
# servicio + gateway. Aquí una API key por header, obligatoria si está definida.
POC_API_KEY = os.getenv("POC_API_KEY", "")

app = FastAPI(title="Orquestador de Procesos (PoC)")
_redis = connect(REDIS_URL)
_dlq = RedisDLQ(_redis)
_idem = RedisIdempotencyStore(_redis)


def requiere_api_key(x_api_key: str = Header(default="")) -> None:
    if not POC_API_KEY:
        return  # sin key configurada: modo demo local
    if not secrets.compare_digest(x_api_key, POC_API_KEY):
        raise HTTPException(status_code=401, detail="API key inválida o ausente")


def _mask_cuenta(cuenta: str) -> str:
    """Enmascara PII para logs/respuesta: deja solo los últimos 4."""
    return f"***{cuenta[-4:]}" if cuenta and len(cuenta) >= 4 else "***"


class WebhookPayload(BaseModel):
    cuenta: str
    monto: float
    modo: str = "ok"  # ok | transitorio | permanente


@app.post("/webhook", dependencies=[Depends(requiere_api_key)])
def webhook(body: WebhookPayload):
    cid = str(uuid.uuid4())
    adapter = ApiAdapter(API_URL)
    tracer = InMemoryTracer(echo=True)  # imprime JSON estructurado a stderr
    engine = SagaEngine(tracer, _dlq, _idem, RealSleeper(), max_retries=3, base_delay=0.3)

    steps = construir_flujo(
        ejecutar_pago=adapter.ejecutar_pago,
        reversar_pago=adapter.reversar_pago,
    )
    payload = body.model_dump()
    # Se traza un hash del input (no la PII); la cuenta va enmascarada.
    input_hash = hashlib.sha256(repr(sorted(payload.items())).encode()).hexdigest()[:12]
    tracer.emit("ENTRADA", cid, {"inputHash": input_hash, "cuenta": _mask_cuenta(payload["cuenta"])})

    ctx = {"correlationId": cid, "payload": payload}
    result = engine.run("procesar_pago", steps, ctx)

    return {
        "correlationId": result.correlation_id,
        "status": result.status,
        "deadLettered": result.dead_lettered,
        "compensados": result.compensated_steps,
        "error": result.error,
        "referencia": ctx.get("referencia_ejecucion"),
        "cuenta": _mask_cuenta(payload["cuenta"]),  # respuesta sin PII
        "trace": tracer.events,
    }


@app.get("/dlq")
def ver_dlq():
    return {"size": _dlq.size(), "items": _dlq.items()}


@app.get("/health")
def health():
    return {"status": "ok"}
