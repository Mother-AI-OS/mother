"""Exceptions for the external tools system.

These exceptions are specific to managing external tool repositories,
distinct from plugin exceptions in mother.plugins.exceptions.
"""

from __future__ import annotations


class ToolError(Exception):
    """Base exception for tool system errors."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ToolNotFoundError(ToolError):
    """Raised when a tool cannot be found."""

    def __init__(self, name: str, source: str | None = None):
        self.name = name
        self.source = source
        msg = f"Tool '{name}' not found"
        if source:
            msg += f" in {source}"
        super().__init__(msg)


class ToolManifestError(ToolError):
    """Raised when a tool manifest is invalid."""

    def __init__(self, name: str, reason: str):
        self.name = name
        self.reason = reason
        super().__init__(f"Invalid manifest for '{name}': {reason}")


class ToolManifestNotFoundError(ToolError):
    """Raised when a tool manifest file cannot be found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Tool manifest not found at: {path}")


class ToolAlreadyInstalledError(ToolError):
    """Raised when trying to install an already installed tool."""

    def __init__(self, name: str, version: str | None = None):
        self.name = name
        self.version = version
        msg = f"Tool '{name}' is already installed"
        if version:
            msg += f" (version {version})"
        super().__init__(msg)


class ToolNotInstalledError(ToolError):
    """Raised when trying to operate on a tool that isn't installed."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Tool '{name}' is not installed")


class ToolInstallError(ToolError):
    """Raised when tool installation fails."""

    def __init__(self, name: str, reason: str):
        self.name = name
        self.reason = reason
        super().__init__(f"Failed to install '{name}': {reason}")


class ToolValidationError(ToolError):
    """Raised when tool validation fails."""

    def __init__(self, name: str, errors: list[str]):
        self.name = name
        self.errors = errors
        error_str = "; ".join(errors)
        super().__init__(f"Validation failed for '{name}': {error_str}")


class ToolPolicyViolationError(ToolError):
    """Raised when a tool operation violates policy."""

    def __init__(
        self,
        name: str,
        operation: str,
        reason: str,
        risk_level: str | None = None,
    ):
        self.name = name
        self.operation = operation
        self.reason = reason
        self.risk_level = risk_level
        msg = f"Policy violation for '{name}' ({operation}): {reason}"
        if risk_level:
            msg += f" [Risk: {risk_level}]"
        super().__init__(msg)


class CatalogError(ToolError):
    """Raised when there's an issue with the tool catalog."""

    def __init__(self, reason: str):
        super().__init__(f"Catalog error: {reason}")
