class FECAPIError(Exception):
    retryable: bool = False

    def __init__(self, message: str, *, status_code: int | None = None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class FECRateLimitError(FECAPIError):
    """Raised when FEC API rate limit is exceeded."""

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
