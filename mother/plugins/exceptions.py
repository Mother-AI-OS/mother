"""Plugin system exceptions for Mother AI OS."""

from typing import Any


class PluginError(Exception):
    """Base exception for all plugin-related errors."""

    def __init__(self, message: str, plugin_name: str | None = None):
        self.plugin_name = plugin_name
        self.message = message
        super().__init__(f"[{plugin_name}] {message}" if plugin_name else message)


class PluginNotFoundError(PluginError):
    """Raised when a plugin cannot be found."""

    def __init__(self, plugin_name: str, searched_locations: list[str] | None = None):
        self.searched_locations = searched_locations or []
        locations_str = ", ".join(self.searched_locations) if self.searched_locations else "default locations"
        super().__init__(f"Plugin not found in: {locations_str}", plugin_name)


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""

    def __init__(self, plugin_name: str, reason: str, cause: Exception | None = None):
        self.reason = reason
        self.cause = cause
        super().__init__(f"Failed to load: {reason}", plugin_name)


class ManifestError(PluginError):
    """Raised when a plugin manifest is invalid."""

    def __init__(self, plugin_name: str, errors: list[str] | str):
        self.errors = [errors] if isinstance(errors, str) else errors
        errors_str = "; ".join(self.errors)
        super().__init__(f"Invalid manifest: {errors_str}", plugin_name)


class ManifestNotFoundError(ManifestError):
    """Raised when a plugin manifest file cannot be found."""

    def __init__(self, plugin_name: str, manifest_path: str):
        self.manifest_path = manifest_path
        super().__init__(plugin_name, f"Manifest not found at {manifest_path}")


class DependencyError(PluginError):
    """Raised when plugin dependencies cannot be satisfied."""

    def __init__(
        self,
        plugin_name: str,
        missing: list[str] | None = None,
        incompatible: list[tuple[str, str, str]] | None = None,
    ):
        self.missing = missing or []
        self.incompatible = incompatible or []

        parts = []
        if self.missing:
            parts.append(f"missing: {', '.join(self.missing)}")
        if self.incompatible:
            incompat_strs = [f"{pkg} (have {have}, need {need})" for pkg, have, need in self.incompatible]
            parts.append(f"incompatible: {', '.join(incompat_strs)}")

        super().__init__(f"Dependency error: {'; '.join(parts)}", plugin_name)


class CapabilityNotFoundError(PluginError):
    """Raised when a requested capability is not found."""

    def __init__(self, capability_name: str, plugin_name: str | None = None):
        self.capability_name = capability_name
        super().__init__(f"Capability '{capability_name}' not found", plugin_name)


class ExecutionError(PluginError):
    """Raised when plugin execution fails."""

    def __init__(
        self,
        plugin_name: str,
        capability: str,
        reason: str,
        exit_code: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
    ):
        self.capability = capability
        self.reason = reason
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Execution of '{capability}' failed: {reason}", plugin_name)


class PermissionError(PluginError):
    """Raised when a plugin attempts an unauthorized action."""

    def __init__(
        self,
        plugin_name: str,
        action: str,
        required_permission: str,
        target: str | None = None,
    ):
        self.action = action
        self.required_permission = required_permission
        self.target = target
        target_str = f" on '{target}'" if target else ""
        super().__init__(
            f"Permission denied for '{action}'{target_str}. Required: {required_permission}",
            plugin_name,
        )


class ConfigurationError(PluginError):
    """Raised when plugin configuration is invalid or missing."""

    def __init__(self, plugin_name: str, field: str, reason: str):
        self.field = field
        self.reason = reason
        super().__init__(f"Configuration error for '{field}': {reason}", plugin_name)


class PluginTimeoutError(PluginError):
    """Raised when plugin execution times out."""

    def __init__(self, plugin_name: str, capability: str, timeout_seconds: int):
        self.capability = capability
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Execution of '{capability}' timed out after {timeout_seconds}s",
            plugin_name,
        )


class PluginValidationError(PluginError):
    """Raised when plugin input/output validation fails."""

    def __init__(
        self,
        plugin_name: str,
        capability: str,
        validation_errors: list[dict[str, Any]],
        stage: str = "input",
    ):
        self.capability = capability
        self.validation_errors = validation_errors
        self.stage = stage
        errors_str = "; ".join(str(e) for e in validation_errors)
        super().__init__(
            f"Validation failed for '{capability}' {stage}: {errors_str}",
            plugin_name,
        )


class PolicyViolationError(PluginError):
    """Raised when a capability call violates security policy.

    This is a HARD block - the action cannot proceed regardless of
    user confirmation. Policy violations are always logged.
    """

    def __init__(
        self,
        plugin_name: str,
        capability: str,
        reason: str,
        matched_rules: list[str] | None = None,
        risk_tier: str = "MEDIUM",
    ):
        self.capability = capability
        self.reason = reason
        self.matched_rules = matched_rules or []
        self.risk_tier = risk_tier
        super().__init__(
            f"Policy violation for '{capability}': {reason}",
            plugin_name,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "error": "policy_violation",
            "plugin": self.plugin_name,
            "capability": self.capability,
            "reason": self.reason,
            "matched_rules": self.matched_rules,
            "risk_tier": self.risk_tier,
        }
