"""Componente reutilizable: Validación.

Capacidad de negocio consumida por muchos procesos. Aquí una validación de un
pago simplificado. Los errores de validación son PERMANENTES (no se reintentan).
"""
from __future__ import annotations

from typing import Any

from saga.errors import PermanentError


def validar_pago(ctx: dict[str, Any]) -> dict[str, Any]:
    payload = ctx.get("payload", {})
    monto = payload.get("monto")
    cuenta = payload.get("cuenta")

    if cuenta in (None, ""):
        raise PermanentError("cuenta requerida")
    if not isinstance(monto, (int, float)):
        raise PermanentError("monto debe ser numérico")
    if monto <= 0:
        raise PermanentError("monto debe ser mayor a 0")
    if monto > 50_000_000:
        raise PermanentError("monto excede el límite permitido")

    return {"validado": True}
