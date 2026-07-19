"""Reusable notification component."""
from __future__ import annotations

from typing import Any


def send_notification(ctx: dict[str, Any]) -> dict[str, Any]:
    cid = ctx.get("correlationId")
    reference = ctx.get("execution_reference")
    return {"notified": True, "notification": f"payment {reference} processed (cid={cid})"}
