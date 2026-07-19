"""Modelos del motor de saga: paso, resultado y contexto de ejecución."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Un paso ejecuta un efecto y devuelve datos que se fusionan al contexto.
StepFn = Callable[[dict[str, Any]], Optional[dict[str, Any]]]
CompensateFn = Callable[[dict[str, Any]], None]


@dataclass
class Step:
    """Un paso de la saga con su compensación opcional.

    `idempotent=True` hace que el motor consulte el idempotency store antes de
    re-aplicar el efecto (clave ante reintentos y reprocesos desde la cola).
    """

    name: str
    execute: StepFn
    compensate: Optional[CompensateFn] = None
    idempotent: bool = True


@dataclass
class SagaResult:
    status: str  # "OK" | "FAILED"
    correlation_id: str
    context: dict[str, Any]
    compensated_steps: list[str] = field(default_factory=list)
    dead_lettered: bool = False
    error: Optional[str] = None
    failed_step: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "OK"
