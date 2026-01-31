import logging

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from civic_lantern.services.fec_exceptions import FECAPIError

logger = logging.getLogger(__name__)


def is_retryable_fec_error(exception: BaseException) -> bool:
    return isinstance(exception, FECAPIError) and exception.retryable


def create_retry_decorator(
    max_attempts: int = 3,
    min_wait: int = 2,
    max_wait: int = 600,
):
    """
    Creates a pre-configured Tenacity retry decorator.
    """
    return retry(
        retry=retry_if_exception(is_retryable_fec_error),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        stop=stop_after_attempt(max_attempts),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


fec_retry = create_retry_decorator()
