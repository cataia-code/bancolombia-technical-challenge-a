"""Domain errors used by the saga engine."""


class SagaError(Exception):
    """Base class for saga engine errors."""


class TransientError(SagaError):
    """Temporary recoverable failure, such as a timeout, 5xx, or unavailable dependency."""


class PermanentError(SagaError):
    """Non-recoverable failure, such as invalid business data or a 4xx response."""
