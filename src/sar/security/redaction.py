import logging
import uuid
from sar.domain.errors import SarError


def public_error(error: Exception) -> str:
    if isinstance(error, SarError):
        return str(error)
    correlation = uuid.uuid4().hex[:12]
    # No traceback, provider response, URL, address, credential, or exception text.
    logging.getLogger("sar").error(
        "operation_failed correlation=%s type=%s", correlation, type(error).__name__
    )
    return f"Não foi possível concluir a operação. Referência: {correlation}."
