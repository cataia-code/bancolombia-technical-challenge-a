"""Tests for the FastAPI orchestrator wiring."""
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.orchestrator as orchestrator
from infra.memory import InMemoryDLQ, InMemoryIdempotencyStore


class FakeApiAdapter:
    def __init__(self, _base_url):
        pass

    def execute_payment(self, ctx):
        return {"execution_reference": "PAY-ORCH", "applied": True}

    def reverse_payment(self, _ctx):
        return None


class NoSleep:
    def sleep(self, _seconds):
        return None


class FakeDLQ:
    def __init__(self, items):
        self._items = items

    def size(self):
        return len(self._items)

    def items(self):
        return self._items


def test_allows_request_without_api_key_when_demo_mode_is_enabled(monkeypatch):
    monkeypatch.setattr(orchestrator, "POC_API_KEY", "")

    assert orchestrator.require_api_key("") is None


def test_rejects_request_when_api_key_is_invalid(monkeypatch):
    monkeypatch.setattr(orchestrator, "POC_API_KEY", "expected")

    try:
        orchestrator.require_api_key("wrong")
    except HTTPException as exc:
        assert exc.status_code == 401
        assert "API key" in exc.detail
    else:
        raise AssertionError("Expected HTTPException")


def test_accepts_request_when_api_key_matches(monkeypatch):
    monkeypatch.setattr(orchestrator, "POC_API_KEY", "expected")

    assert orchestrator.require_api_key("expected") is None


def test_masks_account_values_without_exposing_pii():
    assert orchestrator._mask_account("123456789") == "***6789"
    assert orchestrator._mask_account("123") == "***"
    assert orchestrator._mask_account("") == "***"


def test_health_endpoint_reports_ok():
    client = TestClient(orchestrator.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_returns_dlq_contents(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "_dlq",
        FakeDLQ([{"correlationId": "cid-dlq", "error": "failed"}]),
    )
    client = TestClient(orchestrator.app)

    response = client.get("/dlq")

    assert response.status_code == 200
    assert response.json() == {
        "size": 1,
        "items": [{"correlationId": "cid-dlq", "error": "failed"}],
    }


def test_processes_webhook_and_returns_trace_without_pii(monkeypatch):
    monkeypatch.setattr(orchestrator, "POC_API_KEY", "")
    monkeypatch.setattr(orchestrator, "ApiAdapter", FakeApiAdapter)
    monkeypatch.setattr(orchestrator, "RealSleeper", NoSleep)
    monkeypatch.setattr(orchestrator, "_dlq", InMemoryDLQ())
    monkeypatch.setattr(orchestrator, "_idem", InMemoryIdempotencyStore())
    client = TestClient(orchestrator.app)

    response = client.post(
        "/webhook",
        json={"account": "123456789", "amount": 1000, "mode": "ok"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "OK"
    assert body["deadLettered"] is False
    assert body["reference"] == "PAY-ORCH"
    assert body["account"] == "***6789"
    assert body["trace"][0]["event"] == "INPUT"
    assert body["trace"][0]["account"] == "***6789"
    assert "123456789" not in str(body["trace"])
