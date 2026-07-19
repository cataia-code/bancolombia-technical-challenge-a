"""Tests for the mock downstream system API."""
from fastapi.testclient import TestClient

import app.mock_api as mock_api


def test_health_endpoint_reports_ok():
    client = TestClient(mock_api.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_creates_payment_successfully_by_default():
    client = TestClient(mock_api.app)

    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "idem-ok"},
        json={"account": "123", "amount": 1000},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "APPLIED"
    assert response.json()["reference"].startswith("PAY-")


def test_returns_permanent_rejection_for_permanent_mode():
    client = TestClient(mock_api.app)

    response = client.post("/payments", json={"mode": "permanent"})

    assert response.status_code == 400
    assert response.json() == {"error": "business rejection"}


def test_returns_two_transient_failures_before_success_for_same_idempotency_key():
    client = TestClient(mock_api.app)
    mock_api._attempts.clear()
    headers = {"Idempotency-Key": "idem-transient"}
    payload = {"mode": "transient"}

    first = client.post("/payments", headers=headers, json=payload)
    second = client.post("/payments", headers=headers, json=payload)
    third = client.post("/payments", headers=headers, json=payload)

    assert first.status_code == 503
    assert second.status_code == 503
    assert third.status_code == 200
    assert third.json()["status"] == "APPLIED"


def test_reverses_payment_idempotently():
    client = TestClient(mock_api.app)
    mock_api._reversals.clear()

    first = client.post("/payments/PAY-123/reversal")
    second = client.post("/payments/PAY-123/reversal")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["reference"] == "PAY-123"
    assert first.json()["status"] == "REVERSED"
    assert mock_api._reversals == {"PAY-123"}
