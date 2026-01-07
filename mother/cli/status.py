"""Status CLI command."""

import json
from pathlib import Path

from .. import __version__
from ..config.settings import get_settings
from ..plugins import PluginConfig, PluginManager
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
    """Check status of optional features."""
    home = Path.home()
    features = {}

    # German legal tools (taxlord, leads)
    features["german_legal"] = {
        "taxlord": (home / ".local" / "bin" / "taxlord").exists()
        or (home / "projects" / "taxlord" / ".venv" / "bin" / "taxlord").exists(),
        "leads": (home / ".local" / "bin" / "leads").exists(),
    }

    # Google integration
    features["google"] = {
        "gcp_draft": (home / ".local" / "bin" / "gcp-draft").exists(),
    }

    # PDF tools
    features["pdf"] = {
        "pdf_merge": (home / ".local" / "bin" / "pdf-merge").exists(),
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
    plugin_config = PluginConfig()
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
        print(f"  Built-in: {len(plugins_list)} ({', '.join(plugins_list[:8])}{'...' if len(plugins_list) > 8 else ''})")
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
