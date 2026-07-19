"""Tests del motor de saga: éxito, reintento, error permanente, DLQ, compensación."""
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
        tracer, dlq, idem, sleeper, max_retries=max_retries, base_delay=0.1,
        rng=random.Random(1),
    )
    return engine, tracer, dlq, sleeper


def test_caso_exitoso():
    engine, tracer, dlq, _ = _engine()
    steps = [Step("a", lambda c: {"a": 1}), Step("b", lambda c: {"b": 2})]
    ctx = {"correlationId": "cid-1"}

    result = engine.run("proc", steps, ctx)

    assert result.ok
    assert ctx == {"correlationId": "cid-1", "a": 1, "b": 2}
    assert dlq.size() == 0
    assert tracer.events_of("SALIDA")


def test_reintento_transitorio_luego_exito():
    engine, tracer, dlq, sleeper = _engine()
    intentos = {"n": 0}

    def flaky(_ctx):
        intentos["n"] += 1
        if intentos["n"] < 3:  # falla 2 veces, éxito al 3er intento
            raise TransientError("timeout")
        return {"ok": True}

    result = engine.run("proc", [Step("flaky", flaky)], {"correlationId": "cid-2"})

    assert result.ok
    assert intentos["n"] == 3
    assert len(sleeper.delays) == 2  # dos backoffs
    assert len(tracer.events_of("REINTENTO")) == 2
    assert dlq.size() == 0


def test_reintentos_agotados_van_a_dlq():
    engine, tracer, dlq, sleeper = _engine(max_retries=2)

    def siempre_falla(_ctx):
        raise TransientError("5xx")

    result = engine.run("proc", [Step("x", siempre_falla)], {"correlationId": "cid-3"})

    assert not result.ok
    assert result.dead_lettered
    assert dlq.size() == 1
    assert dlq.messages[0]["failedStep"] == "x"
    assert len(sleeper.delays) == 2  # max_retries backoffs


def test_error_permanente_no_se_reintenta_y_compensa():
    engine, tracer, dlq, sleeper = _engine()
    reversado = {"llamado": False}

    def paso_ok(_ctx):
        return {"aplicado": True}

    def compensar(_ctx):
        reversado["llamado"] = True

    def paso_permanente(_ctx):
        raise PermanentError("dato inválido")

    steps = [
        Step("ejecucion", paso_ok, compensate=compensar),
        Step("segundo", paso_permanente),
    ]
    result = engine.run("proc", steps, {"correlationId": "cid-4"})

    assert not result.ok
    assert result.failed_step == "segundo"
    assert result.dead_lettered
    assert reversado["llamado"] is True                 # se compensó
    assert result.compensated_steps == ["ejecucion"]    # en orden inverso
    assert len(sleeper.delays) == 0                      # NO se reintentó
    assert dlq.size() == 1


def test_idempotencia_evita_doble_efecto():
    engine, tracer, dlq, _ = _engine()
    ejecuciones = {"n": 0}

    def con_efecto(_ctx):
        ejecuciones["n"] += 1
        return {"aplicado": True}

    steps = [Step("pago", con_efecto, idempotent=True)]
    # marcar como ya visto simula un reproceso desde la cola
    engine._idem.mark("cid-5", "pago")

    result = engine.run("proc", steps, {"correlationId": "cid-5"})

    assert result.ok
    assert ejecuciones["n"] == 0  # no se re-aplicó el efecto
    assert tracer.events_of("SKIP_IDEMPOTENTE")
