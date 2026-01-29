import logging

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


def is_transient_http_error(exception: BaseException) -> bool:
    """
    Predicate function to determine if an error is worth retrying.
    """
    if isinstance(exception, httpx.HTTPStatusError):
        # Retry on 5xx (Server) or 429 (Rate Limit)
        return (
            exception.response.status_code >= 500
            or exception.response.status_code == 429
        )

    # Retry on connectivity issues, timeouts, and protocol/chunking errors
    return isinstance(
        exception, (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError)
    )


def create_retry_decorator(
    max_attempts: int = 3,
    min_wait: int = 2,
    max_wait: int = 10,
):
    """
    Creates a pre-configured Tenacity retry decorator.
    """
    return retry(
        retry=retry_if_exception(is_transient_http_error),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        stop=stop_after_attempt(max_attempts),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


fec_retry = create_retry_decorator()
