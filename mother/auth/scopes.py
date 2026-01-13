"""Scope enforcement for capability access control.

Scopes provide fine-grained access control beyond roles. Each capability
maps to a scope, and API keys can be granted specific scopes.

Scope Format:
    - "prefix:action" - Specific action (e.g., "filesystem:read")
    - "prefix:*" - All actions in prefix (e.g., "filesystem:*")
    - "*" - All scopes (admin-only)

Examples:
    - "filesystem:read" - Read files
    - "filesystem:write" - Write/delete files
    - "filesystem:*" - All filesystem operations
    - "tasks:read" - View tasks
    - "tasks:write" - Create/update tasks
    - "shell:execute" - Execute shell commands
    - "policy:read" - View policy configuration
    - "policy:write" - Modify policy (admin-only)
    - "keys:manage" - Manage API keys (admin-only)
"""

import logging
import re

from .models import IdentityContext, Role

logger = logging.getLogger("mother.auth.scopes")

# Capability prefix to scope mapping
# Maps capability name patterns to their required scope
CAPABILITY_SCOPE_MAP: dict[str, str] = {
    # Filesystem operations
    r"^filesystem_(read|list|exists|stat|search).*": "filesystem:read",
    r"^filesystem_(write|create|delete|move|copy).*": "filesystem:write",
    # Tasks
    r"^tasks_(list|get|search|focus|top|stats).*": "tasks:read",
    r"^tasks_(add|update|complete|delete).*": "tasks:write",
    # Email
    r"^email_(list|get|search).*": "email:read",
    r"^email_(send|compose|reply|forward).*": "email:write",
    # Shell
    r"^shell_(run|execute).*": "shell:execute",
    # PDF
    r"^pdf_(info|count|read).*": "pdf:read",
    r"^pdf_(merge|split|extract|rotate|delete).*": "pdf:write",
    # Datacraft
    r"^datacraft_(list|get|search|stats).*": "datacraft:read",
    r"^datacraft_(process|delete).*": "datacraft:write",
    # Transmit
    r"^transmit_(channels|history|get).*": "transmit:read",
    r"^transmit_(email|fax|post|bea)$": "transmit:send",
    # Web
    r"^web_(fetch|search).*": "web:read",
    # Tor (high-risk)
    r"^tor_.*": "tor:access",
    r"^tor-shell_.*": "tor:access",
    # Memory
    r"^memory_(search|get).*": "memory:read",
    r"^memory_(remember|forget).*": "memory:write",
    # Policy (admin)
    r"^policy_(get|list|validate).*": "policy:read",
    r"^policy_(update|reload).*": "policy:write",
    # Key management (admin)
    r"^keys_(list|get).*": "keys:read",
    r"^keys_(add|revoke|rotate|delete).*": "keys:manage",
}

# Default scopes for each role
ROLE_DEFAULT_SCOPES: dict[Role, list[str]] = {
    Role.ADMIN: ["*"],  # All scopes
    Role.OPERATOR: [
        "filesystem:read",
        "filesystem:write",
        "tasks:read",
        "tasks:write",
        "email:read",
        "email:write",
        "shell:execute",
        "pdf:read",
        "pdf:write",
        "datacraft:read",
        "datacraft:write",
        "transmit:read",
        "transmit:send",
        "web:read",
        "memory:read",
        "memory:write",
    ],
    Role.READONLY: [
        "filesystem:read",
        "tasks:read",
        "email:read",
        "pdf:read",
        "datacraft:read",
        "transmit:read",
        "web:read",
        "memory:read",
        "policy:read",
    ],
}


def get_role_scopes(role: Role) -> list[str]:
    """Get default scopes for a role.

    Args:
        role: The role to get scopes for.

    Returns:
        List of scope strings.
    """
    return ROLE_DEFAULT_SCOPES.get(role, [])


def capability_to_scope(capability_name: str) -> str | None:
    """Convert a capability name to its required scope.

    Args:
        capability_name: Full capability name (e.g., "filesystem_read_file").

    Returns:
        Required scope string or None if no mapping found.
    """
    for pattern, scope in CAPABILITY_SCOPE_MAP.items():
        if re.match(pattern, capability_name):
            return scope

    # Fallback: extract prefix and use read scope
    if "_" in capability_name:
        prefix = capability_name.split("_")[0]
        return f"{prefix}:read"

    return None


def check_scope(identity: IdentityContext | None, capability: str) -> tuple[bool, str]:
    """Check if an identity has the required scope for a capability.

    This function should be called BEFORE policy evaluation to enforce
    scope-based access control.

    Args:
        identity: The identity context from authentication, or None for legacy mode.
        capability: The capability being requested.

    Returns:
        Tuple of (allowed, reason).
    """
    # Legacy mode: no identity context, allow all
    if identity is None:
        return True, "legacy_mode"

    # Get required scope for capability
    required_scope = capability_to_scope(capability)
    if required_scope is None:
        # No scope mapping, allow by default (will be checked by policy)
        logger.debug(f"No scope mapping for capability: {capability}")
        return True, "no_scope_required"

    # Check if identity has the required scope
    if identity.has_scope(required_scope):
        return True, "scope_granted"

    reason = f"Missing scope '{required_scope}' for capability '{capability}'"
    logger.warning(f"Scope check failed for {identity.name}: {reason}")
    return False, reason


def is_admin_scope(scope: str) -> bool:
    """Check if a scope is admin-only.

    Args:
        scope: The scope to check.

    Returns:
        True if this scope should only be granted to admins.
    """
    admin_only_scopes = [
        "policy:write",
        "keys:manage",
        "tor:access",
        "*",
    ]
    return scope in admin_only_scopes


def validate_scopes(scopes: list[str], role: Role) -> tuple[bool, str]:
    """Validate that scopes are appropriate for the role.

    Args:
        scopes: List of scopes to validate.
        role: The role being granted these scopes.

    Returns:
        Tuple of (valid, reason).
    """
    if role != Role.ADMIN:
        for scope in scopes:
            if is_admin_scope(scope):
                return False, f"Scope '{scope}' requires admin role"

    return True, "valid"


def parse_scope(scope: str) -> tuple[str, str]:
    """Parse a scope string into prefix and action.

    Args:
        scope: Scope string (e.g., "filesystem:read").

    Returns:
        Tuple of (prefix, action).

    Raises:
        ValueError: If scope format is invalid.
    """
    if scope == "*":
        return "*", "*"

    if ":" not in scope:
        raise ValueError(f"Invalid scope format: {scope} (expected 'prefix:action')")

    parts = scope.split(":", 1)
    return parts[0], parts[1]
