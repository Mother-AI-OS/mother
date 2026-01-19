"""CLI commands for external tool management.

Provides commands for:
- Listing tools (installed and available)
- Installing tools from local paths, git URLs, or catalog
- Uninstalling tools
- Enabling/disabling tools
- Searching the catalog
"""

from __future__ import annotations

import json
import sys
from typing import Any

from ..tools import (
    ExternalToolRegistry,
    ToolAlreadyInstalledError,
    ToolCatalog,
    ToolInstallError,
    ToolNotFoundError,
    ToolNotInstalledError,
    ToolStatus,
    ToolStore,
)


def _get_registry() -> ExternalToolRegistry:
    """Create a registry instance with default configuration."""
    store = ToolStore()
    catalog = ToolCatalog()
    return ExternalToolRegistry(store=store, catalog=catalog)


def _format_status(status: ToolStatus) -> str:
    """Format a tool status for display."""
    if status == ToolStatus.NOT_INSTALLED:
        return "not installed"
    elif status == ToolStatus.INSTALLED_DISABLED:
        return "installed (disabled)"
    elif status == ToolStatus.INSTALLED_ENABLED:
        return "installed (enabled)"
    elif status == ToolStatus.ERROR:
        return "error"
    return str(status.value)


def _format_risk(risk_level: str) -> str:
    """Format risk level with visual indicator."""
    indicators = {
        "low": "[low]",
        "medium": "[medium]",
        "high": "[HIGH]",
        "critical": "[CRITICAL]",
    }
    return indicators.get(risk_level, f"[{risk_level}]")


def cmd_list(
    show_all: bool = False,
    show_installed: bool = False,
    show_available: bool = False,
    json_output: bool = False,
) -> int:
    """List tools.

    Args:
        show_all: Show all tools (default)
        show_installed: Show only installed tools
        show_available: Show only available (not installed) tools
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    registry = _get_registry()

    if show_installed:
        tools = registry.list_installed()
        if json_output:
            data = [t.to_dict() for t in tools]
            print(json.dumps(data, indent=2))
        else:
            if not tools:
                print("No tools installed.")
                return 0
            print("Installed tools:")
            print()
            for tool in tools:
                status = "enabled" if tool.enabled else "disabled"
                risk = _format_risk(tool.risk_level)
                print(f"  {tool.name} v{tool.version}")
                print(f"    Status: {status} | Risk: {risk}")
                print(f"    Source: {tool.source}")
                if tool.description:
                    print(f"    {tool.description}")
                print()
    elif show_available:
        entries = registry.list_available()
        if json_output:
            data = [e.to_dict() for e in entries]
            print(json.dumps(data, indent=2))
        else:
            if not entries:
                print("All catalog tools are installed.")
                return 0
            print("Available tools (not installed):")
            print()
            for entry in entries:
                risk = _format_risk(entry.risk_level)
                print(f"  {entry.name} v{entry.version}")
                print(f"    Risk: {risk} | Types: {', '.join(entry.integration_types)}")
                if entry.description:
                    print(f"    {entry.description}")
                print()
    else:
        # Default: show all
        tools = registry.list_all()
        if json_output:
            data = [t.to_dict() for t in tools]
            print(json.dumps(data, indent=2))
        else:
            if not tools:
                print("No tools found.")
                return 0
            print("All tools:")
            print()
            for tool in tools:
                status = _format_status(tool.status)
                risk = _format_risk(tool.risk_level)
                print(f"  {tool.name} v{tool.version}")
                print(f"    Status: {status} | Risk: {risk}")
                if tool.description:
                    print(f"    {tool.description}")
                print()

    return 0


def cmd_status(name: str, json_output: bool = False) -> int:
    """Show detailed status for a tool.

    Args:
        name: Tool name
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    registry = _get_registry()

    try:
        info = registry.get_status(name)
    except ToolNotFoundError:
        print(f"Error: Tool '{name}' not found.", file=sys.stderr)
        return 1

    if json_output:
        data = info.to_dict()
        # Add health check if installed
        if info.installed:
            healthy, message = registry.check_health(name)
            data["health"] = {"healthy": healthy, "message": message}
        print(json.dumps(data, indent=2))
    else:
        print(f"Tool: {info.name}")
        print(f"Version: {info.version}")
        print(f"Status: {_format_status(info.status)}")
        print(f"Risk Level: {_format_risk(info.risk_level)}")
        print(f"Integration Types: {', '.join(info.integration_types)}")
        if info.description:
            print(f"Description: {info.description}")
        if info.source:
            print(f"Source: {info.source}")

        if info.installed:
            print()
            print("Installation Details:")
            print(f"  Installed At: {info.installed.installed_at}")
            print(f"  Manifest: {info.installed.manifest_path}")

            # Health check
            healthy, message = registry.check_health(name)
            health_status = "healthy" if healthy else "unhealthy"
            print()
            print(f"Health: {health_status}")
            if not healthy:
                print(f"  {message}")

        if info.catalog_entry:
            print()
            print("Catalog Information:")
            print(f"  Repository: {info.catalog_entry.repository}")
            if info.catalog_entry.homepage:
                print(f"  Homepage: {info.catalog_entry.homepage}")
            if info.catalog_entry.author:
                print(f"  Author: {info.catalog_entry.author}")
            if info.catalog_entry.deprecated:
                print(f"  DEPRECATED: {info.catalog_entry.deprecation_notice}")

    return 0


def cmd_install(
    source: str,
    enable: bool = False,
    yes: bool = False,
    json_output: bool = False,
) -> int:
    """Install a tool.

    Args:
        source: Tool source (path, URL, or catalog name)
        enable: Enable tool after install
        yes: Skip confirmation for high-risk tools
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    registry = _get_registry()

    # Check if it's a catalog tool and get risk level
    catalog = ToolCatalog()
    catalog_entry = catalog.get_entry(source)

    # Warn about high-risk tools
    if catalog_entry and catalog_entry.risk_level in ("high", "critical"):
        if not yes and not json_output:
            print(f"Warning: '{source}' is a {catalog_entry.risk_level}-risk tool.")
            print(f"  {catalog_entry.description}")
            print()
            confirm = input("Continue with installation? [y/N] ")
            if confirm.lower() not in ("y", "yes"):
                print("Installation cancelled.")
                return 1

    try:
        tool = registry.install(source, enabled=enable)
    except ToolAlreadyInstalledError:
        if json_output:
            print(json.dumps({"error": "already_installed", "name": source}))
        else:
            print(f"Error: Tool '{source}' is already installed.", file=sys.stderr)
        return 1
    except ToolNotFoundError as e:
        if json_output:
            print(json.dumps({"error": "not_found", "name": source, "message": str(e)}))
        else:
            print(f"Error: Tool not found: {e}", file=sys.stderr)
        return 1
    except ToolInstallError as e:
        if json_output:
            print(json.dumps({"error": "install_failed", "message": str(e)}))
        else:
            print(f"Error: Installation failed: {e}", file=sys.stderr)
        return 1

    if json_output:
        data = tool.to_dict()
        data["message"] = "installed"
        print(json.dumps(data, indent=2))
    else:
        status = "enabled" if tool.enabled else "disabled"
        print(f"Installed: {tool.name} v{tool.version}")
        print(f"Status: {status}")
        print(f"Source: {tool.source}")
        if not tool.enabled:
            print()
            print(f"Run 'mother tools enable {tool.name}' to enable this tool.")

    return 0


def cmd_uninstall(name: str, yes: bool = False, json_output: bool = False) -> int:
    """Uninstall a tool.

    Args:
        name: Tool name
        yes: Skip confirmation
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    registry = _get_registry()

    # Check if installed
    if not registry.is_installed(name):
        if json_output:
            print(json.dumps({"error": "not_installed", "name": name}))
        else:
            print(f"Error: Tool '{name}' is not installed.", file=sys.stderr)
        return 1

    # Confirm
    if not yes and not json_output:
        confirm = input(f"Uninstall '{name}'? This will remove all tool files. [y/N] ")
        if confirm.lower() not in ("y", "yes"):
            print("Uninstall cancelled.")
            return 1

    try:
        registry.uninstall(name)
    except ToolNotInstalledError:
        if json_output:
            print(json.dumps({"error": "not_installed", "name": name}))
        else:
            print(f"Error: Tool '{name}' is not installed.", file=sys.stderr)
        return 1

    if json_output:
        print(json.dumps({"message": "uninstalled", "name": name}))
    else:
        print(f"Uninstalled: {name}")

    return 0


def cmd_enable(name: str, json_output: bool = False) -> int:
    """Enable an installed tool.

    Args:
        name: Tool name
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    registry = _get_registry()

    try:
        registry.enable(name)
    except ToolNotInstalledError:
        if json_output:
            print(json.dumps({"error": "not_installed", "name": name}))
        else:
            print(f"Error: Tool '{name}' is not installed.", file=sys.stderr)
        return 1

    if json_output:
        print(json.dumps({"message": "enabled", "name": name}))
    else:
        print(f"Enabled: {name}")

    return 0


def cmd_disable(name: str, json_output: bool = False) -> int:
    """Disable an installed tool.

    Args:
        name: Tool name
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    registry = _get_registry()

    try:
        registry.disable(name)
    except ToolNotInstalledError:
        if json_output:
            print(json.dumps({"error": "not_installed", "name": name}))
        else:
            print(f"Error: Tool '{name}' is not installed.", file=sys.stderr)
        return 1

    if json_output:
        print(json.dumps({"message": "disabled", "name": name}))
    else:
        print(f"Disabled: {name}")

    return 0


def cmd_search(query: str, json_output: bool = False) -> int:
    """Search the tool catalog.

    Args:
        query: Search query
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    registry = _get_registry()
    results = registry.search_catalog(query)

    if json_output:
        data = [e.to_dict() for e in results]
        print(json.dumps(data, indent=2))
    else:
        if not results:
            print(f"No tools found matching '{query}'.")
            return 0

        print(f"Search results for '{query}':")
        print()
        for entry in results:
            risk = _format_risk(entry.risk_level)
            installed = registry.is_installed(entry.name)
            status = " [installed]" if installed else ""
            print(f"  {entry.name} v{entry.version}{status}")
            print(f"    Risk: {risk} | Types: {', '.join(entry.integration_types)}")
            if entry.description:
                print(f"    {entry.description}")
            print()

    return 0


def cmd_health(name: str, json_output: bool = False) -> int:
    """Check health of an installed tool.

    Args:
        name: Tool name
        json_output: Output as JSON

    Returns:
        Exit code (0 for success, 1 if unhealthy)
    """
    registry = _get_registry()

    if not registry.is_installed(name):
        if json_output:
            print(json.dumps({"error": "not_installed", "name": name}))
        else:
            print(f"Error: Tool '{name}' is not installed.", file=sys.stderr)
        return 1

    healthy, message = registry.check_health(name)

    if json_output:
        print(json.dumps({
            "name": name,
            "healthy": healthy,
            "message": message,
        }))
    else:
        if healthy:
            print(f"{name}: healthy")
        else:
            print(f"{name}: unhealthy")
            print(f"  {message}")

    return 0 if healthy else 1
