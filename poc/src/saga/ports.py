"""Puertos (interfaces) del motor de saga.

El motor depende solo de estas abstracciones — nunca de Redis, HTTP o un
proveedor concreto. Los adaptadores concretos viven en `infra/` y `adapters/`.
Esto es Dependency Inversion: la misma pieza corre con fakes en memoria (tests)
o con Redis/HTTP (docker-compose) sin cambiar una línea del motor.
"""
from __future__ import annotations

from typing import Any, Protocol


class Tracer(Protocol):
    """Emite eventos estructurados correlacionados por `correlation_id`."""

    def emit(self, event: str, correlation_id: str, data: dict[str, Any]) -> None: ...


class DeadLetterQueue(Protocol):
    """Cola de mensajes irrecuperables que requieren intervención."""

    def put(self, message: dict[str, Any]) -> None: ...

    def size(self) -> int: ...


class IdempotencyStore(Protocol):
    """Registra (correlation_id, paso) ya aplicados para no repetir efectos."""

    def seen(self, correlation_id: str, step: str) -> bool: ...

    def mark(self, correlation_id: str, step: str) -> None: ...


class Sleeper(Protocol):
    """Espera inyectable: real en producción, instantánea en tests."""

    def sleep(self, seconds: float) -> None: ...
