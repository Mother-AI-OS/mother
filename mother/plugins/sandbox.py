"""Security sandbox for Mother plugins.

This module provides permission validation for plugin actions.
v1 implements permission checking only (no process isolation).

Permission format:
- Simple: "network", "secrets:read"
- Scoped: "filesystem:read:~/Documents", "filesystem:write:/tmp"

Future v2 will add:
- Process isolation via resource limits
- Filesystem sandboxing
- Network isolation
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .exceptions import PermissionError

logger = logging.getLogger("mother.plugins.sandbox")


class PermissionType(str, Enum):
    """Types of permissions plugins can request."""

    # Filesystem access
    FILESYSTEM_READ = "filesystem:read"
    FILESYSTEM_WRITE = "filesystem:write"
    FILESYSTEM_DELETE = "filesystem:delete"

    # Network access
    NETWORK = "network"
    NETWORK_INTERNAL = "network:internal"  # localhost only
    NETWORK_EXTERNAL = "network:external"  # internet

    # Secrets/credentials
    SECRETS_READ = "secrets:read"
    SECRETS_WRITE = "secrets:write"

    # System
    SHELL = "shell"
    SUBPROCESS = "subprocess"

    # User interaction
    CONFIRM = "confirm"  # Can request user confirmation
    NOTIFY = "notify"  # Can send notifications


@dataclass
class Permission:
    """Parsed permission with optional scope."""

    type: str  # e.g., "filesystem:read"
    scope: str | None = None  # e.g., "~/Documents"
    granted: bool = True

    @classmethod
    def parse(cls, permission_str: str) -> "Permission":
        """Parse a permission string.

        Examples:
            "network" -> Permission(type="network", scope=None)
            "filesystem:read" -> Permission(type="filesystem:read", scope=None)
            "filesystem:read:~/Documents" -> Permission(type="filesystem:read", scope="~/Documents")
        """
        parts = permission_str.split(":", 2)

        if len(parts) == 1:
            return cls(type=parts[0])
        elif len(parts) == 2:
            return cls(type=f"{parts[0]}:{parts[1]}")
        else:
            return cls(type=f"{parts[0]}:{parts[1]}", scope=parts[2])

    def matches(self, required: "Permission") -> bool:
        """Check if this permission satisfies a required permission.

        Args:
            required: The permission being requested

        Returns:
            True if this permission grants what's required
        """
        # Type must match
        if self.type != required.type:
            # Check for broader permissions (e.g., "filesystem" grants "filesystem:read")
            if not required.type.startswith(self.type + ":"):
                return False

        # If no scope on granted, it covers everything
        if self.scope is None:
            return True

        # If required has no scope but granted has scope, still matches
        if required.scope is None:
            return True

        # Check scope match
        return self._scope_matches(self.scope, required.scope)

    def _scope_matches(self, granted_scope: str, required_scope: str) -> bool:
        """Check if granted scope covers required scope.

        Supports:
        - Exact match
        - Path containment (granted=/home covers required=/home/user)
        - Glob patterns (granted=*.txt covers required=file.txt)
        """
        # Expand home directory
        granted_path = os.path.expanduser(granted_scope)
        required_path = os.path.expanduser(required_scope)

        # Exact match
        if granted_path == required_path:
            return True

        # Path containment
        try:
            granted_abs = Path(granted_path).resolve()
            required_abs = Path(required_path).resolve()

            # Check if required is under granted
            if str(required_abs).startswith(str(granted_abs) + os.sep):
                return True
            if required_abs == granted_abs:
                return True
        except Exception:
            pass

        # Glob pattern match
        if fnmatch.fnmatch(required_scope, granted_scope):
            return True

        return False

    def __str__(self) -> str:
        """String representation."""
        if self.scope:
            return f"{self.type}:{self.scope}"
        return self.type


@dataclass
class PermissionGrant:
    """A permission granted to a plugin."""

    permission: Permission
    source: str = "config"  # Where the grant came from
    expires: float | None = None  # Unix timestamp, None = never


@dataclass
class PermissionDenial:
    """Record of a denied permission request."""

    plugin_name: str
    permission: Permission
    action: str
    target: str | None
    timestamp: float


@dataclass
class PluginSandbox:
    """Security sandbox for a plugin.

    Validates permissions before allowing actions.
    """

    plugin_name: str
    granted_permissions: list[Permission] = field(default_factory=list)
    denied_actions: list[PermissionDenial] = field(default_factory=list)

    # Audit logging
    audit_enabled: bool = True

    @classmethod
    def from_manifest_permissions(
        cls,
        plugin_name: str,
        permissions: list[str],
    ) -> "PluginSandbox":
        """Create a sandbox from manifest permission strings.

        Args:
            plugin_name: Name of the plugin
            permissions: List of permission strings from manifest

        Returns:
            Configured sandbox instance
        """
        granted = [Permission.parse(p) for p in permissions]
        return cls(plugin_name=plugin_name, granted_permissions=granted)

    def check_permission(
        self,
        action: str,
        target: str | None = None,
    ) -> bool:
        """Check if an action is permitted.

        Args:
            action: The action being attempted (e.g., "filesystem:read")
            target: Optional target of the action (e.g., file path)

        Returns:
            True if permitted, False otherwise
        """
        required = Permission(type=action, scope=target)

        for granted in self.granted_permissions:
            if granted.matches(required):
                if self.audit_enabled:
                    logger.debug(
                        f"[{self.plugin_name}] Permission granted: {action}"
                        + (f" on {target}" if target else "")
                    )
                return True

        if self.audit_enabled:
            logger.warning(
                f"[{self.plugin_name}] Permission denied: {action}"
                + (f" on {target}" if target else "")
            )

        return False

    def require_permission(
        self,
        action: str,
        target: str | None = None,
    ) -> None:
        """Require a permission, raising if not granted.

        Args:
            action: The action being attempted
            target: Optional target of the action

        Raises:
            PermissionError: If permission is not granted
        """
        if not self.check_permission(action, target):
            raise PermissionError(
                plugin_name=self.plugin_name,
                action=action,
                required_permission=action,
                target=target,
            )

    def grant_permission(self, permission_str: str) -> None:
        """Grant an additional permission.

        Args:
            permission_str: Permission string to grant
        """
        permission = Permission.parse(permission_str)
        self.granted_permissions.append(permission)
        logger.info(f"[{self.plugin_name}] Granted permission: {permission}")

    def revoke_permission(self, permission_str: str) -> bool:
        """Revoke a permission.

        Args:
            permission_str: Permission string to revoke

        Returns:
            True if permission was found and revoked
        """
        permission = Permission.parse(permission_str)
        for i, granted in enumerate(self.granted_permissions):
            if str(granted) == str(permission):
                self.granted_permissions.pop(i)
                logger.info(f"[{self.plugin_name}] Revoked permission: {permission}")
                return True
        return False

    def list_permissions(self) -> list[str]:
        """List all granted permissions."""
        return [str(p) for p in self.granted_permissions]


class SandboxManager:
    """Manages sandboxes for all loaded plugins."""

    def __init__(self):
        self._sandboxes: dict[str, PluginSandbox] = {}
        self._global_denials: set[str] = set()  # Globally denied actions

    def create_sandbox(
        self,
        plugin_name: str,
        permissions: list[str],
    ) -> PluginSandbox:
        """Create a sandbox for a plugin.

        Args:
            plugin_name: Name of the plugin
            permissions: Permission strings from manifest

        Returns:
            New sandbox instance
        """
        sandbox = PluginSandbox.from_manifest_permissions(plugin_name, permissions)
        self._sandboxes[plugin_name] = sandbox
        return sandbox

    def get_sandbox(self, plugin_name: str) -> PluginSandbox | None:
        """Get the sandbox for a plugin."""
        return self._sandboxes.get(plugin_name)

    def remove_sandbox(self, plugin_name: str) -> None:
        """Remove a plugin's sandbox."""
        self._sandboxes.pop(plugin_name, None)

    def check_global_denial(self, action: str) -> bool:
        """Check if an action is globally denied.

        Args:
            action: The action to check

        Returns:
            True if globally denied
        """
        return action in self._global_denials

    def add_global_denial(self, action: str) -> None:
        """Globally deny an action for all plugins.

        Args:
            action: The action to deny
        """
        self._global_denials.add(action)
        logger.warning(f"Globally denied action: {action}")

    def remove_global_denial(self, action: str) -> None:
        """Remove a global denial.

        Args:
            action: The action to allow again
        """
        self._global_denials.discard(action)


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


def validate_path_permission(
    sandbox: PluginSandbox,
    path: str,
    mode: str = "read",
) -> None:
    """Validate filesystem permission for a path.

    Args:
        sandbox: The plugin's sandbox
        path: Path being accessed
        mode: Access mode ("read", "write", "delete")

    Raises:
        PermissionError: If access is not permitted
    """
    action = f"filesystem:{mode}"
    sandbox.require_permission(action, path)


def validate_network_permission(
    sandbox: PluginSandbox,
    host: str | None = None,
) -> None:
    """Validate network permission.

    Args:
        sandbox: The plugin's sandbox
        host: Optional target host

    Raises:
        PermissionError: If network access is not permitted
    """
    # Check if it's internal (localhost) or external
    if host and host in ("localhost", "127.0.0.1", "::1"):
        if sandbox.check_permission("network:internal", host):
            return
        if sandbox.check_permission("network", host):
            return
    else:
        if sandbox.check_permission("network:external", host):
            return
        if sandbox.check_permission("network", host):
            return

    raise PermissionError(
        plugin_name=sandbox.plugin_name,
        action="network",
        required_permission="network",
        target=host,
    )
