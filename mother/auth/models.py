"""Authentication models for multi-key auth system."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class Role(str, Enum):
    """API key roles with different permission levels."""

    ADMIN = "admin"  # Full access including key management
    OPERATOR = "operator"  # Execute capabilities, no key/policy management
    READONLY = "readonly"  # Read-only operations only


@dataclass
class APIKey:
    """API key data model."""

    id: str  # UUID
    name: str  # Human-readable name
    key_hash: str  # bcrypt hash of actual key
    role: Role
    scopes: list[str] = field(default_factory=list)  # Capability prefixes
    created_at: datetime = field(default_factory=_utcnow)
    expires_at: datetime | None = None
    revoked: bool = False
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if the key is currently valid."""
        if self.revoked:
            return False
        if self.expires_at and datetime.now(UTC) > self.expires_at:
            return False
        return True

    def to_dict(self) -> dict:
        """Convert to dictionary (excludes key_hash for safety)."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "scopes": self.scopes,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked": self.revoked,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "metadata": self.metadata,
        }


@dataclass
class IdentityContext:
    """Identity context passed through request lifecycle.

    This context is attached to each authenticated request and contains
    the identity information derived from the API key.
    """

    key_id: str
    name: str
    role: Role
    scopes: list[str] = field(default_factory=list)

    def has_scope(self, required: str) -> bool:
        """Check if this identity has the required scope.

        Scope format: "prefix:action" or "prefix:*" for wildcard.
        Examples: "filesystem:read", "tasks:*", "*" (admin all-access)

        Args:
            required: The scope string required for the operation.

        Returns:
            True if the identity has the required scope.
        """
        # Admin with "*" scope has all permissions
        if "*" in self.scopes:
            return True

        # Check for exact match
        if required in self.scopes:
            return True

        # Check for wildcard match (e.g., "filesystem:*" matches "filesystem:read")
        if ":" in required:
            prefix = required.split(":")[0]
            wildcard = f"{prefix}:*"
            if wildcard in self.scopes:
                return True

        return False

    def is_admin(self) -> bool:
        """Check if this identity has admin role."""
        return self.role == Role.ADMIN

    def is_operator(self) -> bool:
        """Check if this identity has operator role."""
        return self.role == Role.OPERATOR

    def is_readonly(self) -> bool:
        """Check if this identity has readonly role."""
        return self.role == Role.READONLY

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "key_id": self.key_id,
            "name": self.name,
            "role": self.role.value,
            "scopes": self.scopes,
        }
