"""Errores de dominio del motor de saga.

La distinción es deliberada y central: solo los errores *transitorios* se
reintentan; los *permanentes* disparan compensación + dead-letter de inmediato.
"""


class SagaError(Exception):
    """Raíz de los errores del motor."""


class TransientError(SagaError):
    """Fallo temporal y recuperable (timeout, 5xx, indisponibilidad).

    El motor lo reintenta con backoff exponencial + jitter.
    """


class PermanentError(SagaError):
    """Fallo no recuperable (validación de negocio, 4xx, dato inválido).

    No se reintenta: se compensan los pasos previos y se envía a la DLQ.
    """
