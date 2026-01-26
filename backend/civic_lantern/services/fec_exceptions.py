class FECAPIError(Exception):
    """Base exception for FEC API errors."""

    pass


class FECRateLimitError(FECAPIError):
    """Raised when FEC API rate limit is exceeded."""

    pass


class FECNotFoundError(FECAPIError):
    """Raised when requested resource is not found (404)."""

    pass


class FECValidationError(FECAPIError):
    """Raised when invalid parameters are provided (400)."""

    pass


class FECAuthenticationError(FECAPIError):
    """Raised when API key is invalid or missing (401/403)."""

    pass


class FECTimeoutError(FECAPIError):
    """Raised when request times out."""

    pass
