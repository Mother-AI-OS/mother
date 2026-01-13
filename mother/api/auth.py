"""API key authentication middleware with multi-key support.

This module provides authentication middleware that supports both:
1. Legacy single-key mode: Uses MOTHER_API_KEY environment variable
2. Multi-key mode: Uses SQLite-backed key store with roles and scopes

The mode is determined automatically:
- If keys exist in the key store, multi-key mode is used
- Otherwise, falls back to legacy single-key mode

Usage:
    # In route handlers:
    @router.post("/command")
    async def execute_command(
        identity: IdentityContext | None = Depends(get_identity_context),
    ):
        if identity:
            print(f"Authenticated as {identity.name}")
"""

import logging

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from ..auth.keys import APIKeyStore, get_key_store
from ..auth.models import IdentityContext
from ..config.settings import get_settings

logger = logging.getLogger("mother.api.auth")

# API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _is_multi_key_mode() -> bool:
    """Check if multi-key mode is enabled.

    Multi-key mode is enabled when there are keys in the key store.
    Otherwise, falls back to legacy single-key mode.
    """
    try:
        store = get_key_store()
        return store.key_count() > 0
    except Exception:
        return False


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """Verify the API key from header.

    This function maintains backward compatibility with the legacy single-key mode
    while supporting multi-key mode when keys are configured in the store.

    Returns:
        The API key if valid, None if no auth required.

    Raises:
        HTTPException: If authentication fails.
    """
    settings = get_settings()

    # Check multi-key mode first
    if _is_multi_key_mode():
        if not api_key:
            if settings.require_auth:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key required. Provide X-API-Key header.",
                )
            return None

        store = get_key_store()
        identity = store.validate_key(api_key)
        if identity is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or revoked API key.",
            )
        return api_key

    # Legacy single-key mode
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


async def get_identity_context(
    api_key: str | None = Security(api_key_header),
) -> IdentityContext | None:
    """Get identity context from API key.

    This is the preferred authentication dependency for routes that need
    to know who is making the request. It returns an IdentityContext with
    the key's identity information, or None in legacy/unauthenticated mode.

    Usage:
        @router.post("/command")
        async def execute_command(
            identity: IdentityContext | None = Depends(get_identity_context),
        ):
            if identity:
                print(f"Request from {identity.name} with role {identity.role}")

    Returns:
        IdentityContext if authenticated in multi-key mode, None otherwise.

    Raises:
        HTTPException: If authentication fails.
    """
    settings = get_settings()

    # Check multi-key mode
    if _is_multi_key_mode():
        if not api_key:
            if settings.require_auth:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key required. Provide X-API-Key header.",
                )
            return None

        store = get_key_store()
        identity = store.validate_key(api_key)
        if identity is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or revoked API key.",
            )
        return identity

    # Legacy single-key mode: validate but return None (no identity context)
    if settings.api_key:
        if settings.require_auth and not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required. Provide X-API-Key header.",
            )
        if api_key and api_key != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key.",
            )

    return None


def optional_api_key(
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """Optional API key - doesn't raise if missing."""
    return api_key


async def require_admin(
    identity: IdentityContext | None = Depends(get_identity_context),
) -> IdentityContext:
    """Require admin role for the route.

    Usage:
        @router.post("/admin/action")
        async def admin_action(
            identity: IdentityContext = Depends(require_admin),
        ):
            # Only admins can reach here

    Raises:
        HTTPException: If not authenticated or not admin.
    """
    if identity is None:
        # Legacy mode: allow if no auth required
        settings = get_settings()
        if not settings.require_auth:
            # Create a pseudo-admin context for legacy mode
            return IdentityContext(
                key_id="legacy",
                name="legacy",
                role="admin",
                scopes=["*"],
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    if not identity.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )

    return identity


async def require_operator(
    identity: IdentityContext | None = Depends(get_identity_context),
) -> IdentityContext:
    """Require operator or admin role for the route.

    Raises:
        HTTPException: If not authenticated or insufficient role.
    """
    if identity is None:
        settings = get_settings()
        if not settings.require_auth:
            return IdentityContext(
                key_id="legacy",
                name="legacy",
                role="admin",
                scopes=["*"],
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    if identity.is_readonly():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin role required.",
        )

    return identity


def create_scope_dependency(required_scope: str):
    """Create a dependency that requires a specific scope.

    Usage:
        require_filesystem_write = create_scope_dependency("filesystem:write")

        @router.post("/files")
        async def create_file(
            identity: IdentityContext = Depends(require_filesystem_write),
        ):
            # Only keys with filesystem:write scope can reach here

    Args:
        required_scope: The scope required to access the route.

    Returns:
        A FastAPI dependency function.
    """

    async def scope_dependency(
        identity: IdentityContext | None = Depends(get_identity_context),
    ) -> IdentityContext:
        if identity is None:
            settings = get_settings()
            if not settings.require_auth:
                return IdentityContext(
                    key_id="legacy",
                    name="legacy",
                    role="admin",
                    scopes=["*"],
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )

        if not identity.has_scope(required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{required_scope}' required.",
            )

        return identity

    return scope_dependency
