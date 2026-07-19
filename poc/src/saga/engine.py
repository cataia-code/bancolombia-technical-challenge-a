"""Saga engine with retries, compensation, DLQ, and idempotency."""
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
        self._tracer.emit("START", cid, {"process": process, "steps": len(steps)})
        executed: list[Step] = []

        for step in steps:
            try:
                self._run_step(step, context, cid)
                executed.append(step)
                self._tracer.emit("EXECUTE", cid, {"step": step.name, "status": "OK"})
            except (PermanentError, TransientError) as exc:
                return self._fail(process, executed, context, cid, step, exc)

        self._tracer.emit("OUTPUT", cid, {"status": "OK"})
        return SagaResult(status="OK", correlation_id=cid, context=context)

    def _run_step(self, step: Step, ctx: dict[str, Any], cid: str) -> None:
        if step.idempotent and self._idem.seen(cid, step.name):
            self._tracer.emit("SKIP_IDEMPOTENT", cid, {"step": step.name})
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
                    "RETRY",
                    cid,
                    {"step": step.name, "attempt": attempt, "delay_s": round(delay, 3), "cause": str(exc)},
                )
                self._sleep.sleep(delay)

    def _backoff(self, attempt: int) -> float:
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
        for step in reversed(executed):
            if step.compensate is None:
                continue
            try:
                step.compensate(ctx)
                compensated.append(step.name)
                self._tracer.emit("COMPENSATE", cid, {"step": step.name})
            except Exception as comp_err:  # noqa: BLE001
                self._tracer.emit(
                    "COMPENSATION_FAILED", cid, {"step": step.name, "error": str(comp_err)}
                )

        self._dlq.put(
            {
                "correlationId": cid,
                "process": process,
                "failedStep": failed.name,
                "error": str(error),
                "errorType": type(error).__name__,
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
