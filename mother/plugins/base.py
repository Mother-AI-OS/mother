"""Plugin base classes for Mother AI OS.

This module defines the abstract base class that all plugins must implement,
along with the PluginResult dataclass for standardized execution results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .manifest import CapabilitySpec, PluginManifest


class ResultStatus(str, Enum):
    """Status of a plugin execution result."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PENDING_CONFIRMATION = "pending_confirmation"


@dataclass
class PluginResult:
    """Standardized result from plugin execution.

    Attributes:
        success: Whether the execution completed successfully
        status: Detailed status of the execution
        data: Structured output data from the execution
        raw_output: Raw string output (for CLI plugins)
        error_message: Human-readable error message if failed
        error_code: Machine-readable error code
        execution_time: Time taken to execute (seconds)
        timestamp: When the execution completed
        metadata: Additional metadata about the execution
    """

    success: bool
    status: ResultStatus = ResultStatus.SUCCESS
    data: dict[str, Any] | list[Any] | None = None
    raw_output: str | None = None
    error_message: str | None = None
    error_code: str | None = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(
        cls,
        data: dict[str, Any] | list[Any] | None = None,
        raw_output: str | None = None,
        execution_time: float = 0.0,
        **metadata: Any,
    ) -> "PluginResult":
        """Create a successful result."""
        return cls(
            success=True,
            status=ResultStatus.SUCCESS,
            data=data,
            raw_output=raw_output,
            execution_time=execution_time,
            metadata=metadata,
        )

    @classmethod
    def error_result(
        cls,
        message: str,
        code: str | None = None,
        raw_output: str | None = None,
        execution_time: float = 0.0,
        **metadata: Any,
    ) -> "PluginResult":
        """Create an error result."""
        return cls(
            success=False,
            status=ResultStatus.ERROR,
            error_message=message,
            error_code=code,
            raw_output=raw_output,
            execution_time=execution_time,
            metadata=metadata,
        )

    @classmethod
    def timeout_result(
        cls,
        timeout_seconds: int,
        raw_output: str | None = None,
    ) -> "PluginResult":
        """Create a timeout result."""
        return cls(
            success=False,
            status=ResultStatus.TIMEOUT,
            error_message=f"Execution timed out after {timeout_seconds} seconds",
            error_code="TIMEOUT",
            raw_output=raw_output,
            execution_time=float(timeout_seconds),
        )

    @classmethod
    def pending_confirmation(
        cls,
        action_description: str,
        params: dict[str, Any],
        **metadata: Any,
    ) -> "PluginResult":
        """Create a result requiring user confirmation."""
        return cls(
            success=True,  # Not an error, just needs confirmation
            status=ResultStatus.PENDING_CONFIRMATION,
            data={
                "action": action_description,
                "params": params,
            },
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "status": self.status.value,
            "data": self.data,
            "raw_output": self.raw_output,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        if self.success:
            if self.status == ResultStatus.PENDING_CONFIRMATION:
                return f"[PENDING] {self.data.get('action', 'Action requires confirmation')}"
            return f"[OK] {self.data or self.raw_output or 'Success'}"
        return f"[{self.status.value.upper()}] {self.error_message or 'Unknown error'}"


@dataclass
class PluginInfo:
    """Information about a discovered plugin."""

    name: str
    version: str
    description: str
    author: str
    source: str  # Where the plugin was loaded from
    capabilities: list[str]  # List of capability names
    license: str | None = None
    loaded: bool = False
    error: str | None = None

    @classmethod
    def from_manifest(cls, manifest: "PluginManifest", source: str) -> "PluginInfo":
        """Create PluginInfo from a manifest."""
        return cls(
            name=manifest.plugin.name,
            version=manifest.plugin.version,
            description=manifest.plugin.description,
            author=manifest.plugin.author,
            source=source,
            capabilities=[cap.name for cap in manifest.capabilities],
            license=manifest.plugin.license,
            loaded=True,
        )

    @classmethod
    def failed(cls, name: str, source: str, error: str) -> "PluginInfo":
        """Create PluginInfo for a plugin that failed to load."""
        return cls(
            name=name,
            version="unknown",
            description="",
            author="unknown",
            source=source,
            capabilities=[],
            license=None,
            loaded=False,
            error=error,
        )


class PluginBase(ABC):
    """Abstract base class for all Mother plugins.

    Plugins must implement the execute() method and provide a manifest
    describing their capabilities.

    Example:
        class MyPlugin(PluginBase):
            @property
            def manifest(self) -> PluginManifest:
                return self._manifest

            async def execute(
                self,
                capability: str,
                params: dict[str, Any],
            ) -> PluginResult:
                if capability == "do_something":
                    return await self._do_something(**params)
                raise CapabilityNotFoundError(capability, self.name)
    """

    def __init__(self, manifest: "PluginManifest", config: dict[str, Any] | None = None):
        """Initialize the plugin.

        Args:
            manifest: The plugin's manifest
            config: Plugin-specific configuration values
        """
        self._manifest = manifest
        self._config = config or {}

    @property
    def manifest(self) -> "PluginManifest":
        """Get the plugin manifest."""
        return self._manifest

    @property
    def name(self) -> str:
        """Get the plugin name."""
        return self._manifest.plugin.name

    @property
    def version(self) -> str:
        """Get the plugin version."""
        return self._manifest.plugin.version

    @property
    def config(self) -> dict[str, Any]:
        """Get the plugin configuration."""
        return self._config

    def get_capabilities(self) -> list["CapabilitySpec"]:
        """Get all capability specifications."""
        return self._manifest.capabilities

    def get_capability(self, name: str) -> "CapabilitySpec | None":
        """Get a specific capability by name."""
        return self._manifest.get_capability(name)

    def has_capability(self, name: str) -> bool:
        """Check if plugin has a specific capability."""
        return self.get_capability(name) is not None

    def get_anthropic_schemas(self) -> list[dict[str, Any]]:
        """Get all capabilities as Anthropic tool_use schemas."""
        return self._manifest.get_all_anthropic_schemas()

    def requires_confirmation(self, capability: str) -> bool:
        """Check if a capability requires user confirmation."""
        cap = self.get_capability(capability)
        return cap.confirmation_required if cap else False

    @abstractmethod
    async def execute(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> PluginResult:
        """Execute a capability with the given parameters.

        Args:
            capability: Name of the capability to execute
            params: Parameters for the capability

        Returns:
            PluginResult with execution outcome

        Raises:
            CapabilityNotFoundError: If capability doesn't exist
            PluginValidationError: If params are invalid
            ExecutionError: If execution fails
        """
        ...

    async def initialize(self) -> None:
        """Called when the plugin is loaded.

        Override this method to perform initialization tasks like
        connecting to services, loading resources, etc.
        """
        pass

    async def shutdown(self) -> None:
        """Called when the plugin is unloaded.

        Override this method to perform cleanup tasks like
        closing connections, saving state, etc.
        """
        pass

    def validate_params(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> list[str]:
        """Validate parameters for a capability.

        Args:
            capability: Name of the capability
            params: Parameters to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        cap = self.get_capability(capability)
        if not cap:
            return [f"Unknown capability: {capability}"]

        errors = []
        provided_params = set(params.keys())

        for param_spec in cap.parameters:
            if param_spec.required and param_spec.name not in provided_params:
                errors.append(f"Missing required parameter: {param_spec.name}")

            if param_spec.name in params:
                value = params[param_spec.name]

                # Type validation
                if param_spec.type.value == "string" and not isinstance(value, str):
                    errors.append(f"Parameter '{param_spec.name}' must be a string")
                elif param_spec.type.value == "integer" and not isinstance(value, int):
                    errors.append(f"Parameter '{param_spec.name}' must be an integer")
                elif param_spec.type.value == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Parameter '{param_spec.name}' must be a number")
                elif param_spec.type.value == "boolean" and not isinstance(value, bool):
                    errors.append(f"Parameter '{param_spec.name}' must be a boolean")
                elif param_spec.type.value == "array" and not isinstance(value, list):
                    errors.append(f"Parameter '{param_spec.name}' must be an array")
                elif param_spec.type.value == "object" and not isinstance(value, dict):
                    errors.append(f"Parameter '{param_spec.name}' must be an object")

                # Choices validation
                if param_spec.choices and value not in param_spec.choices:
                    errors.append(
                        f"Parameter '{param_spec.name}' must be one of: {', '.join(param_spec.choices)}"
                    )

        return errors

    def __repr__(self) -> str:
        """String representation of the plugin."""
        return f"<Plugin {self.name}@{self.version}>"
