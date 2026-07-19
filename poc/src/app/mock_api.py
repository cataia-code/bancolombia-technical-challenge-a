"""Mock target system used by the local PoC."""
from __future__ import annotations

from collections import defaultdict

from fastapi import FastAPI, Header, Request, Response

app = FastAPI(title="Mock Target System")

_attempts: dict[str, int] = defaultdict(int)
_reversals: set[str] = set()


@app.post("/payments")
@app.post("/pagos")
async def create_payment(request: Request, idempotency_key: str = Header(default="no-key")):
    payload = await request.json()
    mode = payload.get("mode", payload.get("modo", "ok"))

    if mode in {"permanent", "permanente"}:
        return Response(
            content='{"error":"business rejection"}',
            status_code=400,
            media_type="application/json",
        )

    if mode in {"transient", "transitorio"}:
        _attempts[idempotency_key] += 1
        if _attempts[idempotency_key] <= 2:
            return Response(
                content='{"error":"service unavailable"}',
                status_code=503,
                media_type="application/json",
            )

    reference = f"PAY-{abs(hash(idempotency_key)) % 100000:05d}"
    return {
        "reference": reference,
        "status": "APPLIED",
        "referencia": reference,
        "estado": "APLICADO",
    }


@app.post("/payments/{reference}/reversal")
@app.post("/pagos/{reference}/reversa")
async def reverse_payment(reference: str):
    _reversals.add(reference)
    return {
        "reference": reference,
        "status": "REVERSED",
        "referencia": reference,
        "estado": "REVERSADO",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
