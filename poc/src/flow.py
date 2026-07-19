"""Example process: process a payment.

Builds saga steps from reusable components and injected execution capabilities.
The execution capability can be an API adapter, an RPA adapter, or a test fake
without changing the process definition.

Order: validation -> execution with compensation -> optional portal registration
-> notification.
"""
from __future__ import annotations

from typing import Callable, Optional

from components.notification import send_notification
from components.validation import validate_payment
from saga.models import Step

Effect = Callable[[dict], Optional[dict]]


def build_payment_flow(
    execute_payment: Effect,
    reverse_payment: Optional[Callable[[dict], None]] = None,
    register_in_portal: Optional[Effect] = None,
) -> list[Step]:
    steps: list[Step] = [
        Step("validation", validate_payment, idempotent=False),
        Step("payment_execution", execute_payment, compensate=reverse_payment, idempotent=True),
    ]
    if register_in_portal is not None:
        steps.append(Step("portal_registration", register_in_portal, idempotent=True))
    steps.append(Step("notification", send_notification, idempotent=False))
    return steps
