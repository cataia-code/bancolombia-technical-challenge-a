"""Tests for Redis-backed infrastructure adapters using an in-memory fake."""
import json

import infra.redis_infra as redis_infra
from infra.redis_infra import RedisDLQ, RedisIdempotencyStore, connect


class FakeRedis:
    def __init__(self):
        self.lists = {}
        self.values = {}
        self.expirations = {}

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def llen(self, key):
        return len(self.lists.get(key, []))

    def lrange(self, key, start, end):
        values = self.lists.get(key, [])
        if end == -1:
            end = len(values) - 1
        return values[start : end + 1]

    def exists(self, key):
        return key in self.values

    def set(self, key, value, ex):
        self.values[key] = value
        self.expirations[key] = ex


def test_stores_and_reads_dead_letter_messages_as_json():
    client = FakeRedis()
    dlq = RedisDLQ(client, key="custom:dlq")

    dlq.put({"correlationId": "cid-1", "error": "failed"})

    assert client.lists["custom:dlq"] == [
        json.dumps({"correlationId": "cid-1", "error": "failed"}, ensure_ascii=False)
    ]
    assert dlq.size() == 1
    assert dlq.items() == [{"correlationId": "cid-1", "error": "failed"}]


def test_marks_and_detects_idempotency_keys_with_ttl():
    client = FakeRedis()
    store = RedisIdempotencyStore(client, ttl_seconds=60)

    assert store.seen("cid-1", "payment") is False

    store.mark("cid-1", "payment")

    assert store.seen("cid-1", "payment") is True
    assert client.values["idem:cid-1:payment"] == "1"
    assert client.expirations["idem:cid-1:payment"] == 60


def test_connect_creates_redis_client_with_decoded_responses(monkeypatch):
    captured = {}

    class FakeRedisModule:
        class Redis:
            @staticmethod
            def from_url(url, decode_responses):
                captured["url"] = url
                captured["decode_responses"] = decode_responses
                return "client"

    monkeypatch.setattr(redis_infra, "redis", FakeRedisModule, raising=False)
    monkeypatch.setitem(__import__("sys").modules, "redis", FakeRedisModule)

    assert connect("redis://example/0") == "client"
    assert captured == {"url": "redis://example/0", "decode_responses": True}
