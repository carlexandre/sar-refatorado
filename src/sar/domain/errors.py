class SarError(Exception):
    """Safe, user-facing error. Never wrap raw provider messages in this class."""


class ValidationError(SarError):
    pass


class AccessDenied(SarError):
    pass


class ConfigurationError(SarError):
    pass


class IntegrationError(SarError):
    pass


class NotFound(SarError):
    pass


class ConcurrencyError(SarError):
    pass


class DeliveryUncertain(IntegrationError):
    """Submission may have reached the SMTP server; do not automatically retry."""
