"""Reusable validation component.

This business capability validates a simplified payment payload. Validation
errors are permanent because retrying the same invalid input would not fix it.
"""
from __future__ import annotations

from typing import Any

from saga.errors import PermanentError


def validate_payment(ctx: dict[str, Any]) -> dict[str, Any]:
    payload = ctx.get("payload", {})
    amount = payload.get("amount", payload.get("monto"))
    account = payload.get("account", payload.get("cuenta"))

    if account in (None, ""):
        raise PermanentError("account is required")
    if not isinstance(amount, (int, float)):
        raise PermanentError("amount must be numeric")
    if amount <= 0:
        raise PermanentError("amount must be greater than 0")
    if amount > 50_000_000:
        raise PermanentError("amount exceeds the allowed limit")

    return {"validated": True}
