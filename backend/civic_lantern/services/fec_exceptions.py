class FECAPIError(Exception):
    retryable: bool = False

    def __init__(self, message: str, *, status_code: int | None = None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class FECRateLimitError(FECAPIError):
    """Raised when FEC API rate limit is exceeded.

    The minute_limiter in FECClient should prevent 429s entirely, but its
    window is only 1 second wide — if one does occur, fec_retry's backoff
    (2s minimum) already outlasts that window, so a retry can succeed.
    """

    retryable = True


class FECNotFoundError(FECAPIError):
    """Raised when requested resource is not found (404)."""

    retryable = False


class FECValidationError(FECAPIError):
    """Raised when invalid parameters are provided (400)."""

    retryable = False


class FECAuthenticationError(FECAPIError):
    """Raised when API key is invalid or missing (401/403)."""

    retryable = False


class FECServerError(FECAPIError):
    """Raised when server returns 5xx error."""

    retryable = True


class FECTimeoutError(FECAPIError):
    """Raised when request times out."""

    retryable = True


class FECNetworkError(FECAPIError):
    """Raised when network connectivity fails."""

    retryable = True


class FECProtocolError(FECAPIError):
    """Raised when protocol/chunking errors occur."""

    retryable = True


class PartialFetchError(Exception):
    """Raised when pagination exhausts retries on some pages but not all.

    Carries whatever records were successfully fetched, so a caller can
    choose to ingest the partial data rather than discarding it outright —
    while still being able to tell the run wasn't fully clean.
    """

    def __init__(self, message: str, *, results: list[dict], failed_pages: list[int]):
        super().__init__(message)
        self.results = results
        self.failed_pages = failed_pages
