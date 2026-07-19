"""Executable demo without infrastructure."""
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))

from adapters.rpa_adapter import RpaAdapter  # noqa: E402
from flow import build_payment_flow  # noqa: E402
from infra.memory import (  # noqa: E402
    ImmediateSleeper,
    InMemoryDLQ,
    InMemoryIdempotencyStore,
    InMemoryTracer,
)
from saga.engine import SagaEngine  # noqa: E402
from saga.errors import PermanentError  # noqa: E402


def run_scenario(title, steps, ctx):
    print(f"\n=== {title} ===")
    tracer = InMemoryTracer(echo=True)
    dlq = InMemoryDLQ()
    engine = SagaEngine(
        tracer,
        dlq,
        InMemoryIdempotencyStore(),
        ImmediateSleeper(),
        max_retries=3,
        base_delay=0.1,
        rng=random.Random(7),
    )
    result = engine.run("process_payment", steps, ctx)
    print(
        f"--> status={result.status} dead_lettered={result.dead_lettered} "
        f"compensated={result.compensated_steps} dlq={dlq.size()}"
    )
    return result


def successful_payment(_ctx):
    return {"execution_reference": "PAY-001", "applied": True}


def main():
    run_scenario(
        "1. Successful case",
        build_payment_flow(execute_payment=successful_payment),
        {"correlationId": "cid-demo-1", "payload": {"account": "123", "amount": 100_000}},
    )

    rpa = RpaAdapter(transient_failures=2)
    run_scenario(
        "2. Transient RPA retry -> success",
        build_payment_flow(
            execute_payment=successful_payment,
            register_in_portal=rpa.register_in_portal,
        ),
        {"correlationId": "cid-demo-2", "payload": {"account": "123", "amount": 50_000}},
    )

    def permanently_failing_portal(_ctx):
        raise PermanentError("the portal rejected the registration")

    def reverse_payment(_ctx):
        print("   [compensation] reversing payment PAY-001", file=sys.stderr)

    run_scenario(
        "3. Permanent error -> compensation + DLQ",
        build_payment_flow(
            execute_payment=successful_payment,
            reverse_payment=reverse_payment,
            register_in_portal=permanently_failing_portal,
        ),
        {"correlationId": "cid-demo-3", "payload": {"account": "123", "amount": 100}},
    )


if __name__ == "__main__":
    main()
