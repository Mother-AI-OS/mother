"""Status CLI command."""

import json

from .. import __version__
from ..config.settings import get_settings
from ..plugins import PluginConfig, PluginManager
from ..tools.registry import ToolRegistry


async def show_status(json_output: bool = False) -> int:
    """Show system status.

    Args:
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    settings = get_settings()

    # Initialize plugin manager
    plugin_config = PluginConfig()
    plugin_manager = PluginManager(plugin_config)
    plugin_manager.discover()
    await plugin_manager.load_all()

    # Initialize tool registry for legacy tools count
    registry = ToolRegistry(settings=settings, enable_plugins=False)

    # Gather status info
    status = {
        "version": __version__,
        "model": settings.claude_model,
        "api_host": settings.api_host,
        "api_port": settings.api_port,
        "legacy_tools": len(registry.wrappers),
        "plugins": len(plugin_manager.list_plugins()),
        "plugin_capabilities": len(plugin_manager),
        "plugins_list": list(plugin_manager.list_plugins().keys()),
        "legacy_tools_list": list(registry.wrappers.keys()),
    }

    if json_output:
        print(json.dumps(status, indent=2))
    else:
        print(f"\n{'=' * 50}")
        print(f"Mother AI OS v{__version__}")
        print(f"{'=' * 50}")
        print()
        print("Configuration:")
        print(f"  Model:    {status['model']}")
        print(f"  Server:   {status['api_host']}:{status['api_port']}")
        print()
        print("Tools:")
        print(
            f"  Legacy:   {status['legacy_tools']} ({', '.join(status['legacy_tools_list'][:5])}{'...' if len(status['legacy_tools_list']) > 5 else ''})"
        )
        print(f"  Plugins:  {status['plugins']} ({', '.join(status['plugins_list'])})")
        print(f"  Total capabilities: {status['plugin_capabilities']}")
        print()

        # Check for common issues
        issues = []
        if not settings.anthropic_api_key:
            issues.append("ANTHROPIC_API_KEY not set")
        if not settings.openai_api_key:
            issues.append("OPENAI_API_KEY not set (memory disabled)")

        if issues:
            print("Warnings:")
            for issue in issues:
                print(f"  \033[33m!\033[0m {issue}")
            print()

        print("Status: \033[32mReady\033[0m")
        print()

    await plugin_manager.shutdown()
    return 0
