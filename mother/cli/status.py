"""Status CLI command."""

import importlib.util
import json

from .. import __version__
from ..config.settings import get_settings
from ..plugins import PluginConfig, PluginManager, resolve_enabled_plugins
from ..tools.registry import ToolRegistry


def _check_email_config() -> dict:
    """Check email configuration status."""
    from ..config.email_accounts import EmailAccountStore

    try:
        store = EmailAccountStore()
        accounts = store.list_accounts()
        default = store.get_default_account()
        return {
            "configured": len(accounts) > 0,
            "accounts": len(accounts),
            "default": default.email if default else None,
        }
    except Exception:
        return {"configured": False, "accounts": 0, "default": None}


def _check_optional_features() -> dict:
    """Report which optional extras of this package are installed.

    Only extras that actually gate a built-in capability belong here. This
    previously probed for two binaries that shipped with the author's private
    tooling and that no code in this package ever called, so it reported on
    software the user had no way to obtain.
    """
    features: dict[str, dict[str, bool]] = {}

    # The darkweb-osint plugin needs the "darkweb" extra (LangChain, bs4).
    features["darkweb"] = {
        "engine": importlib.util.find_spec("langchain_core") is not None,
    }

    return features


async def show_status(json_output: bool = False) -> int:
    """Show system status.

    Args:
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    settings = get_settings()

    # Initialize plugin manager
    plugin_config = PluginConfig(explicitly_enabled_plugins=resolve_enabled_plugins())
    plugin_manager = PluginManager(plugin_config)
    plugin_manager.discover()
    await plugin_manager.load_all()

    # Initialize tool registry for legacy tools count
    registry = ToolRegistry(settings=settings, enable_plugins=False)

    # Check feature status
    email_config = _check_email_config()
    optional_features = _check_optional_features()

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
        "email": email_config,
        "features": optional_features,
        "credentials": {
            "anthropic_api_key": bool(settings.anthropic_api_key),
            "openai_api_key": bool(settings.openai_api_key),
        },
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

        # Email status
        print("Email:")
        if email_config["configured"]:
            print(f"  \033[32m✓\033[0m {email_config['accounts']} account(s) configured")
            if email_config["default"]:
                print(f"    Default: {email_config['default']}")
        else:
            print("  \033[33m○\033[0m Not configured (run: mother email add)")
        print()

        # Tools status
        print("Plugins:")
        plugins_list = status["plugins_list"]
        print(
            f"  Built-in: {len(plugins_list)} ({', '.join(plugins_list[:8])}{'...' if len(plugins_list) > 8 else ''})"
        )
        print(f"  Total capabilities: {status['plugin_capabilities']}")

        if status["legacy_tools"] > 0:
            print()
            print("Legacy Tools (deprecated):")
            print(f"  \033[33m!\033[0m {status['legacy_tools']} ({', '.join(status['legacy_tools_list'])})")
        print()

        # Optional features
        print("Optional Features:")
        for category, tools in optional_features.items():
            enabled = [t for t, v in tools.items() if v]
            disabled = [t for t, v in tools.items() if not v]
            if enabled:
                print(f"  {category}: \033[32m✓\033[0m {', '.join(enabled)}")
            if disabled:
                print(f"  {category}: \033[90m○\033[0m {', '.join(disabled)} (not installed)")
        print()

        # Check for common issues
        issues = []
        if not settings.anthropic_api_key:
            issues.append("ANTHROPIC_API_KEY not set (run: mother setup)")
        if not settings.openai_api_key:
            issues.append("OPENAI_API_KEY not set (memory features disabled)")
        if not email_config["configured"]:
            issues.append("No email accounts (run: mother email add)")

        if issues:
            print("Setup Required:")
            for issue in issues:
                print(f"  \033[33m!\033[0m {issue}")
            print()
            print("Status: \033[33mPartially Ready\033[0m")
        else:
            print("Status: \033[32mReady\033[0m")
        print()

    await plugin_manager.shutdown()
    return 0
