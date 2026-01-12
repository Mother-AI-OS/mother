"""Security sandbox for Mother plugins.

This module provides permission validation and resource isolation for plugin actions.

Features:
- Permission checking (v1)
- Resource limits (CPU, memory, time)
- Workspace isolation (restrict file operations to workspace)
- Integration with policy engine and audit logging

Permission format:
- Simple: "network", "secrets:read"
- Scoped: "filesystem:read:~/Documents", "filesystem:write:/tmp"
"""

from __future__ import annotations

import fnmatch
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .exceptions import PermissionError

logger = logging.getLogger("mother.plugins.sandbox")


# -----------------------------------------------------------------------------
# Sandbox Configuration
# -----------------------------------------------------------------------------


class ResourceLimits(BaseModel):
    """Resource limits for sandboxed execution.

    Attributes:
        max_cpu_seconds: Maximum CPU time in seconds
        max_memory_mb: Maximum memory usage in MB
        max_execution_time: Maximum wall-clock time in seconds
        max_file_size_mb: Maximum file size that can be written
        max_open_files: Maximum number of open file descriptors
        max_subprocess: Maximum number of subprocess calls
    """

    max_cpu_seconds: int = Field(default=60, description="Max CPU time")
    max_memory_mb: int = Field(default=512, description="Max memory in MB")
    max_execution_time: int = Field(default=300, description="Max wall-clock time")
    max_file_size_mb: int = Field(default=100, description="Max file size in MB")
    max_open_files: int = Field(default=100, description="Max open file descriptors")
    max_subprocess: int = Field(default=10, description="Max subprocess calls")


class WorkspaceConfig(BaseModel):
    """Workspace isolation configuration.

    Attributes:
        enabled: Whether workspace isolation is enabled
        workspace_dir: The workspace directory path
        allow_read_outside: Allow reading files outside workspace
        allowed_read_paths: Additional paths allowed for reading
        temp_dir: Temporary directory for plugin use
    """

    enabled: bool = Field(default=True, description="Enable workspace isolation")
    workspace_dir: Path = Field(
        default=Path("./workspace"),
        description="Workspace directory path",
    )
    allow_read_outside: bool = Field(
        default=True,
        description="Allow reading outside workspace",
    )
    allowed_read_paths: list[str] = Field(
        default_factory=list,
        description="Additional paths allowed for reading",
    )
    temp_dir: Path | None = Field(
        default=None,
        description="Temporary directory for plugin use",
    )

    def is_path_in_workspace(self, path: str | Path) -> bool:
        """Check if a path is within the workspace.

        Args:
            path: Path to check

        Returns:
            True if path is within workspace
        """
        try:
            check_path = Path(path).resolve()
            workspace = self.workspace_dir.resolve()
            return str(check_path).startswith(str(workspace) + os.sep) or check_path == workspace
        except Exception:
            return False

    def is_path_allowed_read(self, path: str | Path) -> bool:
        """Check if a path is allowed for reading.

        Args:
            path: Path to check

        Returns:
            True if reading is allowed
        """
        if not self.enabled:
            return True

        if self.is_path_in_workspace(path):
            return True

        if self.allow_read_outside:
            # Check against allowed read paths
            check_path = str(Path(path).resolve())
            for allowed in self.allowed_read_paths:
                allowed_path = str(Path(allowed).expanduser().resolve())
                if check_path.startswith(allowed_path):
                    return True
            return True  # Allow read outside by default

        return False

    def is_path_allowed_write(self, path: str | Path) -> bool:
        """Check if a path is allowed for writing.

        Args:
            path: Path to check

        Returns:
            True if writing is allowed
        """
        if not self.enabled:
            return True

        return self.is_path_in_workspace(path)


class SandboxConfig(BaseModel):
    """Complete sandbox configuration.

    Attributes:
        enabled: Whether sandboxing is enabled
        resource_limits: Resource limits for execution
        workspace: Workspace isolation configuration
        audit_all_actions: Log all sandbox actions
        enforce_permissions: Enforce permission checks
        allow_shell: Allow shell command execution
        allow_network: Allow network access
    """

    enabled: bool = Field(default=True, description="Enable sandboxing")
    resource_limits: ResourceLimits = Field(
        default_factory=ResourceLimits,
        description="Resource limits",
    )
    workspace: WorkspaceConfig = Field(
        default_factory=WorkspaceConfig,
        description="Workspace configuration",
    )
    audit_all_actions: bool = Field(
        default=True,
        description="Log all sandbox actions",
    )
    enforce_permissions: bool = Field(
        default=True,
        description="Enforce permission checks",
    )
    allow_shell: bool = Field(
        default=False,
        description="Allow shell command execution (dangerous)",
    )
    allow_network: bool = Field(
        default=True,
        description="Allow network access",
    )


# -----------------------------------------------------------------------------
# Execution Context
# -----------------------------------------------------------------------------


@dataclass
class ExecutionContext:
    """Context for tracking sandboxed execution.

    Tracks resource usage and enforces limits during execution.
    """

    plugin_name: str
    start_time: float = field(default_factory=time.time)
    subprocess_count: int = 0
    files_written: list[str] = field(default_factory=list)
    bytes_written: int = 0
    network_requests: int = 0

    def record_subprocess(self) -> None:
        """Record a subprocess call."""
        self.subprocess_count += 1

    def record_file_write(self, path: str, size: int) -> None:
        """Record a file write operation."""
        self.files_written.append(path)
        self.bytes_written += size

    def record_network_request(self) -> None:
        """Record a network request."""
        self.network_requests += 1

    def elapsed_time(self) -> float:
        """Get elapsed wall-clock time."""
        return time.time() - self.start_time

    def check_limits(self, limits: ResourceLimits) -> str | None:
        """Check if any limits have been exceeded.

        Returns:
            Error message if limit exceeded, None otherwise
        """
        if self.elapsed_time() > limits.max_execution_time:
            return f"Execution time exceeded ({limits.max_execution_time}s limit)"

        if self.subprocess_count > limits.max_subprocess:
            return f"Subprocess limit exceeded ({limits.max_subprocess} limit)"

        max_bytes = limits.max_file_size_mb * 1024 * 1024
        if self.bytes_written > max_bytes:
            return f"File write size exceeded ({limits.max_file_size_mb}MB limit)"

        return None


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
    def parse(cls, permission_str: str) -> Permission:
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

    def matches(self, required: Permission) -> bool:
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

    Validates permissions before allowing actions, with optional
    workspace isolation for write operations.
    """

    plugin_name: str
    granted_permissions: list[Permission] = field(default_factory=list)
    denied_actions: list[PermissionDenial] = field(default_factory=list)
    workspace_config: WorkspaceConfig | None = None

    # Audit logging
    audit_enabled: bool = True

    @classmethod
    def from_manifest_permissions(
        cls,
        plugin_name: str,
        permissions: list[str],
        workspace_config: WorkspaceConfig | None = None,
    ) -> PluginSandbox:
        """Create a sandbox from manifest permission strings.

        Args:
            plugin_name: Name of the plugin
            permissions: List of permission strings from manifest
            workspace_config: Optional workspace isolation config

        Returns:
            Configured sandbox instance
        """
        granted = [Permission.parse(p) for p in permissions]
        return cls(
            plugin_name=plugin_name,
            granted_permissions=granted,
            workspace_config=workspace_config,
        )

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
        # Check workspace restrictions for filesystem operations
        if self.workspace_config and target and action.startswith("filesystem:"):
            mode = action.split(":")[1] if ":" in action else "read"
            if mode == "read":
                if not self.workspace_config.is_path_allowed_read(target):
                    if self.audit_enabled:
                        logger.warning(
                            f"[{self.plugin_name}] Workspace denied: read {target}"
                        )
                    return False
            elif mode in ("write", "delete"):
                if not self.workspace_config.is_path_allowed_write(target):
                    if self.audit_enabled:
                        logger.warning(
                            f"[{self.plugin_name}] Workspace denied: {mode} {target}"
                        )
                    return False

        required = Permission(type=action, scope=target)

        for granted in self.granted_permissions:
            if granted.matches(required):
                if self.audit_enabled:
                    logger.debug(
                        f"[{self.plugin_name}] Permission granted: {action}" + (f" on {target}" if target else "")
                    )
                return True

        if self.audit_enabled:
            logger.warning(f"[{self.plugin_name}] Permission denied: {action}" + (f" on {target}" if target else ""))

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
    """Manages sandboxes for all loaded plugins.

    Provides centralized management of plugin sandboxes with:
    - Global configuration
    - Execution context tracking
    - Workspace isolation enforcement
    - Audit logging integration
    """

    def __init__(self, config: SandboxConfig | None = None):
        """Initialize the sandbox manager.

        Args:
            config: Global sandbox configuration
        """
        self.config = config or SandboxConfig()
        self._sandboxes: dict[str, PluginSandbox] = {}
        self._contexts: dict[str, ExecutionContext] = {}
        self._global_denials: set[str] = set()

        # Ensure workspace directory exists
        if self.config.workspace.enabled:
            self.config.workspace.workspace_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Sandbox workspace: {self.config.workspace.workspace_dir.resolve()}")

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
        sandbox = PluginSandbox.from_manifest_permissions(
            plugin_name,
            permissions,
            workspace_config=self.config.workspace if self.config.enabled else None,
        )
        self._sandboxes[plugin_name] = sandbox
        return sandbox

    def get_sandbox(self, plugin_name: str) -> PluginSandbox | None:
        """Get the sandbox for a plugin."""
        return self._sandboxes.get(plugin_name)

    def remove_sandbox(self, plugin_name: str) -> None:
        """Remove a plugin's sandbox."""
        self._sandboxes.pop(plugin_name, None)
        self._contexts.pop(plugin_name, None)

    def start_execution(self, plugin_name: str) -> ExecutionContext:
        """Start tracking execution for a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Execution context for tracking
        """
        context = ExecutionContext(plugin_name=plugin_name)
        self._contexts[plugin_name] = context
        return context

    def get_context(self, plugin_name: str) -> ExecutionContext | None:
        """Get the current execution context for a plugin."""
        return self._contexts.get(plugin_name)

    def end_execution(self, plugin_name: str) -> ExecutionContext | None:
        """End execution tracking for a plugin.

        Returns:
            Final execution context
        """
        return self._contexts.pop(plugin_name, None)

    def check_limits(self, plugin_name: str) -> str | None:
        """Check if plugin has exceeded any resource limits.

        Returns:
            Error message if limit exceeded, None otherwise
        """
        context = self._contexts.get(plugin_name)
        if not context:
            return None

        return context.check_limits(self.config.resource_limits)

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

    def validate_path_access(
        self,
        plugin_name: str,
        path: str,
        mode: str = "read",
    ) -> tuple[bool, str | None]:
        """Validate path access against workspace restrictions.

        Args:
            plugin_name: Plugin requesting access
            path: Path to validate
            mode: Access mode (read, write, delete)

        Returns:
            Tuple of (allowed, error_message)
        """
        if not self.config.enabled or not self.config.workspace.enabled:
            return True, None

        workspace = self.config.workspace

        if mode == "read":
            if workspace.is_path_allowed_read(path):
                return True, None
            return False, f"Read access denied: {path} is outside allowed paths"

        elif mode in ("write", "delete"):
            if workspace.is_path_allowed_write(path):
                return True, None
            return False, f"Write access denied: {path} is outside workspace"

        return False, f"Unknown access mode: {mode}"

    def validate_shell_access(self, plugin_name: str) -> tuple[bool, str | None]:
        """Validate shell command access.

        Returns:
            Tuple of (allowed, error_message)
        """
        if not self.config.enabled:
            return True, None

        if not self.config.allow_shell:
            return False, "Shell access is disabled in sandbox configuration"

        return True, None

    def validate_network_access(self, plugin_name: str) -> tuple[bool, str | None]:
        """Validate network access.

        Returns:
            Tuple of (allowed, error_message)
        """
        if not self.config.enabled:
            return True, None

        if not self.config.allow_network:
            return False, "Network access is disabled in sandbox configuration"

        return True, None


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
