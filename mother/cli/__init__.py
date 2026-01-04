"""Mother AI OS CLI.

Provides command-line interface for managing Mother, including:
- Starting the server
- Managing plugins
- Checking system status
"""

import argparse
import asyncio
import sys

from .. import __version__


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="mother",
        description="Mother AI OS - AI Agent orchestrating CLI tools via natural language",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # serve command (default behavior)
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the Mother server",
        description="Start the FastAPI server for the Mother agent",
    )
    serve_parser.add_argument(
        "--host",
        default=None,
        help="Host to bind to (default: from settings)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: from settings)",
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    # plugin command
    plugin_parser = subparsers.add_parser(
        "plugin",
        help="Manage plugins",
        description="Discover, enable, disable, and inspect plugins",
    )
    plugin_subparsers = plugin_parser.add_subparsers(
        dest="plugin_command",
        help="Plugin commands",
    )

    # plugin list
    plugin_list = plugin_subparsers.add_parser(
        "list",
        help="List all available plugins",
    )
    plugin_list.add_argument(
        "--all",
        action="store_true",
        help="Include disabled plugins",
    )
    plugin_list.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # plugin info
    plugin_info = plugin_subparsers.add_parser(
        "info",
        help="Show detailed plugin information",
    )
    plugin_info.add_argument(
        "name",
        help="Plugin name",
    )
    plugin_info.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # plugin enable
    plugin_enable = plugin_subparsers.add_parser(
        "enable",
        help="Enable a plugin",
    )
    plugin_enable.add_argument(
        "name",
        help="Plugin name to enable",
    )

    # plugin disable
    plugin_disable = plugin_subparsers.add_parser(
        "disable",
        help="Disable a plugin",
    )
    plugin_disable.add_argument(
        "name",
        help="Plugin name to disable",
    )

    # plugin capabilities
    plugin_caps = plugin_subparsers.add_parser(
        "capabilities",
        help="List capabilities of a plugin or all plugins",
    )
    plugin_caps.add_argument(
        "name",
        nargs="?",
        help="Plugin name (optional, lists all if omitted)",
    )
    plugin_caps.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # plugin install
    plugin_install = plugin_subparsers.add_parser(
        "install",
        help="Install a plugin from PyPI",
    )
    plugin_install.add_argument(
        "package",
        help="Package name (e.g., 'mother-plugin-example' or 'mother-plugin-example==1.0.0')",
    )
    plugin_install.add_argument(
        "--upgrade",
        "-U",
        action="store_true",
        help="Upgrade package if already installed",
    )

    # plugin uninstall
    plugin_uninstall = plugin_subparsers.add_parser(
        "uninstall",
        help="Uninstall a plugin",
    )
    plugin_uninstall.add_argument(
        "package",
        help="Package name to uninstall",
    )
    plugin_uninstall.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )

    # plugin search
    plugin_search = plugin_subparsers.add_parser(
        "search",
        help="Search for plugins on PyPI",
    )
    plugin_search.add_argument(
        "query",
        nargs="?",
        default="mother-plugin",
        help="Search query (default: 'mother-plugin')",
    )

    # status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show system status",
        description="Display Mother system status and health",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    return parser


def run_serve(args: argparse.Namespace) -> int:
    """Run the server command."""
    from ..config.settings import get_settings
    from ..main import run as run_server

    settings = get_settings()

    # Override settings if provided
    if args.host:
        settings.api_host = args.host
    if args.port:
        settings.api_port = args.port

    run_server()
    return 0


def run_plugin(args: argparse.Namespace) -> int:
    """Run plugin commands."""
    from .plugin import (
        plugin_capabilities,
        plugin_disable,
        plugin_enable,
        plugin_info,
        plugin_install,
        plugin_list,
        plugin_search,
        plugin_uninstall,
    )

    if args.plugin_command == "list":
        return asyncio.run(
            plugin_list(
                show_all=args.all,
                json_output=args.json_output,
            )
        )
    elif args.plugin_command == "info":
        return asyncio.run(
            plugin_info(
                name=args.name,
                json_output=args.json_output,
            )
        )
    elif args.plugin_command == "enable":
        return asyncio.run(plugin_enable(name=args.name))
    elif args.plugin_command == "disable":
        return asyncio.run(plugin_disable(name=args.name))
    elif args.plugin_command == "capabilities":
        return asyncio.run(
            plugin_capabilities(
                name=args.name,
                json_output=args.json_output,
            )
        )
    elif args.plugin_command == "install":
        return plugin_install(
            package=args.package,
            upgrade=args.upgrade,
        )
    elif args.plugin_command == "uninstall":
        return plugin_uninstall(
            package=args.package,
            yes=args.yes,
        )
    elif args.plugin_command == "search":
        return asyncio.run(plugin_search(query=args.query))
    else:
        print("Usage: mother plugin <command>")
        print("Commands: list, info, enable, disable, capabilities, install, uninstall, search")
        return 1


def run_status(args: argparse.Namespace) -> int:
    """Run status command."""
    from .status import show_status

    return asyncio.run(show_status(json_output=args.json_output))


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Default to serve if no command given
    if args.command is None:
        args.command = "serve"
        args.host = None
        args.port = None
        args.reload = False

    try:
        if args.command == "serve":
            return run_serve(args)
        elif args.command == "plugin":
            return run_plugin(args)
        elif args.command == "status":
            return run_status(args)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
