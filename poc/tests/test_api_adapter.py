"""Tests for the API adapter: headers, HTTP error mapping, and compensation."""
import httpx
import pytest

from adapters.api_adapter import ApiAdapter
from saga.errors import PermanentError, TransientError


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


def test_sends_payment_with_correlation_and_idempotency_headers(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured.update({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse(200, {"reference": "PAY-123"})

    monkeypatch.setattr(httpx, "post", fake_post)

    ctx = {"correlationId": "cid-api", "payload": {"account": "123", "amount": 1000}}
    result = ApiAdapter("http://target/").execute_payment(ctx)

    assert result == {"execution_reference": "PAY-123", "applied": True}
    assert captured["url"] == "http://target/payments"
    assert captured["json"] == ctx["payload"]
    assert captured["headers"]["X-Correlation-Id"] == "cid-api"
    assert captured["headers"]["Idempotency-Key"] == "cid-api:payment"


def test_maps_timeout_to_transient_error(monkeypatch):
    def fake_post(*_args, **_kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "post", fake_post)

    ctx = {"correlationId": "cid-timeout", "payload": {"account": "123", "amount": 1000}}
    with pytest.raises(TransientError, match="timeout"):
        ApiAdapter("http://target").execute_payment(ctx)


def test_maps_transport_error_to_transient_error(monkeypatch):
    def fake_post(*_args, **_kwargs):
        raise httpx.TransportError("network down")

    monkeypatch.setattr(httpx, "post", fake_post)

    ctx = {"correlationId": "cid-network", "payload": {"account": "123", "amount": 1000}}
    with pytest.raises(TransientError, match="transport"):
        ApiAdapter("http://target").execute_payment(ctx)


def test_maps_server_error_to_transient_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: FakeResponse(503))

    ctx = {"correlationId": "cid-5xx", "payload": {"account": "123", "amount": 1000}}
    with pytest.raises(TransientError, match="5xx"):
        ApiAdapter("http://target").execute_payment(ctx)


def test_maps_client_error_to_permanent_error_without_leaking_response_body(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *_args, **_kwargs: FakeResponse(409, {"detail": "PII must not leak"}),
    )

    ctx = {"correlationId": "cid-4xx", "payload": {"account": "123", "amount": 1000}}
    with pytest.raises(PermanentError) as exc:
        ApiAdapter("http://target").execute_payment(ctx)

    assert "409" in str(exc.value)
    assert "PII" not in str(exc.value)


def test_reverses_payment_with_reference_and_compensation_headers(monkeypatch):
    captured = {}

    def fake_post(url, headers, timeout):
        captured.update({"url": url, "headers": headers, "timeout": timeout})
        return FakeResponse(200)

    monkeypatch.setattr(httpx, "post", fake_post)

    ApiAdapter("http://target").reverse_payment(
        {"correlationId": "cid-reversal", "execution_reference": "PAY-123"}
    )

    assert captured["url"] == "http://target/payments/PAY-123/reversal"
    assert captured["headers"]["X-Correlation-Id"] == "cid-reversal"
    assert captured["headers"]["Idempotency-Key"] == "cid-reversal:reversal"


def test_skips_reversal_when_payment_reference_is_missing(monkeypatch):
    called = {"value": False}

    def fake_post(*_args, **_kwargs):
        called["value"] = True

    monkeypatch.setattr(httpx, "post", fake_post)

    ApiAdapter("http://target").reverse_payment({"correlationId": "cid-no-ref"})

    assert called["value"] is False


def test_raises_http_error_when_reversal_call_fails(monkeypatch):
    def fake_post(*_args, **_kwargs):
        raise httpx.HTTPError("reversal failed")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(httpx.HTTPError, match="reversal failed"):
        ApiAdapter("http://target").reverse_payment(
            {"correlationId": "cid-reversal-error", "execution_reference": "PAY-500"}
        )
