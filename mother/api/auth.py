"""API key authentication middleware."""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from ..config.settings import get_settings

# API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """Verify the API key from header.

    Returns the API key if valid, raises HTTPException if invalid.
    If no key is configured in settings, allows all requests.
    """
    settings = get_settings()

    # If no API key configured, allow all requests (local-only mode)
    if not settings.api_key:
        return None

    # If auth is required but no key provided
    if settings.require_auth and not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
        )

    # Verify key matches
    if api_key and api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key


def optional_api_key(
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """Optional API key - doesn't raise if missing."""
    return api_key
