"""Built-in plugins for Mother AI OS.

This package contains plugins that ship with Mother and are always available.
Built-in plugins provide core functionality like filesystem access, shell
execution, and web fetching.

Plugins:
- filesystem: Read/write files, list directories, file operations
- shell: Execute shell commands, environment access, system info
- web: Fetch web pages, make HTTP requests, download files
"""

from .filesystem import FilesystemPlugin
from .shell import ShellPlugin
from .web import WebPlugin

# Registry of built-in plugins
# Maps plugin name -> plugin class
BUILTIN_PLUGINS: dict[str, type] = {
    "filesystem": FilesystemPlugin,
    "shell": ShellPlugin,
    "web": WebPlugin,
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
    "FilesystemPlugin",
    "ShellPlugin",
    "WebPlugin",
    "BUILTIN_PLUGINS",
    "get_builtin_plugin_classes",
    "get_builtin_plugin",
]
