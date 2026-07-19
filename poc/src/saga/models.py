"""Saga engine data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

StepFn = Callable[[dict[str, Any]], Optional[dict[str, Any]]]
CompensateFn = Callable[[dict[str, Any]], None]


@dataclass
class Step:
    """A saga step with optional compensation."""

    name: str
    execute: StepFn
    compensate: Optional[CompensateFn] = None
    idempotent: bool = True


@dataclass
class SagaResult:
    status: str
    correlation_id: str
    context: dict[str, Any]
    compensated_steps: list[str] = field(default_factory=list)
    dead_lettered: bool = False
    error: Optional[str] = None
    failed_step: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "OK"
