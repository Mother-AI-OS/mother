"""External tool registry for managing tool repo installations.

This module provides the ExternalToolRegistry which coordinates:
- Tool installation from local paths, git URLs, or catalog
- Tool enabling/disabling
- Tool status and health checks

Note: This is distinct from ToolRegistry (in registry.py) which wraps
the plugin system for runtime capabilities.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ..audit import AuditEventType, get_audit_logger
from .catalog import CatalogEntry, ToolCatalog
from .exceptions import (
    ToolAlreadyInstalledError,
    ToolInstallError,
    ToolNotFoundError,
    ToolNotInstalledError,
    ToolPolicyViolationError,
)
from .store import InstalledTool, ToolStore
from .tool_manifest import ToolManifest, find_tool_manifest, load_tool_manifest

logger = logging.getLogger("mother.tools.external_registry")


class ToolStatus(str, Enum):
    """Status of a tool."""

    NOT_INSTALLED = "not_installed"
    INSTALLED_DISABLED = "installed_disabled"
    INSTALLED_ENABLED = "installed_enabled"
    ERROR = "error"


class InstallSource(str, Enum):
    """Source type for tool installation."""

    LOCAL = "local"  # Local file path
    GIT = "git"  # Git repository URL
    CATALOG = "catalog"  # Known tool from catalog


@dataclass
class ToolInfo:
    """Information about a tool (installed or available)."""

    name: str
    version: str
    description: str
    status: ToolStatus
    source: str | None
    risk_level: str
    integration_types: list[str]
    installed: InstalledTool | None = None
    catalog_entry: CatalogEntry | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "status": self.status.value,
            "source": self.source,
            "risk_level": self.risk_level,
            "integration_types": self.integration_types,
            "error": self.error,
        }


class ExternalToolRegistry:
    """Registry for managing external tool repositories.

    This registry handles:
    - Discovering available tools from the catalog
    - Installing tools from local paths, git URLs, or catalog
    - Managing tool enable/disable state
    - Querying tool status

    Tools are installed to ~/.local/share/mother/tools/<name>/
    """

    def __init__(
        self,
        store: ToolStore | None = None,
        catalog: ToolCatalog | None = None,
        tools_dir: Path | None = None,
    ):
        """Initialize the registry.

        Args:
            store: Tool store for persistence
            catalog: Tool catalog for available tools
            tools_dir: Directory for installed tools
        """
        self._store = store or ToolStore()
        self._catalog = catalog or ToolCatalog()

        if tools_dir is None:
            tools_dir = Path.home() / ".local" / "share" / "mother" / "tools"
        self._tools_dir = tools_dir

    @property
    def tools_dir(self) -> Path:
        """Get the tools installation directory."""
        return self._tools_dir

    def list_all(self) -> list[ToolInfo]:
        """List all tools (installed and available in catalog).

        Returns:
            List of ToolInfo objects
        """
        tools_by_name: dict[str, ToolInfo] = {}

        # Add catalog entries
        for entry in self._catalog.list_entries():
            tools_by_name[entry.name] = ToolInfo(
                name=entry.name,
                version=entry.version,
                description=entry.description,
                status=ToolStatus.NOT_INSTALLED,
                source=f"catalog:{entry.name}",
                risk_level=entry.risk_level,
                integration_types=entry.integration_types,
                catalog_entry=entry,
            )

        # Overlay installed tools
        for installed in self._store.list_tools():
            if installed.name in tools_by_name:
                info = tools_by_name[installed.name]
                info.status = ToolStatus.INSTALLED_ENABLED if installed.enabled else ToolStatus.INSTALLED_DISABLED
                info.installed = installed
                info.version = installed.version
                info.source = installed.source
            else:
                # Tool not in catalog (locally installed)
                tools_by_name[installed.name] = ToolInfo(
                    name=installed.name,
                    version=installed.version,
                    description=installed.description,
                    status=ToolStatus.INSTALLED_ENABLED if installed.enabled else ToolStatus.INSTALLED_DISABLED,
                    source=installed.source,
                    risk_level=installed.risk_level,
                    integration_types=[installed.integration_type],
                    installed=installed,
                )

        return sorted(tools_by_name.values(), key=lambda t: t.name)

    def list_installed(self) -> list[InstalledTool]:
        """List installed tools.

        Returns:
            List of installed tools
        """
        return self._store.list_tools()

    def list_available(self) -> list[CatalogEntry]:
        """List available tools from catalog (not yet installed).

        Returns:
            List of catalog entries for uninstalled tools
        """
        installed_names = {t.name for t in self._store.list_tools()}
        return [e for e in self._catalog.list_entries() if e.name not in installed_names]

    def get_status(self, name: str) -> ToolInfo:
        """Get detailed status for a tool.

        Args:
            name: Tool name

        Returns:
            ToolInfo with current status

        Raises:
            ToolNotFoundError: If tool not found anywhere
        """
        installed = self._store.get_tool(name)
        catalog_entry = self._catalog.get_entry(name)

        if not installed and not catalog_entry:
            raise ToolNotFoundError(name)

        if installed:
            return ToolInfo(
                name=installed.name,
                version=installed.version,
                description=installed.description,
                status=ToolStatus.INSTALLED_ENABLED if installed.enabled else ToolStatus.INSTALLED_DISABLED,
                source=installed.source,
                risk_level=installed.risk_level,
                integration_types=[installed.integration_type],
                installed=installed,
                catalog_entry=catalog_entry,
            )
        else:
            return ToolInfo(
                name=catalog_entry.name,
                version=catalog_entry.version,
                description=catalog_entry.description,
                status=ToolStatus.NOT_INSTALLED,
                source=f"catalog:{catalog_entry.name}",
                risk_level=catalog_entry.risk_level,
                integration_types=catalog_entry.integration_types,
                catalog_entry=catalog_entry,
            )

    def is_installed(self, name: str) -> bool:
        """Check if a tool is installed.

        Args:
            name: Tool name

        Returns:
            True if installed
        """
        return self._store.has_tool(name)

    def is_enabled(self, name: str) -> bool:
        """Check if a tool is enabled.

        Args:
            name: Tool name

        Returns:
            True if installed and enabled
        """
        tool = self._store.get_tool(name)
        return tool is not None and tool.enabled

    def install(
        self,
        source: str,
        enabled: bool = False,
        config_values: dict[str, Any] | None = None,
    ) -> InstalledTool:
        """Install a tool from a source.

        Args:
            source: Installation source:
                - Local path: "/path/to/tool" or "local:/path/to/tool"
                - Git URL: "git:https://github.com/org/repo" or "https://github.com/..."
                - Catalog: "contentcraft" or "catalog:contentcraft"
            enabled: Whether to enable after install (default False)
            config_values: Initial configuration values

        Returns:
            InstalledTool record

        Raises:
            ToolAlreadyInstalledError: If tool already installed
            ToolInstallError: If installation fails
        """
        # Parse source
        source_type, source_path = self._parse_source(source)

        if source_type == InstallSource.LOCAL:
            return self._install_from_local(source_path, enabled, config_values)
        elif source_type == InstallSource.GIT:
            return self._install_from_git(source_path, enabled, config_values)
        elif source_type == InstallSource.CATALOG:
            return self._install_from_catalog(source_path, enabled, config_values)
        else:
            raise ToolInstallError("unknown", f"Unknown source type: {source_type}")

    def _parse_source(self, source: str) -> tuple[InstallSource, str]:
        """Parse an installation source string.

        Args:
            source: Source string

        Returns:
            Tuple of (source_type, path/name)
        """
        # Explicit prefix
        if source.startswith("local:"):
            return InstallSource.LOCAL, source[6:]
        if source.startswith("git:"):
            return InstallSource.GIT, source[4:]
        if source.startswith("catalog:"):
            return InstallSource.CATALOG, source[8:]

        # Auto-detect
        if source.startswith("/") or source.startswith("~") or source.startswith("."):
            return InstallSource.LOCAL, source
        if source.startswith("https://") or source.startswith("git@"):
            return InstallSource.GIT, source

        # Assume catalog name
        return InstallSource.CATALOG, source

    def _install_from_local(
        self,
        path: str,
        enabled: bool,
        config_values: dict[str, Any] | None,
    ) -> InstalledTool:
        """Install from local path."""
        # Expand path
        local_path = Path(path).expanduser().resolve()

        if not local_path.exists():
            raise ToolInstallError("unknown", f"Path does not exist: {local_path}")

        # Find and load manifest
        manifest_path = find_tool_manifest(local_path)
        if not manifest_path:
            raise ToolInstallError("unknown", f"No mother-tool.yaml found in {local_path}")

        manifest = load_tool_manifest(manifest_path)

        # Check if already installed
        if self._store.has_tool(manifest.name):
            raise ToolAlreadyInstalledError(manifest.name)

        # Create tool record (pointing to local path, not copying)
        tool = InstalledTool.create(
            name=manifest.name,
            version=manifest.version,
            source=f"local:{local_path}",
            manifest_path=manifest_path,
            integration_type=manifest.integration.type.value,
            risk_level=manifest.risk_level.value,
            description=manifest.tool.description,
            enabled=enabled,
            config_values=config_values,
        )

        self._store.add_tool(tool)
        logger.info(f"Installed tool from local: {manifest.name} v{manifest.version}")

        # Audit log the installation
        try:
            audit_logger = get_audit_logger()
            audit_logger.log_tool_event(
                event_type=AuditEventType.TOOL_INSTALLED,
                tool_name=manifest.name,
                tool_version=manifest.version,
                source=f"local:{local_path}",
                risk_level=manifest.risk_level.value,
            )
        except Exception as e:
            logger.warning(f"Failed to audit log tool install: {e}")

        return tool

    def _install_from_git(
        self,
        url: str,
        enabled: bool,
        config_values: dict[str, Any] | None,
    ) -> InstalledTool:
        """Install from git repository."""
        # Create temp directory for clone
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            clone_path = Path(tmpdir) / "repo"

            # Clone repository
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", url, str(clone_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                raise ToolInstallError("unknown", f"Git clone failed: {e.stderr}")

            # Find and load manifest
            manifest_path = find_tool_manifest(clone_path)
            if not manifest_path:
                raise ToolInstallError("unknown", f"No mother-tool.yaml found in repository")

            manifest = load_tool_manifest(manifest_path)

            # Check if already installed
            if self._store.has_tool(manifest.name):
                raise ToolAlreadyInstalledError(manifest.name)

            # Copy to tools directory
            install_path = self._tools_dir / manifest.name
            if install_path.exists():
                shutil.rmtree(install_path)

            shutil.copytree(clone_path, install_path)
            installed_manifest_path = install_path / manifest_path.name

            # Create tool record
            tool = InstalledTool.create(
                name=manifest.name,
                version=manifest.version,
                source=f"git:{url}",
                manifest_path=installed_manifest_path,
                integration_type=manifest.integration.type.value,
                risk_level=manifest.risk_level.value,
                description=manifest.tool.description,
                enabled=enabled,
                config_values=config_values,
            )

            self._store.add_tool(tool)
            logger.info(f"Installed tool from git: {manifest.name} v{manifest.version}")

            # Audit log the installation
            try:
                audit_logger = get_audit_logger()
                audit_logger.log_tool_event(
                    event_type=AuditEventType.TOOL_INSTALLED,
                    tool_name=manifest.name,
                    tool_version=manifest.version,
                    source=f"git:{url}",
                    risk_level=manifest.risk_level.value,
                )
            except Exception as e:
                logger.warning(f"Failed to audit log tool install: {e}")

            return tool

    def _install_from_catalog(
        self,
        name: str,
        enabled: bool,
        config_values: dict[str, Any] | None,
    ) -> InstalledTool:
        """Install from catalog."""
        entry = self._catalog.get_entry(name)
        if not entry:
            raise ToolNotFoundError(name, "catalog")

        if entry.deprecated:
            logger.warning(f"Tool '{name}' is deprecated: {entry.deprecation_notice}")

        # Install from git repository
        return self._install_from_git(entry.repository, enabled, config_values)

    def uninstall(self, name: str, remove_files: bool = True) -> None:
        """Uninstall a tool.

        Args:
            name: Tool name
            remove_files: Also remove installed files

        Raises:
            ToolNotInstalledError: If tool not installed
        """
        tool = self._store.get_tool(name)
        if not tool:
            raise ToolNotInstalledError(name)

        # Remove files if installed from git
        if remove_files and tool.source.startswith("git:"):
            install_path = self._tools_dir / name
            if install_path.exists():
                shutil.rmtree(install_path)
                logger.info(f"Removed tool files: {install_path}")

        # Remove from store
        self._store.remove_tool(name)
        logger.info(f"Uninstalled tool: {name}")

        # Audit log the uninstall
        try:
            audit_logger = get_audit_logger()
            audit_logger.log_tool_event(
                event_type=AuditEventType.TOOL_UNINSTALLED,
                tool_name=name,
                tool_version=tool.version,
                source=tool.source,
                risk_level=tool.risk_level,
            )
        except Exception as e:
            logger.warning(f"Failed to audit log tool uninstall: {e}")

    def enable(self, name: str) -> None:
        """Enable an installed tool.

        Args:
            name: Tool name

        Raises:
            ToolNotInstalledError: If tool not installed
        """
        tool = self._store.get_tool(name)
        self._store.enable_tool(name)

        # Audit log
        try:
            audit_logger = get_audit_logger()
            audit_logger.log_tool_event(
                event_type=AuditEventType.TOOL_ENABLED,
                tool_name=name,
                tool_version=tool.version if tool else None,
                source=tool.source if tool else None,
                risk_level=tool.risk_level if tool else None,
            )
        except Exception as e:
            logger.warning(f"Failed to audit log tool enable: {e}")

    def disable(self, name: str) -> None:
        """Disable an installed tool.

        Args:
            name: Tool name

        Raises:
            ToolNotInstalledError: If tool not installed
        """
        tool = self._store.get_tool(name)
        self._store.disable_tool(name)

        # Audit log
        try:
            audit_logger = get_audit_logger()
            audit_logger.log_tool_event(
                event_type=AuditEventType.TOOL_DISABLED,
                tool_name=name,
                tool_version=tool.version if tool else None,
                source=tool.source if tool else None,
                risk_level=tool.risk_level if tool else None,
            )
        except Exception as e:
            logger.warning(f"Failed to audit log tool disable: {e}")

    def search_catalog(self, query: str) -> list[CatalogEntry]:
        """Search the catalog.

        Args:
            query: Search query

        Returns:
            List of matching catalog entries
        """
        return self._catalog.search(query)

    def get_manifest(self, name: str) -> ToolManifest | None:
        """Get the manifest for an installed tool.

        Args:
            name: Tool name

        Returns:
            ToolManifest or None if not installed
        """
        tool = self._store.get_tool(name)
        if not tool:
            return None

        manifest_path = Path(tool.manifest_path)
        if not manifest_path.exists():
            logger.warning(f"Manifest not found for {name}: {manifest_path}")
            return None

        try:
            return load_tool_manifest(manifest_path)
        except Exception as e:
            logger.warning(f"Failed to load manifest for {name}: {e}")
            return None

    def check_health(self, name: str) -> tuple[bool, str]:
        """Check the health of an installed tool.

        Args:
            name: Tool name

        Returns:
            Tuple of (healthy, message)
        """
        tool = self._store.get_tool(name)
        if not tool:
            return False, "Tool not installed"

        # Check manifest exists
        manifest_path = Path(tool.manifest_path)
        if not manifest_path.exists():
            return False, f"Manifest not found: {manifest_path}"

        # Load manifest
        try:
            manifest = load_tool_manifest(manifest_path)
        except Exception as e:
            return False, f"Invalid manifest: {e}"

        # Check CLI binary if CLI integration
        if manifest.integration.type.value == "cli" and manifest.integration.cli:
            binary = manifest.integration.cli.binary
            if not shutil.which(binary):
                # Check common locations
                found = False
                for check_path in [
                    Path.home() / ".local" / "bin" / binary,
                    self._tools_dir / name / ".venv" / "bin" / binary,
                ]:
                    if check_path.exists():
                        found = True
                        break

                if not found:
                    return False, f"Binary not found: {binary}"

            # Run health check command if specified
            if manifest.integration.cli.health_check:
                try:
                    result = subprocess.run(
                        manifest.integration.cli.health_check,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode != 0:
                        return False, f"Health check failed: {result.stderr}"
                except subprocess.TimeoutExpired:
                    return False, "Health check timed out"
                except Exception as e:
                    return False, f"Health check error: {e}"

        return True, "Healthy"
