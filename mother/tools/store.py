"""Tool store for persisting installed tools.

This module provides persistence for the external tools registry,
storing installation state in a JSON file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .exceptions import ToolNotInstalledError

logger = logging.getLogger("mother.tools.store")


@dataclass
class InstalledTool:
    """Represents an installed external tool."""

    name: str
    version: str
    source: str  # "local:/path", "git:url", "catalog:name"
    installed_at: str  # ISO format timestamp
    enabled: bool
    manifest_path: str  # Path to the tool's manifest
    integration_type: str  # python, cli, http, docker
    risk_level: str = "low"
    description: str = ""
    config_values: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        name: str,
        version: str,
        source: str,
        manifest_path: Path | str,
        integration_type: str,
        risk_level: str = "low",
        description: str = "",
        enabled: bool = False,  # Disabled by default
        config_values: dict[str, Any] | None = None,
    ) -> InstalledTool:
        """Create a new InstalledTool with current timestamp.

        Args:
            name: Tool name
            version: Tool version
            source: Installation source
            manifest_path: Path to manifest file
            integration_type: How the tool integrates
            risk_level: Tool risk level
            description: Tool description
            enabled: Whether tool is enabled (default False)
            config_values: User configuration values

        Returns:
            New InstalledTool instance
        """
        return cls(
            name=name,
            version=version,
            source=source,
            installed_at=datetime.now(UTC).isoformat(),
            enabled=enabled,
            manifest_path=str(manifest_path),
            integration_type=integration_type,
            risk_level=risk_level,
            description=description,
            config_values=config_values or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstalledTool:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            version=data["version"],
            source=data["source"],
            installed_at=data["installed_at"],
            enabled=data.get("enabled", False),
            manifest_path=data["manifest_path"],
            integration_type=data["integration_type"],
            risk_level=data.get("risk_level", "low"),
            description=data.get("description", ""),
            config_values=data.get("config_values", {}),
        )


class ToolStore:
    """Persistent storage for installed tools.

    Stores tool installation data in a JSON file at:
    ~/.local/share/mother/tools/tools.json
    """

    def __init__(self, store_path: Path | None = None):
        """Initialize the tool store.

        Args:
            store_path: Path to the store file. Defaults to
                        ~/.local/share/mother/tools/tools.json
        """
        if store_path is None:
            store_path = Path.home() / ".local" / "share" / "mother" / "tools" / "tools.json"

        self._store_path = store_path
        self._tools: dict[str, InstalledTool] = {}
        self._loaded = False

    @property
    def store_path(self) -> Path:
        """Get the store file path."""
        return self._store_path

    def load(self) -> None:
        """Load tools from the store file."""
        if not self._store_path.exists():
            self._tools = {}
            self._loaded = True
            return

        try:
            with open(self._store_path) as f:
                data = json.load(f)

            self._tools = {}
            for name, tool_data in data.get("tools", {}).items():
                try:
                    self._tools[name] = InstalledTool.from_dict(tool_data)
                except Exception as e:
                    logger.warning(f"Failed to load tool '{name}': {e}")

            self._loaded = True
            logger.info(f"Loaded {len(self._tools)} tools from store")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tool store: {e}")
            self._tools = {}
            self._loaded = True
        except Exception as e:
            logger.error(f"Failed to load tool store: {e}")
            self._tools = {}
            self._loaded = True

    def save(self) -> None:
        """Save tools to the store file."""
        # Ensure directory exists
        self._store_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "updated_at": datetime.now(UTC).isoformat(),
            "tools": {name: tool.to_dict() for name, tool in self._tools.items()},
        }

        try:
            with open(self._store_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self._tools)} tools to store")
        except Exception as e:
            logger.error(f"Failed to save tool store: {e}")
            raise

    def _ensure_loaded(self) -> None:
        """Ensure the store has been loaded."""
        if not self._loaded:
            self.load()

    def list_tools(self) -> list[InstalledTool]:
        """List all installed tools.

        Returns:
            List of installed tools
        """
        self._ensure_loaded()
        return list(self._tools.values())

    def get_tool(self, name: str) -> InstalledTool | None:
        """Get an installed tool by name.

        Args:
            name: Tool name

        Returns:
            InstalledTool or None if not found
        """
        self._ensure_loaded()
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is installed.

        Args:
            name: Tool name

        Returns:
            True if installed
        """
        self._ensure_loaded()
        return name in self._tools

    def add_tool(self, tool: InstalledTool) -> None:
        """Add or update an installed tool.

        Args:
            tool: Tool to add
        """
        self._ensure_loaded()
        self._tools[tool.name] = tool
        self.save()
        logger.info(f"Added tool: {tool.name} v{tool.version}")

    def remove_tool(self, name: str) -> None:
        """Remove an installed tool.

        Args:
            name: Tool name to remove

        Raises:
            ToolNotInstalledError: If tool not installed
        """
        self._ensure_loaded()
        if name not in self._tools:
            raise ToolNotInstalledError(name)

        del self._tools[name]
        self.save()
        logger.info(f"Removed tool: {name}")

    def enable_tool(self, name: str) -> None:
        """Enable an installed tool.

        Args:
            name: Tool name

        Raises:
            ToolNotInstalledError: If tool not installed
        """
        self._ensure_loaded()
        if name not in self._tools:
            raise ToolNotInstalledError(name)

        self._tools[name].enabled = True
        self.save()
        logger.info(f"Enabled tool: {name}")

    def disable_tool(self, name: str) -> None:
        """Disable an installed tool.

        Args:
            name: Tool name

        Raises:
            ToolNotInstalledError: If tool not installed
        """
        self._ensure_loaded()
        if name not in self._tools:
            raise ToolNotInstalledError(name)

        self._tools[name].enabled = False
        self.save()
        logger.info(f"Disabled tool: {name}")

    def update_config(self, name: str, config_values: dict[str, Any]) -> None:
        """Update configuration for an installed tool.

        Args:
            name: Tool name
            config_values: New configuration values

        Raises:
            ToolNotInstalledError: If tool not installed
        """
        self._ensure_loaded()
        if name not in self._tools:
            raise ToolNotInstalledError(name)

        self._tools[name].config_values.update(config_values)
        self.save()
        logger.info(f"Updated config for tool: {name}")

    def list_enabled(self) -> list[InstalledTool]:
        """List all enabled tools.

        Returns:
            List of enabled tools
        """
        self._ensure_loaded()
        return [t for t in self._tools.values() if t.enabled]

    def list_disabled(self) -> list[InstalledTool]:
        """List all disabled tools.

        Returns:
            List of disabled tools
        """
        self._ensure_loaded()
        return [t for t in self._tools.values() if not t.enabled]

    def clear(self) -> None:
        """Clear all tools from the store."""
        self._tools = {}
        self.save()
        logger.info("Cleared tool store")
