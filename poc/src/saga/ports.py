"""Ports used by the saga engine."""
from __future__ import annotations

from typing import Any, Protocol


class Tracer(Protocol):
    def emit(self, event: str, correlation_id: str, data: dict[str, Any]) -> None: ...


class DeadLetterQueue(Protocol):
    def put(self, message: dict[str, Any]) -> None: ...

    def size(self) -> int: ...


class IdempotencyStore(Protocol):
    def seen(self, correlation_id: str, step: str) -> bool: ...

    def mark(self, correlation_id: str, step: str) -> None: ...


class Sleeper(Protocol):
    def sleep(self, seconds: float) -> None: ...
