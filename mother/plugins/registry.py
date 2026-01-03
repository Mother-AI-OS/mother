"""Capability registry for Mother plugins.

This module provides a central registry for plugin capabilities,
enabling efficient lookup and schema generation for Claude tool_use.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from .base import PluginInfo
from .exceptions import CapabilityNotFoundError

if TYPE_CHECKING:
    from .executor import ExecutorBase
    from .manifest import CapabilitySpec, PluginManifest

logger = logging.getLogger("mother.plugins.registry")


@dataclass
class CapabilityEntry:
    """Registry entry for a capability."""

    plugin_name: str
    capability_name: str
    full_name: str  # plugin_capability format
    spec: "CapabilitySpec"
    executor: "ExecutorBase"
    confirmation_required: bool = False

    @property
    def anthropic_schema(self) -> dict[str, Any]:
        """Get the Anthropic tool_use schema for this capability."""
        return self.spec.to_anthropic_schema(self.plugin_name)


class PluginRegistry:
    """Central registry for loaded plugins and their capabilities.

    Provides efficient lookup of capabilities by name and generates
    schemas for Claude's tool_use feature.
    """

    def __init__(self):
        """Initialize the registry."""
        self._plugins: dict[str, "ExecutorBase"] = {}
        self._manifests: dict[str, "PluginManifest"] = {}
        self._capabilities: dict[str, CapabilityEntry] = {}  # full_name -> entry
        self._plugin_capabilities: dict[str, list[str]] = {}  # plugin -> [full_names]

    def register(
        self,
        manifest: "PluginManifest",
        executor: "ExecutorBase",
    ) -> None:
        """Register a plugin and its capabilities.

        Args:
            manifest: Plugin manifest
            executor: Initialized executor for the plugin
        """
        plugin_name = manifest.plugin.name

        # Store plugin reference
        self._plugins[plugin_name] = executor
        self._manifests[plugin_name] = manifest
        self._plugin_capabilities[plugin_name] = []

        # Register capabilities
        for cap_spec in manifest.capabilities:
            full_name = f"{plugin_name}_{cap_spec.name}"

            entry = CapabilityEntry(
                plugin_name=plugin_name,
                capability_name=cap_spec.name,
                full_name=full_name,
                spec=cap_spec,
                executor=executor,
                confirmation_required=cap_spec.confirmation_required,
            )

            self._capabilities[full_name] = entry
            self._plugin_capabilities[plugin_name].append(full_name)

            logger.debug(f"Registered capability: {full_name}")

        logger.info(
            f"Registered plugin '{plugin_name}' with "
            f"{len(manifest.capabilities)} capabilities"
        )

    def unregister(self, plugin_name: str) -> None:
        """Unregister a plugin and its capabilities.

        Args:
            plugin_name: Name of the plugin to unregister
        """
        if plugin_name not in self._plugins:
            return

        # Remove capabilities
        for full_name in self._plugin_capabilities.get(plugin_name, []):
            self._capabilities.pop(full_name, None)

        # Remove plugin
        self._plugins.pop(plugin_name, None)
        self._manifests.pop(plugin_name, None)
        self._plugin_capabilities.pop(plugin_name, None)

        logger.info(f"Unregistered plugin: {plugin_name}")

    def get_plugin(self, plugin_name: str) -> "ExecutorBase | None":
        """Get a registered plugin's executor.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Executor or None if not registered
        """
        return self._plugins.get(plugin_name)

    def get_manifest(self, plugin_name: str) -> "PluginManifest | None":
        """Get a registered plugin's manifest.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Manifest or None if not registered
        """
        return self._manifests.get(plugin_name)

    def get_capability(self, full_name: str) -> CapabilityEntry | None:
        """Get a capability by its full name.

        Args:
            full_name: Full capability name (plugin_capability)

        Returns:
            CapabilityEntry or None if not found
        """
        return self._capabilities.get(full_name)

    def get_capability_by_parts(
        self,
        plugin_name: str,
        capability_name: str,
    ) -> CapabilityEntry | None:
        """Get a capability by plugin and capability names.

        Args:
            plugin_name: Name of the plugin
            capability_name: Name of the capability

        Returns:
            CapabilityEntry or None if not found
        """
        full_name = f"{plugin_name}_{capability_name}"
        return self.get_capability(full_name)

    def parse_capability_name(self, full_name: str) -> tuple[str, str]:
        """Parse a full capability name into plugin and capability parts.

        Args:
            full_name: Full name like "mailcraft_send_email"

        Returns:
            Tuple of (plugin_name, capability_name)

        Raises:
            CapabilityNotFoundError: If capability not found
        """
        # Try to find a matching capability
        if full_name in self._capabilities:
            entry = self._capabilities[full_name]
            return entry.plugin_name, entry.capability_name

        # Try splitting at first underscore
        if "_" in full_name:
            parts = full_name.split("_", 1)
            plugin_name = parts[0]
            capability_name = parts[1]

            # Check if this combination exists
            if f"{plugin_name}_{capability_name}" in self._capabilities:
                return plugin_name, capability_name

            # Try with more parts for plugin name
            # e.g., "my_plugin_do_thing" could be plugin="my_plugin", cap="do_thing"
            for i in range(1, full_name.count("_")):
                parts = full_name.rsplit("_", i)
                potential_plugin = "_".join(parts[:-1]) if len(parts) > 2 else parts[0]
                potential_cap = "_".join(parts[-i:]) if i > 1 else parts[-1]

                test_name = f"{potential_plugin}_{potential_cap}"
                if test_name in self._capabilities:
                    entry = self._capabilities[test_name]
                    return entry.plugin_name, entry.capability_name

        raise CapabilityNotFoundError(full_name)

    def list_plugins(self) -> dict[str, PluginInfo]:
        """List all registered plugins.

        Returns:
            Dict mapping plugin names to PluginInfo
        """
        result = {}
        for name, manifest in self._manifests.items():
            result[name] = PluginInfo.from_manifest(manifest, "registry")
        return result

    def list_capabilities(self, plugin_name: str | None = None) -> list[str]:
        """List capabilities, optionally filtered by plugin.

        Args:
            plugin_name: Optional plugin name to filter by

        Returns:
            List of full capability names
        """
        if plugin_name:
            return self._plugin_capabilities.get(plugin_name, []).copy()
        return list(self._capabilities.keys())

    def get_all_anthropic_schemas(self) -> list[dict[str, Any]]:
        """Get all capabilities as Anthropic tool_use schemas.

        Returns:
            List of tool schemas for Claude
        """
        return [entry.anthropic_schema for entry in self._capabilities.values()]

    def get_plugin_schemas(self, plugin_name: str) -> list[dict[str, Any]]:
        """Get schemas for a specific plugin's capabilities.

        Args:
            plugin_name: Name of the plugin

        Returns:
            List of tool schemas
        """
        schemas = []
        for full_name in self._plugin_capabilities.get(plugin_name, []):
            entry = self._capabilities.get(full_name)
            if entry:
                schemas.append(entry.anthropic_schema)
        return schemas

    def requires_confirmation(self, full_name: str) -> bool:
        """Check if a capability requires user confirmation.

        Args:
            full_name: Full capability name

        Returns:
            True if confirmation is required
        """
        entry = self._capabilities.get(full_name)
        return entry.confirmation_required if entry else False

    def search_capabilities(
        self,
        query: str,
        limit: int = 10,
    ) -> list[CapabilityEntry]:
        """Search capabilities by name or description.

        Args:
            query: Search query
            limit: Maximum results to return

        Returns:
            List of matching CapabilityEntry objects
        """
        query_lower = query.lower()
        matches = []

        for entry in self._capabilities.values():
            score = 0

            # Check capability name
            if query_lower in entry.capability_name.lower():
                score += 10
            if query_lower in entry.full_name.lower():
                score += 5

            # Check description
            if query_lower in entry.spec.description.lower():
                score += 3

            # Check plugin name
            if query_lower in entry.plugin_name.lower():
                score += 2

            if score > 0:
                matches.append((score, entry))

        # Sort by score descending
        matches.sort(key=lambda x: x[0], reverse=True)

        return [entry for _, entry in matches[:limit]]

    def __len__(self) -> int:
        """Get the number of registered capabilities."""
        return len(self._capabilities)

    def __contains__(self, full_name: str) -> bool:
        """Check if a capability is registered."""
        return full_name in self._capabilities
