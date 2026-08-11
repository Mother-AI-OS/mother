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
- taxcraft: German tax and document management (optional)
- leads: German tender and lead generation (optional)
- mailcraft: AI-powered email management (categorization, triage, cleanup)
- mattercraft: Legal matter management with knowledge graph RAG
- taskcraft: AI-enhanced task management with value alignment and Google Tasks sync
- contentcraft: AI-powered content creation and multi-platform publishing
- longcraft: Persona-driven content generation with fine-tuning
- google_docs: Google Docs template management (optional)
- tor: Tor network and darknet access (anonymous browsing, .onion sites)
  — HIGH-RISK: registered but not enabled by default; blocked by safe_mode.
- tor_shell: Shell command wrappers for darknet functionality — HIGH-RISK, see tor.
- ssh: SSH access to remote VMs (command execution, file operations)
"""

from .taskcraft import TaskcraftPlugin
from .contentcraft import ContentcraftPlugin
from .datacraft import DatacraftPlugin
from .email import EmailPlugin
from .filesystem import FilesystemPlugin
from .german import LeadsPlugin, TaxCraftPlugin
from .google import GoogleDocsPlugin
from .longcraft import LongcraftPlugin
from .mailcraft import MailcraftPlugin
from .mattercraft import MattercraftPlugin
from .pdf import PDFPlugin
from .robin_plugin import RobinPlugin
from .shell import ShellPlugin
from .ssh import SSHPlugin
from .tasks import TasksPlugin
from .tor import TorPlugin
from .tor_shell import TorShellPlugin
from .transmit import TransmitPlugin
from .web import WebPlugin

# Registry of built-in plugins
# Maps plugin name -> plugin class
BUILTIN_PLUGINS: dict[str, type] = {
    "taskcraft": TaskcraftPlugin,
    "contentcraft": ContentcraftPlugin,
    "filesystem": FilesystemPlugin,
    "shell": ShellPlugin,
    "web": WebPlugin,
    "email": EmailPlugin,
    "pdf": PDFPlugin,
    "datacraft": DatacraftPlugin,
    "tasks": TasksPlugin,
    "transmit": TransmitPlugin,
    "taxcraft": TaxCraftPlugin,
    "leads": LeadsPlugin,
    "longcraft": LongcraftPlugin,
    "mailcraft": MailcraftPlugin,
    "mattercraft": MattercraftPlugin,
    "google-docs": GoogleDocsPlugin,
    # Tor / tor-shell are registered but high-risk: they are NOT in the default
    # enabled set (see explicitly_enabled_plugins in main.py) and safe_mode
    # (default True) blocks all high-risk capabilities, so they only run when a
    # user explicitly enables them. Keep them out of any default-enabled list.
    "tor": TorPlugin,
    "tor-shell": TorShellPlugin,
    # Dark web OSINT (vendored robin engine) is HIGH-RISK: risk_level=HIGH makes it
    # disabled-by-default, its robin_* capabilities are blocked by safe_mode (see the
    # ^robin_ pattern in policy/engine.py), and it is deliberately kept out of any
    # default-enabled list. It only runs when a user explicitly enables it.
    "darkweb-osint": RobinPlugin,
    "ssh": SSHPlugin,
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
    "TaskcraftPlugin",
    "ContentcraftPlugin",
    "DatacraftPlugin",
    "EmailPlugin",
    "FilesystemPlugin",
    "GoogleDocsPlugin",
    "LeadsPlugin",
    "LongcraftPlugin",
    "MailcraftPlugin",
    "MattercraftPlugin",
    "PDFPlugin",
    "RobinPlugin",
    "ShellPlugin",
    "SSHPlugin",
    "TasksPlugin",
    "TaxCraftPlugin",
    "TorPlugin",
    "TorShellPlugin",
    "TransmitPlugin",
    "WebPlugin",
    "BUILTIN_PLUGINS",
    "get_builtin_plugin_classes",
    "get_builtin_plugin",
]
