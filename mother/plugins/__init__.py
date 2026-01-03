"""Mother AI OS Plugin System.

This module provides the main entry point for the plugin system,
combining discovery, loading, registration, and execution.

Example usage:
    from mother.plugins import PluginManager, PluginConfig

    config = PluginConfig()
    manager = PluginManager(config)

    # Discover and load all plugins
    await manager.initialize()

    # Execute a capability
    result = await manager.execute("mailcraft_send_email", {
        "to": "user@example.com",
        "subject": "Hello",
        "body": "World"
    })

    # Get all schemas for Claude
    schemas = manager.get_all_schemas()
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import PluginBase, PluginInfo, PluginResult, ResultStatus
from .exceptions import (
    CapabilityNotFoundError,
    ConfigurationError,
    DependencyError,
    ExecutionError,
    ManifestError,
    ManifestNotFoundError,
    PermissionError,
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginTimeoutError,
    PluginValidationError,
)
from .executor import CLIExecutor, ExecutorBase, PythonExecutor, create_executor
from .loader import PluginLoader
from .manifest import (
    CapabilitySpec,
    ConfigField,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    PluginManifest,
    PluginMetadata,
    find_manifest,
    load_manifest,
)
from .registry import CapabilityEntry, PluginRegistry
from .sandbox import Permission, PluginSandbox, SandboxManager

logger = logging.getLogger("mother.plugins")

# Public exports
__all__ = [
    # Main classes
    "PluginManager",
    "PluginConfig",
    # Base classes
    "PluginBase",
    "PluginResult",
    "PluginInfo",
    "ResultStatus",
    # Manifest
    "PluginManifest",
    "PluginMetadata",
    "CapabilitySpec",
    "ParameterSpec",
    "ConfigField",
    "ExecutionSpec",
    "ExecutionType",
    "load_manifest",
    "find_manifest",
    # Registry
    "PluginRegistry",
    "CapabilityEntry",
    # Loader
    "PluginLoader",
    # Executor
    "ExecutorBase",
    "PythonExecutor",
    "CLIExecutor",
    "create_executor",
    # Sandbox
    "PluginSandbox",
    "SandboxManager",
    "Permission",
    # Exceptions
    "PluginError",
    "PluginNotFoundError",
    "PluginLoadError",
    "ManifestError",
    "ManifestNotFoundError",
    "DependencyError",
    "CapabilityNotFoundError",
    "ExecutionError",
    "PermissionError",
    "ConfigurationError",
    "PluginTimeoutError",
    "PluginValidationError",
]


@dataclass
class PluginConfig:
    """Configuration for the plugin system."""

    # Enable/disable plugin system
    enabled: bool = True

    # Plugin directories
    user_plugins_dir: Path = field(default_factory=lambda: Path.home() / ".mother" / "plugins")
    project_plugins_dir: Path | None = None
    builtin_plugins_dir: Path | None = None

    # Plugin management
    disabled_plugins: list[str] = field(default_factory=list)
    enabled_plugins: list[str] | None = None  # If set, only load these

    # Plugin-specific settings (plugin_name -> settings dict)
    plugin_settings: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Security
    require_permissions: bool = True
    default_timeout: int = 300

    # Auto-load on initialization
    auto_discover: bool = True
    auto_load: bool = True


class PluginManager:
    """Central manager for the Mother plugin system.

    Coordinates plugin discovery, loading, registration, and execution.
    """

    def __init__(self, config: PluginConfig | None = None):
        """Initialize the plugin manager.

        Args:
            config: Plugin configuration (defaults to PluginConfig())
        """
        self.config = config or PluginConfig()

        # Components
        self._loader = PluginLoader(
            user_plugins_dir=self.config.user_plugins_dir,
            project_plugins_dir=self.config.project_plugins_dir,
            builtin_plugins_dir=self.config.builtin_plugins_dir,
        )
        self._registry = PluginRegistry()
        self._sandbox_manager = SandboxManager()

        # State
        self._initialized = False
        self._discovered: dict[str, PluginInfo] = {}

    @property
    def registry(self) -> PluginRegistry:
        """Get the plugin registry."""
        return self._registry

    @property
    def loader(self) -> PluginLoader:
        """Get the plugin loader."""
        return self._loader

    async def initialize(self) -> None:
        """Initialize the plugin system.

        Discovers plugins and optionally auto-loads them based on config.
        """
        if not self.config.enabled:
            logger.info("Plugin system is disabled")
            return

        # Discover plugins
        if self.config.auto_discover:
            self.discover()

        # Auto-load plugins
        if self.config.auto_load:
            await self.load_all()

        self._initialized = True
        logger.info(
            f"Plugin system initialized: {len(self._registry)} capabilities "
            f"from {len(self._registry.list_plugins())} plugins"
        )

    def discover(self) -> dict[str, PluginInfo]:
        """Discover all available plugins.

        Returns:
            Dict mapping plugin names to PluginInfo
        """
        self._discovered = self._loader.discover_all()

        # Filter based on config
        if self.config.enabled_plugins is not None:
            self._discovered = {
                name: info
                for name, info in self._discovered.items()
                if name in self.config.enabled_plugins
            }

        # Remove disabled plugins
        for disabled in self.config.disabled_plugins:
            self._discovered.pop(disabled, None)

        logger.info(f"Discovered {len(self._discovered)} plugins")
        return self._discovered.copy()

    async def load_all(self) -> dict[str, PluginInfo]:
        """Load all discovered plugins.

        Returns:
            Dict of successfully loaded plugins
        """
        loaded = {}

        for name, info in self._discovered.items():
            if not info.loaded:
                continue  # Skip plugins that failed discovery

            try:
                await self.load(name)
                loaded[name] = info
            except Exception as e:
                logger.warning(f"Failed to load plugin '{name}': {e}")
                info.loaded = False
                info.error = str(e)

        return loaded

    async def load(self, plugin_name: str) -> None:
        """Load a specific plugin.

        Args:
            plugin_name: Name of the plugin to load

        Raises:
            PluginNotFoundError: If plugin not discovered
            PluginLoadError: If loading fails
        """
        # Get plugin settings
        settings = self.config.plugin_settings.get(plugin_name, {})

        # Load via loader
        executor = await self._loader.initialize_plugin(plugin_name, settings)

        # Get manifest
        manifest = self._loader.get_manifest(plugin_name)
        if not manifest:
            raise PluginLoadError(plugin_name, "Manifest not found after loading")

        # Create sandbox
        if self.config.require_permissions:
            self._sandbox_manager.create_sandbox(
                plugin_name,
                manifest.permissions,
            )

        # Register in registry
        self._registry.register(manifest, executor)

        logger.info(f"Loaded plugin: {plugin_name}")

    async def unload(self, plugin_name: str) -> None:
        """Unload a plugin.

        Args:
            plugin_name: Name of the plugin to unload
        """
        # Shutdown executor
        executor = self._loader.get_executor(plugin_name)
        if executor:
            await executor.shutdown()

        # Unload from loader
        self._loader.unload_plugin(plugin_name)

        # Unregister
        self._registry.unregister(plugin_name)

        # Remove sandbox
        self._sandbox_manager.remove_sandbox(plugin_name)

        logger.info(f"Unloaded plugin: {plugin_name}")

    async def reload(self, plugin_name: str) -> None:
        """Reload a plugin.

        Args:
            plugin_name: Name of the plugin to reload
        """
        await self.unload(plugin_name)

        # Re-discover to pick up changes
        self._loader.discover_all()

        await self.load(plugin_name)
        logger.info(f"Reloaded plugin: {plugin_name}")

    async def execute(
        self,
        capability_name: str,
        params: dict[str, Any],
        skip_permission_check: bool = False,
    ) -> PluginResult:
        """Execute a plugin capability.

        Args:
            capability_name: Full capability name (plugin_capability)
            params: Parameters for the capability
            skip_permission_check: Skip permission validation (for internal use)

        Returns:
            PluginResult with execution outcome

        Raises:
            CapabilityNotFoundError: If capability not found
            PermissionError: If permission check fails
            ExecutionError: If execution fails
        """
        # Get capability entry
        entry = self._registry.get_capability(capability_name)
        if not entry:
            raise CapabilityNotFoundError(capability_name)

        # Permission check
        if self.config.require_permissions and not skip_permission_check:
            sandbox = self._sandbox_manager.get_sandbox(entry.plugin_name)
            if sandbox:
                # TODO: Determine what permissions are needed based on capability
                pass

        # Check if confirmation required
        if entry.confirmation_required:
            return PluginResult.pending_confirmation(
                action_description=entry.spec.description,
                params=params,
                capability=capability_name,
                plugin=entry.plugin_name,
            )

        # Execute
        try:
            result = await entry.executor.execute(
                entry.capability_name,
                params,
            )
            return result

        except PluginTimeoutError:
            raise
        except Exception as e:
            raise ExecutionError(
                entry.plugin_name,
                entry.capability_name,
                str(e),
            )

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Get all capability schemas for Claude tool_use.

        Returns:
            List of tool schemas
        """
        return self._registry.get_all_anthropic_schemas()

    def get_capability(self, capability_name: str) -> CapabilityEntry | None:
        """Get a capability entry by name.

        Args:
            capability_name: Full capability name

        Returns:
            CapabilityEntry or None
        """
        return self._registry.get_capability(capability_name)

    def parse_capability_name(self, full_name: str) -> tuple[str, str]:
        """Parse a capability name into plugin and capability parts.

        Args:
            full_name: Full capability name

        Returns:
            Tuple of (plugin_name, capability_name)
        """
        return self._registry.parse_capability_name(full_name)

    def list_plugins(self) -> dict[str, PluginInfo]:
        """List all loaded plugins.

        Returns:
            Dict mapping plugin names to PluginInfo
        """
        return self._registry.list_plugins()

    def list_discovered(self) -> dict[str, PluginInfo]:
        """List all discovered plugins (including unloaded).

        Returns:
            Dict mapping plugin names to PluginInfo
        """
        return self._discovered.copy()

    def list_capabilities(self, plugin_name: str | None = None) -> list[str]:
        """List capabilities, optionally filtered by plugin.

        Args:
            plugin_name: Optional plugin to filter by

        Returns:
            List of capability names
        """
        return self._registry.list_capabilities(plugin_name)

    def requires_confirmation(self, capability_name: str) -> bool:
        """Check if a capability requires user confirmation.

        Args:
            capability_name: Full capability name

        Returns:
            True if confirmation required
        """
        return self._registry.requires_confirmation(capability_name)

    def search_capabilities(self, query: str, limit: int = 10) -> list[CapabilityEntry]:
        """Search capabilities by name or description.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching capabilities
        """
        return self._registry.search_capabilities(query, limit)

    def get_plugin_info(self, plugin_name: str) -> PluginInfo | None:
        """Get detailed info about a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            PluginInfo or None
        """
        plugins = self._registry.list_plugins()
        return plugins.get(plugin_name)

    def is_loaded(self, plugin_name: str) -> bool:
        """Check if a plugin is loaded.

        Args:
            plugin_name: Name of the plugin

        Returns:
            True if loaded
        """
        return self._loader.is_loaded(plugin_name)

    async def shutdown(self) -> None:
        """Shutdown all plugins and cleanup."""
        for plugin_name in list(self._registry.list_plugins().keys()):
            try:
                await self.unload(plugin_name)
            except Exception as e:
                logger.warning(f"Error unloading {plugin_name}: {e}")

        self._initialized = False
        logger.info("Plugin system shutdown complete")

    def __len__(self) -> int:
        """Get the number of loaded capabilities."""
        return len(self._registry)

    def __contains__(self, capability_name: str) -> bool:
        """Check if a capability is available."""
        return capability_name in self._registry
