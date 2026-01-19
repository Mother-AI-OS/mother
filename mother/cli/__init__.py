"""Mother AI OS CLI.

Provides command-line interface for managing Mother, including:
- Starting the server
- Managing plugins
- Managing email accounts
- Checking system status
- Initial setup wizard
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

    # setup command
    setup_parser = subparsers.add_parser(
        "setup",
        help="Run the setup wizard",
        description="Interactive first-time setup for Mother AI OS",
    )
    setup_parser.add_argument(
        "-q",
        "--quick",
        action="store_true",
        help="Quick setup (only required settings)",
    )
    setup_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output",
    )

    # email command
    email_parser = subparsers.add_parser(
        "email",
        help="Manage email accounts",
        description="Add, remove, and test email accounts for Mother",
    )
    email_subparsers = email_parser.add_subparsers(
        dest="email_command",
        help="Email commands",
    )

    # email add
    email_subparsers.add_parser(
        "add",
        help="Add a new email account (interactive)",
    )

    # email list
    email_subparsers.add_parser(
        "list",
        help="List all configured accounts",
    )

    # email remove
    email_remove = email_subparsers.add_parser(
        "remove",
        help="Remove an email account",
    )
    email_remove.add_argument("name", help="Account name to remove")
    email_remove.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")

    # email test
    email_test = email_subparsers.add_parser(
        "test",
        help="Test connection to an account",
    )
    email_test.add_argument("name", help="Account name to test")

    # email info
    email_info = email_subparsers.add_parser(
        "info",
        help="Show detailed account information",
    )
    email_info.add_argument("name", help="Account name")

    # email default
    email_default = email_subparsers.add_parser(
        "default",
        help="Set an account as the default",
    )
    email_default.add_argument("name", help="Account name to set as default")

    # credentials command
    credentials_parser = subparsers.add_parser(
        "credentials",
        help="Manage credentials",
        description="View and manage Mother credentials",
    )
    credentials_parser.add_argument(
        "credentials_args",
        nargs="*",
        help="Credentials subcommand and arguments",
    )

    # keys command
    keys_parser = subparsers.add_parser(
        "keys",
        help="Manage API keys",
        description="Add, list, revoke, and rotate API keys for multi-key authentication",
    )
    keys_subparsers = keys_parser.add_subparsers(
        dest="keys_command",
        help="Key management commands",
    )

    # keys init
    keys_init = keys_subparsers.add_parser(
        "init",
        help="Initialize the API key store",
    )
    keys_init.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # keys add
    keys_add = keys_subparsers.add_parser(
        "add",
        help="Create a new API key",
    )
    keys_add.add_argument(
        "name",
        help="Human-readable name for the key (must be unique)",
    )
    keys_add.add_argument(
        "--role",
        "-r",
        default="operator",
        choices=["admin", "operator", "readonly"],
        help="Role for the key (default: operator)",
    )
    keys_add.add_argument(
        "--scope",
        "-s",
        action="append",
        dest="scopes",
        help="Add a scope (can be used multiple times)",
    )
    keys_add.add_argument(
        "--expires",
        "-e",
        type=int,
        dest="expires_days",
        help="Number of days until expiration",
    )
    keys_add.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # keys list
    keys_list = keys_subparsers.add_parser(
        "list",
        help="List all API keys",
    )
    keys_list.add_argument(
        "--all",
        "-a",
        action="store_true",
        dest="include_revoked",
        help="Include revoked keys",
    )
    keys_list.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # keys info
    keys_info = keys_subparsers.add_parser(
        "info",
        help="Show detailed key information",
    )
    keys_info.add_argument(
        "identifier",
        help="Key ID or name",
    )
    keys_info.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # keys revoke
    keys_revoke = keys_subparsers.add_parser(
        "revoke",
        help="Revoke an API key",
    )
    keys_revoke.add_argument(
        "identifier",
        help="Key ID or name",
    )
    keys_revoke.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    keys_revoke.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # keys rotate
    keys_rotate = keys_subparsers.add_parser(
        "rotate",
        help="Rotate an API key (revoke old, create new)",
    )
    keys_rotate.add_argument(
        "identifier",
        help="Key ID or name",
    )
    keys_rotate.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    keys_rotate.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # keys delete
    keys_delete = keys_subparsers.add_parser(
        "delete",
        help="Permanently delete an API key",
    )
    keys_delete.add_argument(
        "identifier",
        help="Key ID or name",
    )
    keys_delete.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    keys_delete.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # doctor command
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check production readiness",
        description="Run comprehensive health checks for production deployment",
    )
    doctor_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed information for each check",
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new Mother instance",
        description="Generate deployment files (docker-compose, .env, policy templates)",
    )
    init_parser.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        default=".",
        help="Output directory (default: current directory)",
    )
    init_parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Skip Docker files",
    )
    init_parser.add_argument(
        "--no-policy",
        action="store_true",
        help="Skip policy template",
    )
    init_parser.add_argument(
        "--no-env",
        action="store_true",
        help="Skip .env.example",
    )
    init_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export configuration",
        description="Export current configuration to a portable archive",
    )
    export_parser.add_argument(
        "-o",
        "--output",
        default="mother-export.tar.gz",
        help="Output file path (default: mother-export.tar.gz)",
    )
    export_parser.add_argument(
        "--include-keys",
        action="store_true",
        help="Include API keys database (security sensitive!)",
    )
    export_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # import command
    import_parser = subparsers.add_parser(
        "import",
        help="Import configuration",
        description="Import configuration from an exported archive",
    )
    import_parser.add_argument(
        "archive",
        help="Path to the export archive",
    )
    import_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    import_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # tools command
    tools_parser = subparsers.add_parser(
        "tools",
        help="Manage external tools",
        description="Install, uninstall, enable, and disable external tool repositories",
    )
    tools_subparsers = tools_parser.add_subparsers(
        dest="tools_command",
        help="Tool management commands",
    )

    # tools list
    tools_list = tools_subparsers.add_parser(
        "list",
        help="List tools",
    )
    tools_list.add_argument(
        "--installed",
        action="store_true",
        help="Show only installed tools",
    )
    tools_list.add_argument(
        "--available",
        action="store_true",
        help="Show only available (not installed) tools",
    )
    tools_list.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # tools status
    tools_status = tools_subparsers.add_parser(
        "status",
        help="Show detailed tool status",
    )
    tools_status.add_argument(
        "name",
        help="Tool name",
    )
    tools_status.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # tools install
    tools_install = tools_subparsers.add_parser(
        "install",
        help="Install a tool",
    )
    tools_install.add_argument(
        "source",
        help="Tool source: local path, git URL, or catalog name",
    )
    tools_install.add_argument(
        "--enable",
        "-e",
        action="store_true",
        help="Enable tool after installation",
    )
    tools_install.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation for high-risk tools",
    )
    tools_install.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # tools uninstall
    tools_uninstall = tools_subparsers.add_parser(
        "uninstall",
        help="Uninstall a tool",
    )
    tools_uninstall.add_argument(
        "name",
        help="Tool name to uninstall",
    )
    tools_uninstall.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation",
    )
    tools_uninstall.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # tools enable
    tools_enable = tools_subparsers.add_parser(
        "enable",
        help="Enable an installed tool",
    )
    tools_enable.add_argument(
        "name",
        help="Tool name to enable",
    )
    tools_enable.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # tools disable
    tools_disable = tools_subparsers.add_parser(
        "disable",
        help="Disable an installed tool",
    )
    tools_disable.add_argument(
        "name",
        help="Tool name to disable",
    )
    tools_disable.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # tools search
    tools_search = tools_subparsers.add_parser(
        "search",
        help="Search the tool catalog",
    )
    tools_search.add_argument(
        "query",
        help="Search query",
    )
    tools_search.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # tools health
    tools_health = tools_subparsers.add_parser(
        "health",
        help="Check health of an installed tool",
    )
    tools_health.add_argument(
        "name",
        help="Tool name to check",
    )
    tools_health.add_argument(
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


def run_setup(args: argparse.Namespace) -> int:
    """Run setup wizard command."""
    from .setup import run_setup as do_setup

    return do_setup(
        skip_optional=args.quick,
        quiet=args.quiet,
    )


def run_email(args: argparse.Namespace) -> int:
    """Run email management commands."""
    from .email_cmd import cmd_add, cmd_default, cmd_info, cmd_list, cmd_remove, cmd_test

    if args.email_command == "add":
        return cmd_add()
    elif args.email_command == "list":
        return cmd_list()
    elif args.email_command == "remove":
        return cmd_remove(args.name, yes=args.yes)
    elif args.email_command == "test":
        return cmd_test(args.name)
    elif args.email_command == "info":
        return cmd_info(args.name)
    elif args.email_command == "default":
        return cmd_default(args.name)
    else:
        print("Usage: mother email <command>")
        print("Commands: add, list, remove, test, info, default")
        return 1


def run_credentials(args: argparse.Namespace) -> int:
    """Run credentials management commands."""
    # Pass the subcommand arguments to the credentials CLI
    import sys

    from ..credentials import main as credentials_main

    original_argv = sys.argv
    sys.argv = ["mother credentials"] + (args.credentials_args or [])
    try:
        credentials_main()
        return 0
    finally:
        sys.argv = original_argv


def run_keys(args: argparse.Namespace) -> int:
    """Run API key management commands."""
    from .keys import (
        cmd_add,
        cmd_delete,
        cmd_info,
        cmd_init,
        cmd_list,
        cmd_revoke,
        cmd_rotate,
    )

    if args.keys_command == "init":
        return cmd_init(json_output=args.json_output)
    elif args.keys_command == "add":
        return cmd_add(
            name=args.name,
            role=args.role,
            scopes=args.scopes,
            expires_days=args.expires_days,
            json_output=args.json_output,
        )
    elif args.keys_command == "list":
        return cmd_list(
            include_revoked=args.include_revoked,
            json_output=args.json_output,
        )
    elif args.keys_command == "info":
        return cmd_info(
            identifier=args.identifier,
            json_output=args.json_output,
        )
    elif args.keys_command == "revoke":
        return cmd_revoke(
            identifier=args.identifier,
            yes=args.yes,
            json_output=args.json_output,
        )
    elif args.keys_command == "rotate":
        return cmd_rotate(
            identifier=args.identifier,
            yes=args.yes,
            json_output=args.json_output,
        )
    elif args.keys_command == "delete":
        return cmd_delete(
            identifier=args.identifier,
            yes=args.yes,
            json_output=args.json_output,
        )
    else:
        print("Usage: mother keys <command>")
        print("Commands: init, add, list, info, revoke, rotate, delete")
        return 1


def run_doctor(args: argparse.Namespace) -> int:
    """Run doctor command."""
    from .doctor import cmd_doctor

    return cmd_doctor(
        verbose=args.verbose,
        json_output=args.json_output,
    )


def run_init(args: argparse.Namespace) -> int:
    """Run init command."""
    from .init_cmd import cmd_init

    return cmd_init(
        output_dir=args.output_dir,
        no_docker=args.no_docker,
        no_policy=args.no_policy,
        no_env=args.no_env,
        json_output=args.json_output,
    )


def run_export(args: argparse.Namespace) -> int:
    """Run export command."""
    from .init_cmd import cmd_export

    return cmd_export(
        output=args.output,
        include_keys=args.include_keys,
        json_output=args.json_output,
    )


def run_import(args: argparse.Namespace) -> int:
    """Run import command."""
    from .init_cmd import cmd_import

    return cmd_import(
        archive=args.archive,
        force=args.force,
        json_output=args.json_output,
    )


def run_tools(args: argparse.Namespace) -> int:
    """Run tools management commands."""
    from .tools_cmd import (
        cmd_disable,
        cmd_enable,
        cmd_health,
        cmd_install,
        cmd_list,
        cmd_search,
        cmd_status,
        cmd_uninstall,
    )

    if args.tools_command == "list":
        return cmd_list(
            show_installed=args.installed,
            show_available=args.available,
            json_output=args.json_output,
        )
    elif args.tools_command == "status":
        return cmd_status(
            name=args.name,
            json_output=args.json_output,
        )
    elif args.tools_command == "install":
        return cmd_install(
            source=args.source,
            enable=args.enable,
            yes=args.yes,
            json_output=args.json_output,
        )
    elif args.tools_command == "uninstall":
        return cmd_uninstall(
            name=args.name,
            yes=args.yes,
            json_output=args.json_output,
        )
    elif args.tools_command == "enable":
        return cmd_enable(
            name=args.name,
            json_output=args.json_output,
        )
    elif args.tools_command == "disable":
        return cmd_disable(
            name=args.name,
            json_output=args.json_output,
        )
    elif args.tools_command == "search":
        return cmd_search(
            query=args.query,
            json_output=args.json_output,
        )
    elif args.tools_command == "health":
        return cmd_health(
            name=args.name,
            json_output=args.json_output,
        )
    else:
        print("Usage: mother tools <command>")
        print("Commands: list, status, install, uninstall, enable, disable, search, health")
        return 1


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
        elif args.command == "setup":
            return run_setup(args)
        elif args.command == "email":
            return run_email(args)
        elif args.command == "credentials":
            return run_credentials(args)
        elif args.command == "keys":
            return run_keys(args)
        elif args.command == "doctor":
            return run_doctor(args)
        elif args.command == "init":
            return run_init(args)
        elif args.command == "export":
            return run_export(args)
        elif args.command == "import":
            return run_import(args)
        elif args.command == "tools":
            return run_tools(args)
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
