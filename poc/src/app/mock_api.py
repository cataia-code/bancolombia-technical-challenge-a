"""Sistema destino simulado (mock).

Modela el comportamiento del sistema real según `payload.modo`:
  - "ok"          -> 200 con referencia
  - "transitorio" -> 503 las primeras 2 veces por Idempotency-Key, luego 200
  - "permanente"  -> 400 (rechazo de negocio)
Expone además la reversa (compensación), idempotente por referencia.
"""
from __future__ import annotations

from collections import defaultdict

from fastapi import FastAPI, Header, Request, Response

app = FastAPI(title="Mock Sistema Destino")

_intentos: dict[str, int] = defaultdict(int)
_reversas: set[str] = set()


@app.post("/pagos")
async def crear_pago(request: Request, idempotency_key: str = Header(default="sin-clave")):
    payload = await request.json()
    modo = payload.get("modo", "ok")

    if modo == "permanente":
        return Response(content='{"error":"rechazo de negocio"}', status_code=400,
                        media_type="application/json")

    if modo == "transitorio":
        _intentos[idempotency_key] += 1
        if _intentos[idempotency_key] <= 2:
            return Response(content='{"error":"servicio no disponible"}', status_code=503,
                            media_type="application/json")

    referencia = f"PAY-{abs(hash(idempotency_key)) % 100000:05d}"
    return {"referencia": referencia, "estado": "APLICADO"}


@app.post("/pagos/{referencia}/reversa")
async def reversar(referencia: str):
    _reversas.add(referencia)  # idempotente: reversar dos veces no cambia el estado
    return {"referencia": referencia, "estado": "REVERSADO"}


@app.get("/health")
async def health():
    return {"status": "ok"}
