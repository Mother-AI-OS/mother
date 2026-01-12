"""Built-in plugins for Mother AI OS.

This package contains plugins that ship with Mother and are always available.
Built-in plugins provide core functionality like filesystem access, shell
execution, and web fetching.

Plugins:
- filesystem: Read/write files, list directories, file operations
- shell: Execute shell commands, environment access, system info
- web: Fetch web pages, make HTTP requests, download files
- email: Read and send email via IMAP/SMTP
- pdf: PDF manipulation (merge, split, extract, rotate)
- datacraft: Document processing (parse, search, extract tables)
- tasks: Task management (add, list, complete, prioritize)
- transmit: Document transmission (email, fax, post, beA)
- taxlord: German tax and document management (optional)
- leads: German tender and lead generation (optional)
- google_docs: Google Docs template management (optional)
- tor: Tor network and darknet access (anonymous browsing, .onion sites)
- tor_shell: Shell command wrappers for darknet functionality
"""

from .datacraft import DatacraftPlugin
from .email import EmailPlugin
from .filesystem import FilesystemPlugin
from .german import LeadsPlugin, TaxlordPlugin
from .google import GoogleDocsPlugin
from .pdf import PDFPlugin
from .shell import ShellPlugin
from .tasks import TasksPlugin
from .tor import TorPlugin
from .tor_shell import TorShellPlugin
from .transmit import TransmitPlugin
from .web import WebPlugin

# Registry of built-in plugins
# Maps plugin name -> plugin class
BUILTIN_PLUGINS: dict[str, type] = {
    "filesystem": FilesystemPlugin,
    "shell": ShellPlugin,
    "web": WebPlugin,
    "email": EmailPlugin,
    "pdf": PDFPlugin,
    "datacraft": DatacraftPlugin,
    "tasks": TasksPlugin,
    "transmit": TransmitPlugin,
    "taxlord": TaxlordPlugin,
    "leads": LeadsPlugin,
    "google-docs": GoogleDocsPlugin,
    "tor": TorPlugin,
    "tor-shell": TorShellPlugin,
}


def get_builtin_plugin_classes() -> dict[str, type]:
    """Get all built-in plugin classes.

    Returns:
        Dict mapping plugin name to plugin class
    """
    return BUILTIN_PLUGINS.copy()


def get_builtin_plugin(name: str) -> type | None:
    """Get a specific built-in plugin class by name.

    Args:
        name: Plugin name

    Returns:
        Plugin class or None if not found
    """
    return BUILTIN_PLUGINS.get(name)


__all__ = [
    "DatacraftPlugin",
    "EmailPlugin",
    "FilesystemPlugin",
    "GoogleDocsPlugin",
    "LeadsPlugin",
    "PDFPlugin",
    "ShellPlugin",
    "TasksPlugin",
    "TaxlordPlugin",
    "TorPlugin",
    "TorShellPlugin",
    "TransmitPlugin",
    "WebPlugin",
    "BUILTIN_PLUGINS",
    "get_builtin_plugin_classes",
    "get_builtin_plugin",
]
