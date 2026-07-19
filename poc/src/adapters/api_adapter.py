"""Adapter for a target system exposed through HTTP APIs.

It translates HTTP semantics into domain errors:
  - timeout / 5xx -> TransientError
  - 4xx           -> PermanentError

It also propagates `correlationId` and `Idempotency-Key` headers. `httpx` is
imported lazily so the saga engine remains decoupled from HTTP infrastructure.
"""
from __future__ import annotations

from typing import Any

from saga.errors import PermanentError, TransientError


class ApiAdapter:
    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def execute_payment(self, ctx: dict[str, Any]) -> dict[str, Any]:
        import httpx

        cid = ctx["correlationId"]
        payload = ctx["payload"]
        headers = {"X-Correlation-Id": cid, "Idempotency-Key": f"{cid}:payment"}
        try:
            response = httpx.post(
                f"{self._base_url}/payments",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise TransientError(f"timeout calling target system: {exc}") from exc
        except httpx.TransportError as exc:
            raise TransientError(f"transport error calling target system: {exc}") from exc

        if response.status_code >= 500:
            raise TransientError(f"target system returned 5xx: {response.status_code}")
        if response.status_code >= 400:
            raise PermanentError(f"business rejection {response.status_code}")

        data = response.json()
        reference = data.get("reference", data.get("referencia"))
        return {"execution_reference": reference, "applied": True}

    def reverse_payment(self, ctx: dict[str, Any]) -> None:
        """Best-effort compensation for an applied payment."""
        import httpx

        reference = ctx.get("execution_reference")
        if not reference:
            return
        cid = ctx["correlationId"]
        try:
            httpx.post(
                f"{self._base_url}/payments/{reference}/reversal",
                headers={"X-Correlation-Id": cid, "Idempotency-Key": f"{cid}:reversal"},
                timeout=self._timeout,
            )
        except httpx.HTTPError:
            raise
