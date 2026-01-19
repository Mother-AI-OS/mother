"""Tool manifest schema for external tool repositories.

This module defines the schema for mother-tool.yaml files that describe
how an external tool repo integrates with Mother.

A tool manifest is distinct from a plugin manifest (mother-plugin.yaml):
- Tool manifest: Describes the external tool repo and how to install/run it
- Plugin manifest: Describes capabilities that get loaded into Mother's runtime

A tool repo may have both:
- mother-tool.yaml: For tool registry installation/management
- mother-plugin.yaml: For plugin capabilities (if it provides a Mother plugin)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ToolManifestError, ToolManifestNotFoundError

logger = logging.getLogger("mother.tools.manifest")

# Valid tool name pattern: lowercase alphanumeric with hyphens, 3-30 chars
TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,29}$")

# Manifest file names to search for
MANIFEST_FILENAMES = ["mother-tool.yaml", "mother-tool.yml"]


class RiskLevel(str, Enum):
    """Risk level for a tool."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IntegrationType(str, Enum):
    """How the tool integrates with Mother."""

    PYTHON = "python"  # Direct Python import
    CLI = "cli"  # CLI subprocess
    HTTP = "http"  # HTTP REST API
    DOCKER = "docker"  # Docker container


@dataclass
class PythonIntegration:
    """Python integration configuration."""

    module: str  # Python module path
    class_name: str | None = None  # Optional class name
    entrypoint: str | None = None  # Optional function name
    install_command: str | None = None  # pip install command


@dataclass
class CLIIntegration:
    """CLI integration configuration."""

    binary: str  # Binary name or path
    install_command: str | None = None  # How to install
    health_check: str | None = None  # Command to verify installation
    output_format: str = "text"  # Expected output format: text, json


@dataclass
class HTTPIntegration:
    """HTTP integration configuration."""

    base_url: str | None = None  # Default base URL
    port: int = 8000  # Default port
    health_endpoint: str = "/health"  # Health check endpoint
    start_command: str | None = None  # Command to start the service


@dataclass
class DockerIntegration:
    """Docker integration configuration."""

    image: str  # Docker image name
    tag: str = "latest"
    ports: dict[int, int] = field(default_factory=dict)  # host:container
    volumes: dict[str, str] = field(default_factory=dict)  # host:container
    environment: dict[str, str] = field(default_factory=dict)


@dataclass
class ToolMetadata:
    """Metadata about a tool."""

    name: str
    version: str
    description: str
    author: str | None = None
    homepage: str | None = None
    repository: str | None = None
    license: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    tags: list[str] = field(default_factory=list)


@dataclass
class IntegrationSpec:
    """Integration specification."""

    type: IntegrationType
    python: PythonIntegration | None = None
    cli: CLIIntegration | None = None
    http: HTTPIntegration | None = None
    docker: DockerIntegration | None = None


@dataclass
class ConfigField:
    """Configuration field that users can set."""

    name: str
    description: str
    type: str = "string"  # string, integer, boolean, path
    required: bool = False
    default: Any = None
    secret: bool = False  # If true, value should be stored securely


@dataclass
class ToolManifest:
    """Complete tool manifest."""

    schema_version: str
    tool: ToolMetadata
    integration: IntegrationSpec
    permissions: list[str] = field(default_factory=list)
    config: list[ConfigField] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        """Get the tool name."""
        return self.tool.name

    @property
    def version(self) -> str:
        """Get the tool version."""
        return self.tool.version

    @property
    def risk_level(self) -> RiskLevel:
        """Get the tool risk level."""
        return self.tool.risk_level

    def is_high_risk(self) -> bool:
        """Check if this tool is high-risk."""
        return self.tool.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def get_high_risk_permissions(self) -> list[str]:
        """Get list of high-risk permissions required by this tool."""
        high_risk = [
            "shell",
            "subprocess",
            "filesystem:write",
            "network:external",
            "secrets:write",
        ]
        return [p for p in self.permissions if any(h in p for h in high_risk)]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "schema_version": self.schema_version,
            "tool": {
                "name": self.tool.name,
                "version": self.tool.version,
                "description": self.tool.description,
                "author": self.tool.author,
                "homepage": self.tool.homepage,
                "repository": self.tool.repository,
                "license": self.tool.license,
                "risk_level": self.tool.risk_level.value,
                "tags": self.tool.tags,
            },
            "integration": {
                "type": self.integration.type.value,
                "python": _python_to_dict(self.integration.python),
                "cli": _cli_to_dict(self.integration.cli),
                "http": _http_to_dict(self.integration.http),
                "docker": _docker_to_dict(self.integration.docker),
            },
            "permissions": self.permissions,
            "config": [
                {
                    "name": c.name,
                    "description": c.description,
                    "type": c.type,
                    "required": c.required,
                    "default": c.default,
                    "secret": c.secret,
                }
                for c in self.config
            ],
            "dependencies": self.dependencies,
        }


def _python_to_dict(spec: PythonIntegration | None) -> dict | None:
    if not spec:
        return None
    return {
        "module": spec.module,
        "class_name": spec.class_name,
        "entrypoint": spec.entrypoint,
        "install_command": spec.install_command,
    }


def _cli_to_dict(spec: CLIIntegration | None) -> dict | None:
    if not spec:
        return None
    return {
        "binary": spec.binary,
        "install_command": spec.install_command,
        "health_check": spec.health_check,
        "output_format": spec.output_format,
    }


def _http_to_dict(spec: HTTPIntegration | None) -> dict | None:
    if not spec:
        return None
    return {
        "base_url": spec.base_url,
        "port": spec.port,
        "health_endpoint": spec.health_endpoint,
        "start_command": spec.start_command,
    }


def _docker_to_dict(spec: DockerIntegration | None) -> dict | None:
    if not spec:
        return None
    return {
        "image": spec.image,
        "tag": spec.tag,
        "ports": spec.ports,
        "volumes": spec.volumes,
        "environment": spec.environment,
    }


def validate_tool_name(name: str) -> bool:
    """Validate a tool name.

    Tool names must be:
    - Lowercase alphanumeric with hyphens
    - Start with a letter
    - 3-30 characters

    Args:
        name: Tool name to validate

    Returns:
        True if valid
    """
    return bool(TOOL_NAME_PATTERN.match(name))


def find_tool_manifest(directory: Path) -> Path | None:
    """Find a tool manifest file in a directory.

    Args:
        directory: Directory to search

    Returns:
        Path to manifest or None if not found
    """
    for filename in MANIFEST_FILENAMES:
        manifest_path = directory / filename
        if manifest_path.exists():
            return manifest_path
    return None


def load_tool_manifest(path: Path) -> ToolManifest:
    """Load and validate a tool manifest from a file.

    Args:
        path: Path to manifest file or directory containing manifest

    Returns:
        Validated ToolManifest

    Raises:
        ToolManifestNotFoundError: If manifest file not found
        ToolManifestError: If manifest is invalid
    """
    # If path is a directory, find the manifest
    if path.is_dir():
        manifest_path = find_tool_manifest(path)
        if not manifest_path:
            raise ToolManifestNotFoundError(str(path))
        path = manifest_path

    if not path.exists():
        raise ToolManifestNotFoundError(str(path))

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ToolManifestError("unknown", f"Invalid YAML: {e}")

    return validate_tool_manifest(data, path.parent.name)


def validate_tool_manifest(data: dict[str, Any], name_hint: str = "unknown") -> ToolManifest:
    """Validate tool manifest data and return a ToolManifest object.

    Args:
        data: Raw manifest data
        name_hint: Hint for tool name (used in error messages)

    Returns:
        Validated ToolManifest

    Raises:
        ToolManifestError: If validation fails
    """
    if not isinstance(data, dict):
        raise ToolManifestError(name_hint, "Manifest must be a dictionary")

    # Schema version
    schema_version = data.get("schema_version", "1.0")
    if not isinstance(schema_version, str):
        raise ToolManifestError(name_hint, "schema_version must be a string")

    # Tool metadata
    tool_data = data.get("tool")
    if not tool_data:
        raise ToolManifestError(name_hint, "Missing 'tool' section")

    try:
        tool = _parse_tool_metadata(tool_data, name_hint)
    except Exception as e:
        raise ToolManifestError(name_hint, f"Invalid tool metadata: {e}")

    # Integration
    integration_data = data.get("integration")
    if not integration_data:
        raise ToolManifestError(tool.name, "Missing 'integration' section")

    try:
        integration = _parse_integration(integration_data, tool.name)
    except Exception as e:
        raise ToolManifestError(tool.name, f"Invalid integration: {e}")

    # Permissions
    permissions = data.get("permissions", [])
    if not isinstance(permissions, list):
        raise ToolManifestError(tool.name, "permissions must be a list")

    # Config
    config_data = data.get("config", [])
    config = [_parse_config_field(c, tool.name) for c in config_data]

    # Dependencies
    dependencies = data.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ToolManifestError(tool.name, "dependencies must be a list")

    return ToolManifest(
        schema_version=schema_version,
        tool=tool,
        integration=integration,
        permissions=permissions,
        config=config,
        dependencies=dependencies,
    )


def _parse_tool_metadata(data: dict, name_hint: str) -> ToolMetadata:
    """Parse tool metadata section."""
    name = data.get("name")
    if not name:
        raise ValueError("Missing 'name' field")

    if not validate_tool_name(name):
        raise ValueError(
            f"Invalid tool name '{name}': must be lowercase alphanumeric "
            "with hyphens, 3-30 characters, starting with a letter"
        )

    version = data.get("version")
    if not version:
        raise ValueError("Missing 'version' field")

    description = data.get("description", "")

    risk_str = data.get("risk_level", "low").lower()
    try:
        risk_level = RiskLevel(risk_str)
    except ValueError:
        raise ValueError(f"Invalid risk_level: {risk_str}")

    return ToolMetadata(
        name=name,
        version=str(version),
        description=description,
        author=data.get("author"),
        homepage=data.get("homepage"),
        repository=data.get("repository"),
        license=data.get("license"),
        risk_level=risk_level,
        tags=data.get("tags", []),
    )


def _parse_integration(data: dict, tool_name: str) -> IntegrationSpec:
    """Parse integration section."""
    type_str = data.get("type")
    if not type_str:
        raise ValueError("Missing integration 'type'")

    try:
        integration_type = IntegrationType(type_str.lower())
    except ValueError:
        raise ValueError(f"Invalid integration type: {type_str}")

    python = None
    cli = None
    http = None
    docker = None

    if integration_type == IntegrationType.PYTHON:
        python_data = data.get("python", {})
        if not python_data.get("module"):
            raise ValueError("Python integration requires 'module' field")
        python = PythonIntegration(
            module=python_data["module"],
            class_name=python_data.get("class_name"),
            entrypoint=python_data.get("entrypoint"),
            install_command=python_data.get("install_command"),
        )

    elif integration_type == IntegrationType.CLI:
        cli_data = data.get("cli", {})
        if not cli_data.get("binary"):
            raise ValueError("CLI integration requires 'binary' field")
        cli = CLIIntegration(
            binary=cli_data["binary"],
            install_command=cli_data.get("install_command"),
            health_check=cli_data.get("health_check"),
            output_format=cli_data.get("output_format", "text"),
        )

    elif integration_type == IntegrationType.HTTP:
        http_data = data.get("http", {})
        http = HTTPIntegration(
            base_url=http_data.get("base_url"),
            port=http_data.get("port", 8000),
            health_endpoint=http_data.get("health_endpoint", "/health"),
            start_command=http_data.get("start_command"),
        )

    elif integration_type == IntegrationType.DOCKER:
        docker_data = data.get("docker", {})
        if not docker_data.get("image"):
            raise ValueError("Docker integration requires 'image' field")
        docker = DockerIntegration(
            image=docker_data["image"],
            tag=docker_data.get("tag", "latest"),
            ports=docker_data.get("ports", {}),
            volumes=docker_data.get("volumes", {}),
            environment=docker_data.get("environment", {}),
        )

    return IntegrationSpec(
        type=integration_type,
        python=python,
        cli=cli,
        http=http,
        docker=docker,
    )


def _parse_config_field(data: dict, tool_name: str) -> ConfigField:
    """Parse a config field."""
    name = data.get("name")
    if not name:
        raise ValueError("Config field missing 'name'")

    return ConfigField(
        name=name,
        description=data.get("description", ""),
        type=data.get("type", "string"),
        required=data.get("required", False),
        default=data.get("default"),
        secret=data.get("secret", False),
    )
