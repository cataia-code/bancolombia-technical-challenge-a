"""Adaptador hacia un sistema destino por API (el camino preferido).

Traduce la semántica HTTP a errores de dominio:
  - timeout / 5xx  -> TransientError  (se reintenta)
  - 4xx            -> PermanentError  (no se reintenta)
Propaga `correlationId` e `Idempotency-Key` en headers.
`httpx` se importa de forma perezosa para no acoplar el motor a la librería.
"""
from __future__ import annotations

from typing import Any

from saga.errors import PermanentError, TransientError


class ApiAdapter:
    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def ejecutar_pago(self, ctx: dict[str, Any]) -> dict[str, Any]:
        import httpx  # import perezoso

        cid = ctx["correlationId"]
        payload = ctx["payload"]
        headers = {"X-Correlation-Id": cid, "Idempotency-Key": f"{cid}:pago"}
        try:
            resp = httpx.post(
                f"{self._base_url}/pagos",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:  # transitorio
            raise TransientError(f"timeout hacia sistema destino: {exc}") from exc
        except httpx.TransportError as exc:  # red caída, transitorio
            raise TransientError(f"error de transporte: {exc}") from exc

        if resp.status_code >= 500:
            raise TransientError(f"sistema destino 5xx: {resp.status_code}")
        if resp.status_code >= 400:
            # No se propaga el cuerpo crudo del sistema destino: puede contener PII
            # y terminaría en logs/DLQ. Solo el código de estado.
            raise PermanentError(f"rechazo de negocio {resp.status_code}")

        data = resp.json()
        return {"referencia_ejecucion": data.get("referencia"), "aplicado": True}

    def reversar_pago(self, ctx: dict[str, Any]) -> None:
        """Compensación: reversa la ejecución (idempotente por referencia)."""
        import httpx

        ref = ctx.get("referencia_ejecucion")
        if not ref:
            return
        cid = ctx["correlationId"]
        try:
            httpx.post(
                f"{self._base_url}/pagos/{ref}/reversa",
                headers={"X-Correlation-Id": cid, "Idempotency-Key": f"{cid}:reversa"},
                timeout=self._timeout,
            )
        except httpx.HTTPError:
            # La compensación best-effort; el motor registra COMPENSACION_FALLIDA.
            raise
