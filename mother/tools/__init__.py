"""Tools module - CLI wrappers and external tool management.

This module provides:
- Legacy ToolWrapper for CLI tool wrapping (deprecated, use plugins)
- ToolRegistry for plugin-based tool management
- External tool manifest schema for tool repo integration
- ExternalToolRegistry for managing external tool repo installations

External Tools:
    The tool manifest system (mother-tool.yaml) allows external tool repos
    to integrate with Mother. Use ExternalToolRegistry to install and manage
    external tools. See mother.tools.tool_manifest for schema details.
"""

from .base import ToolParameter, ToolResult, ToolWrapper
from .catalog import CatalogEntry, ToolCatalog
from .exceptions import (
    CatalogError,
    ToolAlreadyInstalledError,
    ToolError,
    ToolInstallError,
    ToolManifestError,
    ToolManifestNotFoundError,
    ToolNotFoundError,
    ToolNotInstalledError,
    ToolPolicyViolationError,
    ToolValidationError,
)
from .external_registry import ExternalToolRegistry, InstallSource, ToolInfo, ToolStatus
from .policy import (
    ToolPolicyAction,
    ToolPolicyConfig,
    ToolPolicyDecision,
    ToolPolicyEngine,
    get_tool_policy_engine,
    load_tool_policy,
    reload_tool_policy,
)
from .registry import ToolRegistry
from .store import InstalledTool, ToolStore
from .tool_manifest import (
    CLIIntegration,
    ConfigField,
    DockerIntegration,
    HTTPIntegration,
    IntegrationSpec,
    IntegrationType,
    PythonIntegration,
    RiskLevel,
    ToolManifest,
    ToolMetadata,
    find_tool_manifest,
    load_tool_manifest,
    validate_tool_manifest,
    validate_tool_name,
)

__all__ = [
    # Legacy (deprecated)
    "ToolWrapper",
    "ToolResult",
    "ToolParameter",
    # Plugin-based registry
    "ToolRegistry",
    # External tool registry
    "ExternalToolRegistry",
    "ToolStore",
    "InstalledTool",
    "ToolCatalog",
    "CatalogEntry",
    "ToolInfo",
    "ToolStatus",
    "InstallSource",
    # External tool manifest
    "ToolManifest",
    "ToolMetadata",
    "IntegrationSpec",
    "IntegrationType",
    "PythonIntegration",
    "CLIIntegration",
    "HTTPIntegration",
    "DockerIntegration",
    "ConfigField",
    "RiskLevel",
    "load_tool_manifest",
    "find_tool_manifest",
    "validate_tool_manifest",
    "validate_tool_name",
    # Policy
    "ToolPolicyAction",
    "ToolPolicyConfig",
    "ToolPolicyDecision",
    "ToolPolicyEngine",
    "get_tool_policy_engine",
    "load_tool_policy",
    "reload_tool_policy",
    # Exceptions
    "ToolError",
    "ToolNotFoundError",
    "ToolManifestError",
    "ToolManifestNotFoundError",
    "ToolAlreadyInstalledError",
    "ToolNotInstalledError",
    "ToolInstallError",
    "ToolValidationError",
    "ToolPolicyViolationError",
    "CatalogError",
]
