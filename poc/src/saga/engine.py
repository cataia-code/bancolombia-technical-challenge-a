"""Motor de saga con reintentos, compensación, DLQ e idempotencia.

Implementa el flujo técnico de la Pregunta 12 de la propuesta:
entrada -> validación -> ejecución (idempotente) -> reintento con backoff ante
fallo transitorio -> compensación en orden inverso + DLQ ante fallo permanente
o reintentos agotados. Todo correlacionado por `correlation_id`.
"""
from __future__ import annotations

import random
from typing import Any

from .errors import PermanentError, TransientError
from .models import SagaResult, Step
from .ports import DeadLetterQueue, IdempotencyStore, Sleeper, Tracer


class SagaEngine:
    def __init__(
        self,
        tracer: Tracer,
        dlq: DeadLetterQueue,
        idempotency: IdempotencyStore,
        sleeper: Sleeper,
        max_retries: int = 3,
        base_delay: float = 0.2,
        rng: random.Random | None = None,
    ) -> None:
        self._tracer = tracer
        self._dlq = dlq
        self._idem = idempotency
        self._sleep = sleeper
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._rng = rng or random.Random()

    def run(self, process: str, steps: list[Step], context: dict[str, Any]) -> SagaResult:
        cid = context["correlationId"]
        self._tracer.emit("INICIO", cid, {"proceso": process, "pasos": len(steps)})
        executed: list[Step] = []

        for step in steps:
            try:
                self._run_step(step, context, cid)
                executed.append(step)
                self._tracer.emit("EJECUCION", cid, {"step": step.name, "status": "OK"})
            except (PermanentError, TransientError) as exc:
                return self._fail(process, executed, context, cid, step, exc)

        self._tracer.emit("SALIDA", cid, {"status": "OK"})
        return SagaResult(status="OK", correlation_id=cid, context=context)

    # --- interno --------------------------------------------------------------

    def _run_step(self, step: Step, ctx: dict[str, Any], cid: str) -> None:
        if step.idempotent and self._idem.seen(cid, step.name):
            self._tracer.emit("SKIP_IDEMPOTENTE", cid, {"step": step.name})
            return

        attempt = 0
        while True:
            try:
                result = step.execute(ctx) or {}
                ctx.update(result)
                if step.idempotent:
                    self._idem.mark(cid, step.name)
                return
            except TransientError as exc:
                attempt += 1
                if attempt > self._max_retries:
                    raise
                delay = self._backoff(attempt)
                self._tracer.emit(
                    "REINTENTO",
                    cid,
                    {"step": step.name, "intento": attempt, "delay_s": round(delay, 3), "causa": str(exc)},
                )
                self._sleep.sleep(delay)

    def _backoff(self, attempt: int) -> float:
        # Exponencial con jitter: base * 2^(n-1) * [0.5, 1.0)
        return self._base_delay * (2 ** (attempt - 1)) * (0.5 + self._rng.random() * 0.5)

    def _fail(
        self,
        process: str,
        executed: list[Step],
        ctx: dict[str, Any],
        cid: str,
        failed: Step,
        error: Exception,
    ) -> SagaResult:
        compensated: list[str] = []
        for step in reversed(executed):  # rollback en orden inverso
            if step.compensate is None:
                continue
            try:
                step.compensate(ctx)
                compensated.append(step.name)
                self._tracer.emit("COMPENSACION", cid, {"step": step.name})
            except Exception as comp_err:  # noqa: BLE001 — se registra y se continúa
                self._tracer.emit(
                    "COMPENSACION_FALLIDA", cid, {"step": step.name, "error": str(comp_err)}
                )

        self._dlq.put(
            {
                "correlationId": cid,
                "proceso": process,
                "failedStep": failed.name,
                "error": str(error),
                "tipo": type(error).__name__,
            }
        )
        self._tracer.emit("DLQ", cid, {"failedStep": failed.name, "error": str(error)})
        return SagaResult(
            status="FAILED",
            correlation_id=cid,
            context=ctx,
            compensated_steps=compensated,
            dead_lettered=True,
            error=str(error),
            failed_step=failed.name,
        )
