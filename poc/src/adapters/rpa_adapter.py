"""Edge RPA adapter used when the target system has no API.

The adapter sits behind the same callable shape as `ApiAdapter`, so the process
does not need to know whether the effect is executed through HTTP or UI
automation.
"""
from __future__ import annotations

from typing import Any

from saga.errors import TransientError


class RpaAdapter:
    def __init__(self, transient_failures: int = 0) -> None:
        self._pending_failures = transient_failures

    def register_in_portal(self, ctx: dict[str, Any]) -> dict[str, Any]:
        if self._pending_failures > 0:
            self._pending_failures -= 1
            raise TransientError("the portal screen did not respond in time")
        reference = ctx.get("execution_reference", "NO-REF")
        return {"registered_in_portal": True, "portal_ref": f"PORTAL-{reference}"}
