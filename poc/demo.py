"""Demo ejecutable sin infraestructura: imprime la traza por correlationId de
tres escenarios (éxito, reintento transitorio, error permanente con compensación).

Uso:  python demo.py
"""
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))

from adapters.rpa_adapter import RpaAdapter  # noqa: E402
from flow import construir_flujo  # noqa: E402
from infra.memory import (  # noqa: E402
    ImmediateSleeper,
    InMemoryDLQ,
    InMemoryIdempotencyStore,
    InMemoryTracer,
)
from saga.engine import SagaEngine  # noqa: E402
from saga.errors import PermanentError  # noqa: E402


def escenario(titulo, steps, ctx):
    print(f"\n=== {titulo} ===")
    tracer = InMemoryTracer(echo=True)
    dlq = InMemoryDLQ()
    engine = SagaEngine(
        tracer, dlq, InMemoryIdempotencyStore(), ImmediateSleeper(),
        max_retries=3, base_delay=0.1, rng=random.Random(7),
    )
    result = engine.run("procesar_pago", steps, ctx)
    print(f"--> status={result.status} dead_lettered={result.dead_lettered} "
          f"compensados={result.compensated_steps} dlq={dlq.size()}")
    return result


def pago_ok(_ctx):
    return {"referencia_ejecucion": "PAY-001", "aplicado": True}


def main():
    # 1) Camino feliz
    escenario(
        "1. Caso exitoso",
        construir_flujo(ejecutar_pago=pago_ok),
        {"correlationId": "cid-demo-1", "payload": {"cuenta": "123", "monto": 100_000}},
    )

    # 2) RPA con fallo transitorio -> reintenta y termina
    rpa = RpaAdapter(fallos_transitorios=2)
    escenario(
        "2. Reintento transitorio (RPA) -> exito",
        construir_flujo(ejecutar_pago=pago_ok, registrar_portal=rpa.registrar_en_portal),
        {"correlationId": "cid-demo-2", "payload": {"cuenta": "123", "monto": 50_000}},
    )

    # 3) Error permanente tardío -> compensa el pago + DLQ
    def portal_permanente(_ctx):
        raise PermanentError("el portal rechazo el registro")

    def reversar(_ctx):
        print("   [compensacion] reversando pago PAY-001", file=sys.stderr)

    escenario(
        "3. Error permanente -> compensacion + DLQ",
        construir_flujo(
            ejecutar_pago=pago_ok, reversar_pago=reversar, registrar_portal=portal_permanente
        ),
        {"correlationId": "cid-demo-3", "payload": {"cuenta": "123", "monto": 100}},
    )


if __name__ == "__main__":
    main()
