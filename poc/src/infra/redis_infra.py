"""Redis-backed implementations of the saga ports."""
from __future__ import annotations

import json
from typing import Any


class RedisDLQ:
    def __init__(self, client, key: str = "dlq:payments") -> None:
        self._r = client
        self._key = key

    def put(self, message: dict[str, Any]) -> None:
        self._r.rpush(self._key, json.dumps(message, ensure_ascii=False))

    def size(self) -> int:
        return int(self._r.llen(self._key))

    def items(self) -> list[dict[str, Any]]:
        return [json.loads(message) for message in self._r.lrange(self._key, 0, -1)]


class RedisIdempotencyStore:
    def __init__(self, client, ttl_seconds: int = 86_400) -> None:
        self._r = client
        self._ttl = ttl_seconds

    def _k(self, correlation_id: str, step: str) -> str:
        return f"idem:{correlation_id}:{step}"

    def seen(self, correlation_id: str, step: str) -> bool:
        return bool(self._r.exists(self._k(correlation_id, step)))

    def mark(self, correlation_id: str, step: str) -> None:
        self._r.set(self._k(correlation_id, step), "1", ex=self._ttl)


def connect(url: str):
    import redis

    return redis.Redis.from_url(url, decode_responses=True)
