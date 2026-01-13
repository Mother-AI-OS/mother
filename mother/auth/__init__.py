"""Authentication and authorization module.

This module provides multi-key API authentication with roles and scopes.
"""

from .keys import APIKeyStore
from .models import APIKey, IdentityContext, Role
from .scopes import check_scope, get_role_scopes

__all__ = [
    "APIKey",
    "APIKeyStore",
    "IdentityContext",
    "Role",
    "check_scope",
    "get_role_scopes",
]
