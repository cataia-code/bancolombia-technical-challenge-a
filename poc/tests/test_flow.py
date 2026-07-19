"""Tests del flujo de ejemplo "procesar pago" con fakes (sin infraestructura)."""
import random

from adapters.rpa_adapter import RpaAdapter
from flow import construir_flujo
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
        InMemoryTracer(), InMemoryDLQ(), InMemoryIdempotencyStore(),
        ImmediateSleeper(), max_retries=3, base_delay=0.05, rng=random.Random(1),
    )
    return engine


def _pago_ok(ctx):
    return {"referencia_ejecucion": "PAY-001", "aplicado": True}


def test_flujo_pago_exitoso():
    engine = _engine()
    steps = construir_flujo(ejecutar_pago=_pago_ok)
    ctx = {"correlationId": "cid-ok", "payload": {"cuenta": "123", "monto": 100_000}}

    result = engine.run("procesar_pago", steps, ctx)

    assert result.ok
    assert ctx["validado"] is True
    assert ctx["referencia_ejecucion"] == "PAY-001"
    assert ctx["notificado"] is True


def test_flujo_con_rpa_transitorio_reintenta_y_termina():
    engine = _engine()
    rpa = RpaAdapter(fallos_transitorios=2)  # la UI falla 2 veces y luego responde
    steps = construir_flujo(
        ejecutar_pago=_pago_ok, registrar_portal=rpa.registrar_en_portal
    )
    ctx = {"correlationId": "cid-rpa", "payload": {"cuenta": "123", "monto": 50_000}}

    result = engine.run("procesar_pago", steps, ctx)

    assert result.ok
    assert ctx["registrado_en_portal"] is True
    assert ctx["portal_ref"] == "PORTAL-PAY-001"


def test_flujo_validacion_invalida_es_permanente():
    engine = _engine()
    steps = construir_flujo(ejecutar_pago=_pago_ok)
    ctx = {"correlationId": "cid-bad", "payload": {"cuenta": "123", "monto": -5}}

    result = engine.run("procesar_pago", steps, ctx)

    assert not result.ok
    assert result.failed_step == "validacion"
    assert result.dead_lettered
    assert result.compensated_steps == []  # nada se había ejecutado aún


def test_flujo_falla_tardia_compensa_el_pago():
    engine = _engine()
    reversas = {"n": 0}

    def reversar(_ctx):
        reversas["n"] += 1

    def portal_permanente(_ctx):
        raise PermanentError("el portal rechazó el registro")

    steps = construir_flujo(
        ejecutar_pago=_pago_ok,
        reversar_pago=reversar,
        registrar_portal=portal_permanente,
    )
    ctx = {"correlationId": "cid-comp", "payload": {"cuenta": "123", "monto": 100}}

    result = engine.run("procesar_pago", steps, ctx)

    assert not result.ok
    assert result.failed_step == "registro_portal"
    assert reversas["n"] == 1                         # el pago se reversó
    assert result.compensated_steps == ["ejecucion_pago"]
    assert result.dead_lettered
