"""Tests for the example payment flow with in-memory fakes."""
import random

import pytest

from adapters.rpa_adapter import RpaAdapter
from components.validation import validate_payment
from flow import build_payment_flow
from infra.memory import (
    ImmediateSleeper,
    InMemoryDLQ,
    InMemoryIdempotencyStore,
    InMemoryTracer,
)
from saga.engine import SagaEngine
from saga.errors import PermanentError


def _engine():
    engine = SagaEngine(
        InMemoryTracer(),
        InMemoryDLQ(),
        InMemoryIdempotencyStore(),
        ImmediateSleeper(),
        max_retries=3,
        base_delay=0.05,
        rng=random.Random(1),
    )
    return engine


def _successful_payment(ctx):
    return {"execution_reference": "PAY-001", "applied": True}


def test_processes_payment_and_sends_notification_for_valid_payload():
    engine = _engine()
    steps = build_payment_flow(execute_payment=_successful_payment)
    ctx = {"correlationId": "cid-ok", "payload": {"account": "123", "amount": 100_000}}

    result = engine.run("process_payment", steps, ctx)

    assert result.ok
    assert ctx["validated"] is True
    assert ctx["execution_reference"] == "PAY-001"
    assert ctx["notified"] is True


def test_retries_rpa_registration_and_completes_flow():
    engine = _engine()
    rpa = RpaAdapter(transient_failures=2)
    steps = build_payment_flow(
        execute_payment=_successful_payment,
        register_in_portal=rpa.register_in_portal,
    )
    ctx = {"correlationId": "cid-rpa", "payload": {"account": "123", "amount": 50_000}}

    result = engine.run("process_payment", steps, ctx)

    assert result.ok
    assert ctx["registered_in_portal"] is True
    assert ctx["portal_ref"] == "PORTAL-PAY-001"


def test_sends_invalid_payment_to_dlq_without_compensation():
    engine = _engine()
    steps = build_payment_flow(execute_payment=_successful_payment)
    ctx = {"correlationId": "cid-bad", "payload": {"account": "123", "amount": -5}}

    result = engine.run("process_payment", steps, ctx)

    assert not result.ok
    assert result.failed_step == "validation"
    assert result.dead_lettered
    assert result.compensated_steps == []


def test_compensates_payment_when_later_portal_step_fails():
    engine = _engine()
    reversals = {"count": 0}

    def reverse_payment(_ctx):
        reversals["count"] += 1

    def permanently_failing_portal(_ctx):
        raise PermanentError("portal rejected the registration")

    steps = build_payment_flow(
        execute_payment=_successful_payment,
        reverse_payment=reverse_payment,
        register_in_portal=permanently_failing_portal,
    )
    ctx = {"correlationId": "cid-comp", "payload": {"account": "123", "amount": 100}}

    result = engine.run("process_payment", steps, ctx)

    assert not result.ok
    assert result.failed_step == "portal_registration"
    assert reversals["count"] == 1
    assert result.compensated_steps == ["payment_execution"]
    assert result.dead_lettered


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"amount": 100}, "account is required"),
        ({"account": "123", "amount": "100"}, "amount must be"),
        ({"account": "123", "amount": 50_000_001}, "amount exceeds"),
    ],
)
def test_rejects_invalid_payment_payloads(payload, message):
    with pytest.raises(PermanentError, match=message):
        validate_payment({"payload": payload})
