"""Componente reutilizable: Notificación.

Ejemplo de capacidad compartida por N procesos. En la PoC registra la
notificación en el contexto; en real llamaría a un servicio de mensajería.
"""
from __future__ import annotations

from typing import Any


def notificar(ctx: dict[str, Any]) -> dict[str, Any]:
    cid = ctx.get("correlationId")
    ref = ctx.get("referencia_ejecucion")
    return {"notificado": True, "notificacion": f"pago {ref} procesado (cid={cid})"}
