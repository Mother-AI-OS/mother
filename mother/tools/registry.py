"""Tool registry for discovering and managing plugins.

This module provides the ToolRegistry which manages plugin-based tools.
Legacy ToolWrapper-based tools have been removed in favor of the plugin system.

All tool functionality is now provided by plugins in mother.plugins.builtin:
- email: Email composition and sending
- pdf: PDF manipulation (merge, split, extract, rotate)
- datacraft: Document processing and search
- tasks: Task management
- transmit: Document transmission (email, fax, post, beA)
- taxlord: German tax automation
- leads: Lead generation
- google-docs: Google Docs integration
"""

import logging
from typing import Any, Optional

from ..config.settings import Settings
from .base import ToolWrapper

# Import plugin system (optional, for graceful degradation)
try:
    from ..plugins import PluginConfig, PluginManager, PluginResult

    PLUGINS_AVAILABLE = True
except ImportError:
    PLUGINS_AVAILABLE = False
    PluginManager = None
    PluginConfig = None

logger = logging.getLogger("mother.tools.registry")


class ToolRegistry:
    """Registry for managing plugins.

    This registry manages plugin-based tools via the PluginManager.
    Legacy ToolWrapper-based tools have been removed.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        plugin_config: Optional["PluginConfig"] = None,
        enable_plugins: bool = True,
    ):
        self.wrappers: dict[str, ToolWrapper] = {}
        self._settings = settings
        self._plugin_manager: PluginManager | None = None
        self._plugins_enabled = enable_plugins and PLUGINS_AVAILABLE

        # Initialize plugin system
        if self._plugins_enabled:
            self._init_plugins(plugin_config)

    def _init_plugins(self, plugin_config: Optional["PluginConfig"] = None) -> None:
        """Initialize the plugin system.

        Args:
            plugin_config: Optional plugin configuration
        """
        if not PLUGINS_AVAILABLE:
            logger.warning("Plugin system not available (import failed)")
            return

        try:
            config = plugin_config or PluginConfig()
            self._plugin_manager = PluginManager(config)
            # Note: Full initialization (discover + load) happens in async initialize()
            logger.info("Plugin manager created (async initialization pending)")
        except Exception as e:
            logger.error(f"Failed to initialize plugin system: {e}")
            self._plugin_manager = None

    async def initialize_plugins(self) -> None:
        """Async initialization of the plugin system.

        Call this after creating the registry to discover and load plugins.
        """
        if self._plugin_manager is not None:
            try:
                await self._plugin_manager.initialize()
                logger.info(f"Plugin system initialized: {len(self._plugin_manager)} capabilities")
            except Exception as e:
                logger.error(f"Failed to initialize plugins: {e}")

    @property
    def plugin_manager(self) -> Optional["PluginManager"]:
        """Get the plugin manager instance."""
        return self._plugin_manager

    def get_wrapper(self, name: str) -> ToolWrapper | None:
        """Get a tool wrapper by name.

        Note: Legacy wrappers have been removed. This method is kept for
        backwards compatibility but will always return None.
        """
        return self.wrappers.get(name)

    def get_all_anthropic_schemas(self) -> list[dict]:
        """Get all tool schemas in Anthropic format.

        Returns schemas from all registered plugins.
        """
        schemas = []

        # Plugin schemas
        if self._plugin_manager is not None:
            for schema in self._plugin_manager.get_all_schemas():
                schemas.append(schema)

        return schemas

    def list_tools(self) -> dict[str, dict]:
        """List all available tools with their info."""
        result = {}

        # Plugin tools
        if self._plugin_manager is not None:
            for name, info in self._plugin_manager.list_plugins().items():
                result[name] = {
                    "description": info.description,
                    "commands": info.capabilities,
                    "source": "plugin",
                    "version": info.version,
                    "author": info.author,
                    "deprecated": False,
                }

        return result

    def get_tool_details(self, name: str) -> dict | None:
        """Get detailed information about a tool.

        Note: Legacy wrapper details have been removed. Use plugin_manager
        for plugin details.
        """
        return None

    def parse_tool_name(self, full_name: str) -> tuple[str | None, str | None]:
        """Parse a full tool name into plugin name and capability.

        Example: "email_send" -> ("email", "send")
        Example: "pdf_merge" -> ("pdf", "merge")
        """
        # Check plugins
        if self._plugin_manager is not None and full_name in self._plugin_manager:
            try:
                plugin_name, capability = self._plugin_manager.parse_capability_name(full_name)
                return plugin_name, capability
            except Exception:
                pass

        return None, None

    def is_plugin_capability(self, full_name: str) -> bool:
        """Check if a tool name refers to a plugin capability.

        Args:
            full_name: Full tool name (e.g., "email_send")

        Returns:
            True if this is a plugin capability
        """
        if self._plugin_manager is None:
            return False
        return full_name in self._plugin_manager

    async def execute_plugin(
        self,
        full_name: str,
        params: dict[str, Any],
    ) -> "PluginResult":
        """Execute a plugin capability.

        Args:
            full_name: Full capability name (e.g., "email_send")
            params: Parameters for the capability

        Returns:
            PluginResult with execution outcome

        Raises:
            ValueError: If plugins not available or capability not found
        """
        if self._plugin_manager is None:
            raise ValueError("Plugin system not available")

        return await self._plugin_manager.execute(full_name, params)

    def requires_confirmation(self, full_name: str) -> bool:
        """Check if a tool/capability requires user confirmation.

        Args:
            full_name: Full tool name

        Returns:
            True if confirmation is required
        """
        # Check plugins
        if self._plugin_manager is not None and full_name in self._plugin_manager:
            return self._plugin_manager.requires_confirmation(full_name)

        return False
