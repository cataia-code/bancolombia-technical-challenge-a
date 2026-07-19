"""Proceso de ejemplo: "procesar pago".

Ensambla los pasos de la saga a partir de componentes reutilizables y de las
capacidades de ejecución (inyectadas). Las capacidades de ejecución se inyectan
para que el mismo flujo corra contra la API o contra el RPA sin cambios, y para
que los tests usen fakes.

Orden: validación -> ejecución (con compensación) -> registro (opcional) -> notificación
"""
from __future__ import annotations

from typing import Callable, Optional

from components.notification import notificar
from components.validation import validar_pago
from saga.models import Step

Effect = Callable[[dict], Optional[dict]]


def construir_flujo(
    ejecutar_pago: Effect,
    reversar_pago: Optional[Callable[[dict], None]] = None,
    registrar_portal: Optional[Effect] = None,
) -> list[Step]:
    steps: list[Step] = [
        # Validación: función pura, sin efecto externo -> no requiere idempotencia.
        Step("validacion", validar_pago, idempotent=False),
        # Ejecución: efecto externo con compensación (reversa).
        Step("ejecucion_pago", ejecutar_pago, compensate=reversar_pago, idempotent=True),
    ]
    if registrar_portal is not None:
        steps.append(Step("registro_portal", registrar_portal, idempotent=True))
    steps.append(Step("notificacion", notificar, idempotent=False))
    return steps
