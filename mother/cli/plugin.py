"""Plugin management CLI commands."""

import json
import subprocess
import sys
from pathlib import Path

from ..plugins import PluginConfig, PluginInfo, PluginManager


def _get_plugin_manager() -> PluginManager:
    """Create and initialize a plugin manager for CLI use."""
    config = PluginConfig(
        auto_discover=True,
        auto_load=False,  # Don't auto-load for CLI inspection
    )
    return PluginManager(config)


def _format_plugin_row(name: str, info: PluginInfo, loaded: bool = False) -> str:
    """Format a plugin as a table row."""
    status = "loaded" if loaded else ("ready" if info.loaded else "error")
    status_icon = {
        "loaded": "\033[32m●\033[0m",  # Green
        "ready": "\033[33m○\033[0m",  # Yellow
        "error": "\033[31m✗\033[0m",  # Red
    }.get(status, "?")

    caps = len(info.capabilities)
    version = info.version or "-"

    return f"  {status_icon} {name:<20} {version:<10} {caps:>3} capabilities"


def _print_table_header():
    """Print table header for plugin list."""
    print(f"  {'S':<1} {'Name':<20} {'Version':<10} {'Capabilities':>14}")
    print(f"  {'-' * 1} {'-' * 20} {'-' * 10} {'-' * 14}")


async def plugin_list(show_all: bool = False, json_output: bool = False) -> int:
    """List all available plugins.

    Args:
        show_all: Include disabled/errored plugins
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    manager = _get_plugin_manager()

    # Discover plugins
    discovered = manager.discover()

    # Load them to get full capability info
    await manager.load_all()

    loaded_plugins = manager.list_plugins()

    if json_output:
        output = {
            "plugins": [
                {
                    "name": name,
                    "version": info.version,
                    "description": info.description,
                    "author": info.author,
                    "capabilities": info.capabilities,
                    "loaded": name in loaded_plugins,
                    "error": info.error,
                }
                for name, info in discovered.items()
                if show_all or info.loaded
            ]
        }
        print(json.dumps(output, indent=2))
        return 0

    # Text output
    print("\nMother Plugins")
    print("=" * 50)

    if not discovered:
        print("\n  No plugins found.\n")
        return 0

    _print_table_header()

    for name, info in sorted(discovered.items()):
        if not show_all and not info.loaded:
            continue
        is_loaded = name in loaded_plugins
        print(_format_plugin_row(name, info, is_loaded))

    print()

    # Summary
    total = len(discovered)
    loaded = len([i for i in discovered.values() if i.loaded])
    errors = len([i for i in discovered.values() if i.error])

    print(f"  Total: {total} plugins, {loaded} loaded", end="")
    if errors:
        print(f", {errors} with errors", end="")
    print("\n")

    # Cleanup
    await manager.shutdown()

    return 0


async def plugin_info(name: str, json_output: bool = False) -> int:
    """Show detailed information about a plugin.

    Args:
        name: Plugin name
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    manager = _get_plugin_manager()

    # Discover and load
    manager.discover()

    try:
        await manager.load(name)
    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error loading plugin '{name}': {e}", file=sys.stderr)
        return 1

    info = manager.get_plugin_info(name)
    if not info:
        if json_output:
            print(json.dumps({"error": f"Plugin '{name}' not found"}))
        else:
            print(f"Plugin '{name}' not found.", file=sys.stderr)
        return 1

    # Get capabilities
    capabilities = manager.list_capabilities(name)

    if json_output:
        output = {
            "name": name,
            "version": info.version,
            "description": info.description,
            "author": info.author,
            "license": info.license,
            "source": info.source,
            "capabilities": [],
        }

        # Get detailed capability info
        for cap_name in capabilities:
            entry = manager.get_capability(cap_name)
            if entry:
                output["capabilities"].append(
                    {
                        "name": entry.capability_name,
                        "full_name": cap_name,
                        "description": entry.spec.description,
                        "confirmation_required": entry.confirmation_required,
                        "parameters": [
                            {
                                "name": p.name,
                                "type": p.type.value if hasattr(p.type, "value") else str(p.type),
                                "required": p.required,
                                "description": p.description,
                            }
                            for p in entry.spec.parameters
                        ],
                    }
                )

        print(json.dumps(output, indent=2))
    else:
        # Text output
        print(f"\n{'=' * 50}")
        print(f"Plugin: {name}")
        print(f"{'=' * 50}")
        print(f"  Version:     {info.version or '-'}")
        print(f"  Description: {info.description or '-'}")
        print(f"  Author:      {info.author or '-'}")
        print(f"  License:     {info.license or '-'}")
        print(f"  Source:      {info.source or '-'}")
        print()
        print(f"Capabilities ({len(capabilities)}):")
        print("-" * 50)

        for cap_name in capabilities:
            entry = manager.get_capability(cap_name)
            if entry:
                confirm = " [requires confirmation]" if entry.confirmation_required else ""
                print(f"  {entry.capability_name}{confirm}")
                if entry.spec.description:
                    # Wrap description
                    desc = entry.spec.description
                    if len(desc) > 60:
                        desc = desc[:57] + "..."
                    print(f"    {desc}")

        print()

    await manager.shutdown()
    return 0


async def plugin_enable(name: str) -> int:
    """Enable a plugin.

    Args:
        name: Plugin name to enable

    Returns:
        Exit code (0 for success)
    """
    config_path = Path.home() / ".config" / "mother" / "plugins.json"

    # Load existing config
    config = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except Exception:
            pass

    # Update disabled list
    disabled = config.get("disabled_plugins", [])
    if name in disabled:
        disabled.remove(name)
        config["disabled_plugins"] = disabled

        # Save config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        print(f"Plugin '{name}' enabled.")
        print("Restart the server for changes to take effect.")
    else:
        print(f"Plugin '{name}' is already enabled.")

    return 0


async def plugin_disable(name: str) -> int:
    """Disable a plugin.

    Args:
        name: Plugin name to disable

    Returns:
        Exit code (0 for success)
    """
    # Don't allow disabling built-in plugins
    builtin = ["filesystem", "shell", "web"]
    if name in builtin:
        print(f"Cannot disable built-in plugin '{name}'.", file=sys.stderr)
        return 1

    config_path = Path.home() / ".config" / "mother" / "plugins.json"

    # Load existing config
    config = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except Exception:
            pass

    # Update disabled list
    disabled = config.get("disabled_plugins", [])
    if name not in disabled:
        disabled.append(name)
        config["disabled_plugins"] = disabled

        # Save config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        print(f"Plugin '{name}' disabled.")
        print("Restart the server for changes to take effect.")
    else:
        print(f"Plugin '{name}' is already disabled.")

    return 0


async def plugin_capabilities(
    name: str | None = None,
    json_output: bool = False,
) -> int:
    """List capabilities of a plugin or all plugins.

    Args:
        name: Plugin name (optional, lists all if omitted)
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    manager = _get_plugin_manager()

    # Discover and load
    manager.discover()
    await manager.load_all()

    # Get capabilities
    if name:
        capabilities = manager.list_capabilities(name)
        if not capabilities:
            if json_output:
                print(json.dumps({"error": f"No capabilities found for '{name}'"}))
            else:
                print(f"No capabilities found for plugin '{name}'.", file=sys.stderr)
            await manager.shutdown()
            return 1
    else:
        capabilities = manager.list_capabilities()

    if json_output:
        output = {"capabilities": []}
        for cap_name in capabilities:
            entry = manager.get_capability(cap_name)
            if entry:
                output["capabilities"].append(
                    {
                        "name": cap_name,
                        "plugin": entry.plugin_name,
                        "capability": entry.capability_name,
                        "description": entry.spec.description,
                        "confirmation_required": entry.confirmation_required,
                    }
                )
        print(json.dumps(output, indent=2))
    else:
        # Group by plugin
        by_plugin: dict[str, list] = {}
        for cap_name in capabilities:
            entry = manager.get_capability(cap_name)
            if entry:
                if entry.plugin_name not in by_plugin:
                    by_plugin[entry.plugin_name] = []
                by_plugin[entry.plugin_name].append(entry)

        print(f"\nCapabilities ({len(capabilities)} total)")
        print("=" * 60)

        for plugin_name, entries in sorted(by_plugin.items()):
            print(f"\n{plugin_name} ({len(entries)})")
            print("-" * 40)
            for entry in entries:
                confirm = " *" if entry.confirmation_required else ""
                print(f"  {entry.capability_name}{confirm}")

        print("\n  * = requires confirmation\n")

    await manager.shutdown()
    return 0


def plugin_install(package: str, upgrade: bool = False) -> int:
    """Install a plugin from PyPI.

    Args:
        package: Package name (e.g., 'mother-plugin-example' or 'mother-plugin-example==1.0.0')
        upgrade: Whether to upgrade if already installed

    Returns:
        Exit code (0 for success)
    """
    print(f"\nInstalling plugin: {package}")
    print("-" * 40)

    # Build pip command
    cmd = [sys.executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.append(package)

    try:
        # Run pip install
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(result.stdout)
            print(f"\n\033[32m✓\033[0m Plugin '{package}' installed successfully.")
            print("Run 'mother plugin list' to see available plugins.")
            return 0
        else:
            print(result.stderr, file=sys.stderr)
            print(f"\n\033[31m✗\033[0m Failed to install '{package}'.", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def plugin_uninstall(package: str, yes: bool = False) -> int:
    """Uninstall a plugin.

    Args:
        package: Package name to uninstall
        yes: Skip confirmation prompt

    Returns:
        Exit code (0 for success)
    """
    # Don't allow uninstalling mother itself or built-in plugins
    protected = ["mother", "mother-ai-os"]
    if package.lower() in protected:
        print(f"Cannot uninstall '{package}' - it is a core package.", file=sys.stderr)
        return 1

    if not yes:
        print(f"This will uninstall the package '{package}'.")
        response = input("Continue? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("Cancelled.")
            return 0

    print(f"\nUninstalling: {package}")
    print("-" * 40)

    # Build pip command
    cmd = [sys.executable, "-m", "pip", "uninstall", "-y", package]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(result.stdout)
            print(f"\n\033[32m✓\033[0m Plugin '{package}' uninstalled.")
            return 0
        else:
            print(result.stderr, file=sys.stderr)
            print(f"\n\033[31m✗\033[0m Failed to uninstall '{package}'.", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


async def plugin_search(query: str = "mother-plugin") -> int:
    """Search for plugins on PyPI.

    Args:
        query: Search query (default: 'mother-plugin')

    Returns:
        Exit code (0 for success)
    """
    import urllib.error
    import urllib.request

    print(f"\nSearching PyPI for: {query}")
    print("-" * 50)

    # PyPI JSON API for package search
    # Note: PyPI's search API is deprecated, so we search for packages by prefix
    # using the simple API or by fetching known package patterns

    try:
        # Search using PyPI's JSON API for the specific package
        # This works well for exact matches or prefix searches
        url = f"https://pypi.org/pypi/{query}/json"

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
                info = data.get("info", {})
                print(f"\n  \033[32m●\033[0m {info.get('name', query)}")
                print(f"    Version: {info.get('version', 'unknown')}")
                print(f"    Summary: {info.get('summary', 'No description')}")
                print(f"    Author:  {info.get('author', 'unknown')}")
                print(f"    URL:     https://pypi.org/project/{query}/")
                print()
                print("Install with: mother plugin install", query)
                return 0

        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Package not found, try to search with pip
                pass
            else:
                raise

        # Fallback: use pip search alternatives
        # Since pip search is disabled, we'll suggest common patterns
        print("\n  No exact match found.")
        print("\n  Suggested searches:")
        print("    - mother-plugin-*  (community plugins)")
        print("    - mother-tools-*   (tool collections)")
        print()
        print("  Browse available packages at:")
        print("    https://pypi.org/search/?q=mother-plugin")
        print()

        return 0

    except Exception as e:
        print(f"Error searching PyPI: {e}", file=sys.stderr)
        return 1
