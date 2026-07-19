"""In-memory implementations of the saga ports."""
from __future__ import annotations

import json
import sys
from typing import Any


class InMemoryTracer:
    def __init__(self, echo: bool = False) -> None:
        self.events: list[dict[str, Any]] = []
        self._echo = echo

    def emit(self, event: str, correlation_id: str, data: dict[str, Any]) -> None:
        record = {"event": event, "correlationId": correlation_id, **data}
        self.events.append(record)
        if self._echo:
            print(json.dumps(record, ensure_ascii=False), file=sys.stderr)

    def events_of(self, name: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["event"] == name]


class InMemoryDLQ:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def put(self, message: dict[str, Any]) -> None:
        self.messages.append(message)

    def size(self) -> int:
        return len(self.messages)


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()

    def seen(self, correlation_id: str, step: str) -> bool:
        return (correlation_id, step) in self._seen

    def mark(self, correlation_id: str, step: str) -> None:
        self._seen.add((correlation_id, step))


class ImmediateSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.delays.append(seconds)


class RealSleeper:
    def sleep(self, seconds: float) -> None:
        import time

        time.sleep(seconds)
