"""FastAPI orchestrator: receives a webhook, runs the saga, and returns a trace."""
from __future__ import annotations

import hashlib
import os
import secrets
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from adapters.api_adapter import ApiAdapter
from flow import build_payment_flow
from infra.memory import InMemoryTracer, RealSleeper
from infra.redis_infra import RedisDLQ, RedisIdempotencyStore, connect
from saga.engine import SagaEngine

API_URL = os.getenv("MOCK_API_URL", "http://mock-api:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
POC_API_KEY = os.getenv("POC_API_KEY", "")

app = FastAPI(title="Process Orchestrator PoC")
_redis = connect(REDIS_URL)
_dlq = RedisDLQ(_redis)
_idem = RedisIdempotencyStore(_redis)


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not POC_API_KEY:
        return
    if not secrets.compare_digest(x_api_key, POC_API_KEY):
        raise HTTPException(status_code=401, detail="API key is invalid or missing")


def _mask_account(account: str) -> str:
    return f"***{account[-4:]}" if account and len(account) >= 4 else "***"


class WebhookPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str = Field(alias="cuenta")
    amount: float = Field(alias="monto")
    mode: str = Field(default="ok", alias="modo")


@app.post("/webhook", dependencies=[Depends(require_api_key)])
def webhook(body: WebhookPayload):
    cid = str(uuid.uuid4())
    adapter = ApiAdapter(API_URL)
    tracer = InMemoryTracer(echo=True)
    engine = SagaEngine(tracer, _dlq, _idem, RealSleeper(), max_retries=3, base_delay=0.3)

    steps = build_payment_flow(
        execute_payment=adapter.execute_payment,
        reverse_payment=adapter.reverse_payment,
    )
    payload = body.model_dump()
    input_hash = hashlib.sha256(repr(sorted(payload.items())).encode()).hexdigest()[:12]
    masked_account = _mask_account(payload["account"])
    tracer.emit("INPUT", cid, {"inputHash": input_hash, "account": masked_account})

    ctx = {"correlationId": cid, "payload": payload}
    result = engine.run("process_payment", steps, ctx)
    reference = ctx.get("execution_reference")

    return {
        "correlationId": result.correlation_id,
        "status": result.status,
        "deadLettered": result.dead_lettered,
        "compensated": result.compensated_steps,
        "compensados": result.compensated_steps,
        "error": result.error,
        "reference": reference,
        "referencia": reference,
        "account": masked_account,
        "cuenta": masked_account,
        "trace": tracer.events,
    }


@app.get("/dlq")
def read_dlq():
    return {"size": _dlq.size(), "items": _dlq.items()}


@app.get("/health")
def health():
    return {"status": "ok"}
