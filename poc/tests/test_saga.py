"""Tests for the saga engine: success, retries, DLQ, compensation, idempotency."""
import random

from infra.memory import (
    ImmediateSleeper,
    InMemoryDLQ,
    InMemoryIdempotencyStore,
    InMemoryTracer,
)
from saga.engine import SagaEngine
from saga.errors import PermanentError, TransientError
from saga.models import Step


def _engine(max_retries=3):
    tracer, dlq, idem, sleeper = (
        InMemoryTracer(),
        InMemoryDLQ(),
        InMemoryIdempotencyStore(),
        ImmediateSleeper(),
    )
    engine = SagaEngine(
        tracer,
        dlq,
        idem,
        sleeper,
        max_retries=max_retries,
        base_delay=0.1,
        rng=random.Random(1),
    )
    return engine, tracer, dlq, sleeper


def test_returns_ok_when_all_steps_succeed():
    engine, tracer, dlq, _ = _engine()
    steps = [Step("a", lambda c: {"a": 1}), Step("b", lambda c: {"b": 2})]
    ctx = {"correlationId": "cid-1"}

    result = engine.run("proc", steps, ctx)

    assert result.ok
    assert ctx == {"correlationId": "cid-1", "a": 1, "b": 2}
    assert dlq.size() == 0
    assert tracer.events_of("OUTPUT")


def test_retries_transient_failures_until_step_succeeds():
    engine, tracer, dlq, sleeper = _engine()
    attempts = {"count": 0}

    def flaky(_ctx):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TransientError("timeout")
        return {"ok": True}

    result = engine.run("proc", [Step("flaky", flaky)], {"correlationId": "cid-2"})

    assert result.ok
    assert attempts["count"] == 3
    assert len(sleeper.delays) == 2
    assert len(tracer.events_of("RETRY")) == 2
    assert dlq.size() == 0


def test_sends_message_to_dlq_when_retries_are_exhausted():
    engine, tracer, dlq, sleeper = _engine(max_retries=2)

    def always_fails(_ctx):
        raise TransientError("5xx")

    result = engine.run("proc", [Step("x", always_fails)], {"correlationId": "cid-3"})

    assert not result.ok
    assert result.dead_lettered
    assert dlq.size() == 1
    assert dlq.messages[0]["failedStep"] == "x"
    assert dlq.messages[0]["process"] == "proc"
    assert len(sleeper.delays) == 2


def test_compensates_previous_steps_without_retrying_permanent_errors():
    engine, tracer, dlq, sleeper = _engine()
    reversal = {"called": False}

    def successful_step(_ctx):
        return {"applied": True}

    def compensate(_ctx):
        reversal["called"] = True

    def permanent_step(_ctx):
        raise PermanentError("invalid data")

    steps = [
        Step("execution", successful_step, compensate=compensate),
        Step("second", permanent_step),
    ]
    result = engine.run("proc", steps, {"correlationId": "cid-4"})

    assert not result.ok
    assert result.failed_step == "second"
    assert result.dead_lettered
    assert reversal["called"] is True
    assert result.compensated_steps == ["execution"]
    assert len(sleeper.delays) == 0
    assert dlq.size() == 1


def test_records_failed_compensation_and_still_sends_original_failure_to_dlq():
    engine, tracer, dlq, _ = _engine()

    def successful_step(_ctx):
        return {"applied": True}

    def failing_compensation(_ctx):
        raise RuntimeError("compensation unavailable")

    def permanent_step(_ctx):
        raise PermanentError("invalid data")

    steps = [
        Step("execution", successful_step, compensate=failing_compensation),
        Step("second", permanent_step),
    ]

    result = engine.run("proc", steps, {"correlationId": "cid-comp-fail"})

    assert not result.ok
    assert result.dead_lettered
    assert result.compensated_steps == []
    assert dlq.messages[0]["failedStep"] == "second"
    assert tracer.events_of("COMPENSATION_FAILED")[0]["step"] == "execution"


def test_skips_idempotent_step_when_effect_was_already_applied():
    engine, tracer, dlq, _ = _engine()
    executions = {"count": 0}

    def side_effect(_ctx):
        executions["count"] += 1
        return {"applied": True}

    steps = [Step("payment", side_effect, idempotent=True)]
    engine._idem.mark("cid-5", "payment")

    result = engine.run("proc", steps, {"correlationId": "cid-5"})

    assert result.ok
    assert executions["count"] == 0
    assert tracer.events_of("SKIP_IDEMPOTENT")
