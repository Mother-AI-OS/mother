"""Plugin manifest schema and loader for Mother AI OS.

This module defines the Pydantic models for plugin manifests and provides
utilities for loading and validating them from YAML files.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from .exceptions import ManifestError, ManifestNotFoundError

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class ParameterType(str, Enum):
    """Supported parameter types for plugin capabilities."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ExecutionType(str, Enum):
    """Supported execution backends for plugins."""

    PYTHON = "python"
    CLI = "cli"
    DOCKER = "docker"
    HTTP = "http"


# -----------------------------------------------------------------------------
# Parameter & Capability Models
# -----------------------------------------------------------------------------


class ParameterSpec(BaseModel):
    """Specification for a capability parameter."""

    name: str = Field(..., description="Parameter name")
    type: ParameterType = Field(..., description="Parameter type")
    description: str = Field(default="", description="Human-readable description")
    required: bool = Field(default=False, description="Whether parameter is required")
    default: Any = Field(default=None, description="Default value if not provided")
    choices: list[str] | None = Field(default=None, description="Allowed values for enum-like params")

    # For array type
    items_type: ParameterType | None = Field(default=None, description="Type of array items")

    # For object type
    properties: dict[str, dict[str, Any]] | None = Field(default=None, description="Object property definitions")

    # CLI-specific
    flag: str | None = Field(default=None, description="CLI flag (e.g., '--output')")
    positional: bool = Field(default=False, description="Whether this is a positional CLI argument")

    def to_json_schema(self) -> dict[str, Any]:
        """Convert parameter to JSON Schema format for Anthropic tool_use."""
        schema: dict[str, Any] = {"description": self.description or self.name}

        if self.type == ParameterType.STRING:
            schema["type"] = "string"
            if self.choices:
                schema["enum"] = self.choices
        elif self.type == ParameterType.INTEGER:
            schema["type"] = "integer"
        elif self.type == ParameterType.NUMBER:
            schema["type"] = "number"
        elif self.type == ParameterType.BOOLEAN:
            schema["type"] = "boolean"
        elif self.type == ParameterType.ARRAY:
            schema["type"] = "array"
            if self.items_type:
                schema["items"] = {"type": self.items_type.value}
        elif self.type == ParameterType.OBJECT:
            schema["type"] = "object"
            if self.properties:
                schema["properties"] = self.properties

        if self.default is not None:
            schema["default"] = self.default

        return schema


class ReturnSpec(BaseModel):
    """Specification for capability return value."""

    type: ParameterType = Field(..., description="Return type")
    description: str = Field(default="", description="Description of return value")
    properties: dict[str, dict[str, Any]] | None = Field(default=None, description="Object properties if type=object")


class ExampleSpec(BaseModel):
    """Example input/output for a capability."""

    description: str = Field(default="", description="What this example demonstrates")
    input: dict[str, Any] = Field(..., description="Example input parameters")
    output: dict[str, Any] | None = Field(default=None, description="Expected output")


class CapabilitySpec(BaseModel):
    """Specification for a plugin capability (action it can perform)."""

    name: str = Field(..., description="Capability identifier (e.g., 'send_email')")
    description: str = Field(..., description="Human-readable description for LLM")
    parameters: list[ParameterSpec] = Field(default_factory=list, description="Input parameters")
    returns: ReturnSpec | None = Field(default=None, description="Return value specification")
    examples: list[ExampleSpec] = Field(default_factory=list, description="Usage examples")
    confirmation_required: bool = Field(default=False, description="Require user confirmation before execution")
    timeout: int | None = Field(default=None, description="Override default timeout (seconds)")

    def to_anthropic_schema(self, plugin_name: str) -> dict[str, Any]:
        """Convert capability to Anthropic tool_use schema format.

        Args:
            plugin_name: Name of the parent plugin (used for tool naming)

        Returns:
            Dict in Anthropic tool_use format
        """
        # Tool name format: plugin_capability (e.g., mailcraft_send_email)
        tool_name = f"{plugin_name}_{self.name}"

        # Build properties from parameters
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        schema: dict[str, Any] = {
            "name": tool_name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
            },
        }

        if required:
            schema["input_schema"]["required"] = required

        return schema


# -----------------------------------------------------------------------------
# Execution Models
# -----------------------------------------------------------------------------


class PythonExecutionSpec(BaseModel):
    """Configuration for Python execution backend."""

    module: str = Field(..., description="Python module path (e.g., 'my_plugin.tool')")
    class_name: str = Field(..., alias="class", description="Class name in module")


class CLIExecutionSpec(BaseModel):
    """Configuration for CLI execution backend."""

    binary: str = Field(..., description="Path to executable or command name")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    cwd: str | None = Field(default=None, description="Working directory")
    shell: bool = Field(default=False, description="Run via shell")


class DockerExecutionSpec(BaseModel):
    """Configuration for Docker execution backend."""

    image: str = Field(..., description="Docker image (e.g., 'lawkraft/plugin:1.0')")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    volumes: dict[str, str] = Field(default_factory=dict, description="Volume mounts")
    network: str = Field(default="none", description="Network mode")


class HTTPExecutionSpec(BaseModel):
    """Configuration for HTTP execution backend."""

    base_url: str = Field(..., description="Base URL for API")
    headers: dict[str, str] = Field(default_factory=dict, description="Default headers")
    auth_type: Literal["none", "bearer", "basic", "api_key"] = Field(default="none")
    auth_env_var: str | None = Field(default=None, description="Env var containing auth token")


class ExecutionSpec(BaseModel):
    """Execution configuration for a plugin."""

    type: ExecutionType = Field(..., description="Execution backend type")
    python: PythonExecutionSpec | None = Field(default=None)
    cli: CLIExecutionSpec | None = Field(default=None)
    docker: DockerExecutionSpec | None = Field(default=None)
    http: HTTPExecutionSpec | None = Field(default=None)

    @model_validator(mode="after")
    def validate_execution_config(self) -> ExecutionSpec:
        """Ensure the correct execution config is provided for the type."""
        type_to_field = {
            ExecutionType.PYTHON: self.python,
            ExecutionType.CLI: self.cli,
            ExecutionType.DOCKER: self.docker,
            ExecutionType.HTTP: self.http,
        }

        config = type_to_field.get(self.type)
        if config is None:
            raise ValueError(f"Missing '{self.type.value}' configuration for execution type '{self.type.value}'")

        return self


# -----------------------------------------------------------------------------
# Configuration Models
# -----------------------------------------------------------------------------


class ConfigField(BaseModel):
    """Configuration field definition for plugin settings."""

    type: Literal["string", "integer", "boolean", "array"] = Field(..., description="Field type")
    description: str = Field(default="", description="Human-readable description")
    required: bool = Field(default=False, description="Whether field is required")
    default: Any = Field(default=None, description="Default value")
    sensitive: bool = Field(default=False, description="Whether to mask in logs/UI")
    choices: list[str] | None = Field(default=None, description="Allowed values")
    env_var: str | None = Field(default=None, description="Override environment variable name")


# -----------------------------------------------------------------------------
# Main Manifest Model
# -----------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """Plugin risk levels for security classification."""

    LOW = "low"  # Safe operations, no external access
    MEDIUM = "medium"  # Limited external access, read-only operations
    HIGH = "high"  # Write operations, network access, external services
    CRITICAL = "critical"  # Shell execution, system access, credential handling


# Permissions that indicate high-risk operations
HIGH_RISK_PERMISSIONS = frozenset(
    {
        "shell",  # Shell command execution
        "subprocess",  # Subprocess spawning
        "filesystem:write",  # Write to filesystem
        "filesystem:delete",  # Delete files
        "secrets:write",  # Write secrets
        "secrets:read",  # Read secrets (credential access)
        "network:external",  # External network access
    }
)


class PluginMetadata(BaseModel):
    """Plugin metadata section of manifest."""

    name: str = Field(..., description="Plugin identifier (lowercase, alphanumeric, hyphens)")
    version: str = Field(..., description="Semantic version (e.g., '1.0.0')")
    description: str = Field(..., description="Short description for users")
    author: str = Field(..., description="Author name or organization")
    license: str = Field(default="MIT", description="License identifier")
    homepage: str | None = Field(default=None, description="Project homepage URL")
    repository: str | None = Field(default=None, description="Source code repository URL")

    requires_python: str = Field(default=">=3.11", description="Python version requirement")
    requires_mother: str = Field(default=">=1.0.0", description="Mother version requirement")

    # Security settings
    risk_level: RiskLevel = Field(
        default=RiskLevel.MEDIUM,
        description="Security risk level of the plugin",
    )
    disabled_by_default: bool = Field(
        default=False,
        description="If True, plugin must be explicitly enabled",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate plugin name format."""
        if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$|^[a-z]$", v):
            raise ValueError("Plugin name must be lowercase alphanumeric with hyphens, starting with a letter")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate semantic version format."""
        if not re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$", v):
            raise ValueError("Version must follow semantic versioning (e.g., '1.0.0', '1.0.0-beta.1')")
        return v


class PluginManifest(BaseModel):
    """Complete plugin manifest specification.

    This is the top-level model representing a mother-plugin.yaml file.
    """

    schema_version: str = Field(default="1.0", description="Manifest schema version")

    # Plugin metadata (nested under 'plugin' key in YAML)
    plugin: PluginMetadata = Field(..., description="Plugin metadata")

    # Dependencies
    dependencies: list[str] = Field(default_factory=list, description="Python package dependencies")

    # Capabilities (what the plugin can do)
    capabilities: list[CapabilitySpec] = Field(..., min_length=1, description="Plugin capabilities")

    # Execution configuration
    execution: ExecutionSpec = Field(..., description="How to execute the plugin")

    # Permissions required
    permissions: list[str] = Field(default_factory=list, description="Required permissions")

    # Configuration schema
    config: dict[str, ConfigField] = Field(default_factory=dict, description="Configuration fields")

    @property
    def name(self) -> str:
        """Convenience accessor for plugin name."""
        return self.plugin.name

    @property
    def version(self) -> str:
        """Convenience accessor for plugin version."""
        return self.plugin.version

    def get_capability(self, name: str) -> CapabilitySpec | None:
        """Get a capability by name."""
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        return None

    def get_all_anthropic_schemas(self) -> list[dict[str, Any]]:
        """Get all capabilities as Anthropic tool_use schemas."""
        return [cap.to_anthropic_schema(self.plugin.name) for cap in self.capabilities]

    def get_required_config(self) -> list[str]:
        """Get list of required configuration field names."""
        return [name for name, field in self.config.items() if field.required]

    def get_high_risk_permissions(self) -> list[str]:
        """Get list of high-risk permissions this plugin requires.

        Returns:
            List of permission strings that are considered high-risk
        """
        return [p for p in self.permissions if p in HIGH_RISK_PERMISSIONS]

    def has_high_risk_permissions(self) -> bool:
        """Check if the plugin has any high-risk permissions.

        Returns:
            True if the plugin has any high-risk permissions
        """
        return len(self.get_high_risk_permissions()) > 0

    def is_disabled_by_default(self) -> bool:
        """Check if plugin should be disabled by default.

        A plugin is disabled by default if:
        - It explicitly sets disabled_by_default=True in manifest
        - It has a risk_level of HIGH or CRITICAL
        - It requests any high-risk permissions

        Returns:
            True if the plugin should be disabled by default
        """
        # Explicit setting takes precedence
        if self.plugin.disabled_by_default:
            return True

        # High/Critical risk level
        if self.plugin.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return True

        # High-risk permissions
        if self.has_high_risk_permissions():
            return True

        return False


# -----------------------------------------------------------------------------
# Manifest Loading
# -----------------------------------------------------------------------------


def load_manifest(path: Path | str) -> PluginManifest:
    """Load and validate a plugin manifest from a YAML file.

    Args:
        path: Path to the manifest file (mother-plugin.yaml or manifest.yaml)

    Returns:
        Validated PluginManifest instance

    Raises:
        ManifestNotFoundError: If the manifest file doesn't exist
        ManifestError: If the manifest is invalid
    """
    path = Path(path)

    if not path.exists():
        raise ManifestNotFoundError(
            plugin_name=path.parent.name,
            manifest_path=str(path),
        )

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ManifestError(
            plugin_name=path.parent.name,
            errors=f"Invalid YAML: {e}",
        )

    if not isinstance(data, dict):
        raise ManifestError(
            plugin_name=path.parent.name,
            errors="Manifest must be a YAML mapping",
        )

    try:
        return PluginManifest.model_validate(data)
    except Exception as e:
        raise ManifestError(
            plugin_name=data.get("plugin", {}).get("name", path.parent.name),
            errors=str(e),
        )


def find_manifest(plugin_dir: Path) -> Path | None:
    """Find a manifest file in a plugin directory.

    Searches for:
    1. mother-plugin.yaml (preferred)
    2. manifest.yaml (fallback)
    3. plugin.yaml (fallback)

    Args:
        plugin_dir: Directory to search

    Returns:
        Path to manifest file, or None if not found
    """
    candidates = ["mother-plugin.yaml", "manifest.yaml", "plugin.yaml"]

    for name in candidates:
        path = plugin_dir / name
        if path.exists():
            return path

    return None
