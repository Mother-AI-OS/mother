"""Plugin discovery and loading for Mother AI OS.

This module handles discovering plugins from multiple sources:
1. Built-in plugins (mother/plugins/builtin/)
2. Entry points (pip-installed packages)
3. User plugins (~/.mother/plugins/)
4. Project plugins (.mother/plugins/)
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import PluginBase, PluginInfo
from .exceptions import (
    DependencyError,
    PluginNotFoundError,
)
from .executor import BuiltinExecutor, ExecutorBase, create_executor
from .manifest import (
    PluginManifest,
    find_manifest,
    load_manifest,
)

# Import built-in plugins registry
try:
    from .builtin import get_builtin_plugin_classes

    BUILTINS_AVAILABLE = True
except ImportError:
    BUILTINS_AVAILABLE = False

    def get_builtin_plugin_classes():
        return {}


if TYPE_CHECKING:
    pass

logger = logging.getLogger("mother.plugins.loader")

# Entry point group for Mother plugins
ENTRY_POINT_GROUP = "mother.plugins"

# Default plugin directories
DEFAULT_USER_PLUGINS_DIR = Path.home() / ".mother" / "plugins"
DEFAULT_PROJECT_PLUGINS_DIR = Path(".mother") / "plugins"


class PluginLoader:
    """Discovers and loads plugins from multiple sources.

    Discovery order (later sources override earlier):
    1. Built-in plugins
    2. Entry points (installed packages)
    3. User plugins directory
    4. Project plugins directory
    """

    def __init__(
        self,
        user_plugins_dir: Path | None = None,
        project_plugins_dir: Path | None = None,
        builtin_plugins_dir: Path | None = None,
    ):
        """Initialize the plugin loader.

        Args:
            user_plugins_dir: Directory for user plugins (default: ~/.mother/plugins)
            project_plugins_dir: Directory for project plugins (default: .mother/plugins)
            builtin_plugins_dir: Directory for built-in plugins (default: mother/plugins/builtin)
        """
        self.user_plugins_dir = user_plugins_dir or DEFAULT_USER_PLUGINS_DIR
        self.project_plugins_dir = project_plugins_dir or DEFAULT_PROJECT_PLUGINS_DIR
        self.builtin_plugins_dir = builtin_plugins_dir or (Path(__file__).parent / "builtin")

        self._discovered: dict[str, PluginInfo] = {}
        self._manifests: dict[str, PluginManifest] = {}
        self._plugin_dirs: dict[str, Path] = {}  # plugin name -> directory
        self._builtin_instances: dict[str, PluginBase] = {}  # built-in plugin instances
        self._executors: dict[str, ExecutorBase] = {}

    def discover_all(self) -> dict[str, PluginInfo]:
        """Discover all available plugins from all sources.

        Returns:
            Dict mapping plugin names to PluginInfo
        """
        self._discovered.clear()
        self._manifests.clear()
        self._plugin_dirs.clear()
        self._builtin_instances.clear()

        # 1. Built-in plugins (programmatic - from Python classes)
        self._discover_builtin_plugins()

        # 2. Built-in plugins (YAML manifests in builtin directory)
        self._discover_from_directory(self.builtin_plugins_dir, source="builtin")

        # 3. Entry points (installed packages)
        self._discover_from_entry_points()

        # 4. User plugins
        self._discover_from_directory(self.user_plugins_dir, source="user")

        # 5. Project plugins
        if self.project_plugins_dir.exists():
            self._discover_from_directory(self.project_plugins_dir, source="project")

        logger.info(f"Discovered {len(self._discovered)} plugins")
        return self._discovered.copy()

    def _discover_builtin_plugins(self) -> None:
        """Discover built-in plugins from the builtin registry.

        These are plugins with programmatic manifests (not YAML files).
        """
        if not BUILTINS_AVAILABLE:
            logger.debug("Built-in plugins registry not available")
            return

        try:
            builtin_classes = get_builtin_plugin_classes()
            for name, plugin_class in builtin_classes.items():
                try:
                    # Create instance to get manifest
                    instance = plugin_class()
                    manifest = instance.manifest

                    self._manifests[name] = manifest
                    self._builtin_instances[name] = instance
                    self._discovered[name] = PluginInfo.from_manifest(manifest, "builtin:programmatic")
                    logger.debug(f"Discovered built-in plugin: {name}")

                except Exception as e:
                    logger.warning(f"Failed to load built-in plugin {name}: {e}")
                    self._discovered[name] = PluginInfo.failed(name, "builtin:programmatic", str(e))

        except Exception as e:
            logger.warning(f"Failed to discover built-in plugins: {e}")

    def _discover_from_directory(
        self,
        directory: Path,
        source: str,
    ) -> None:
        """Discover plugins from a directory.

        Each subdirectory with a manifest file is treated as a plugin.
        Also supports single-file plugins with adjacent manifest.

        Args:
            directory: Directory to search
            source: Source identifier for logging
        """
        if not directory.exists():
            logger.debug(f"Plugin directory does not exist: {directory}")
            return

        logger.debug(f"Discovering plugins from {source}: {directory}")

        # Check for manifest in directory root (single plugin)
        root_manifest = find_manifest(directory)
        if root_manifest:
            self._load_manifest_info(root_manifest, source)
            return

        # Check subdirectories
        for item in directory.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith((".", "_")):
                continue

            manifest_path = find_manifest(item)
            if manifest_path:
                self._load_manifest_info(manifest_path, source)

    def _discover_from_entry_points(self) -> None:
        """Discover plugins from Python entry points."""
        try:
            eps = importlib.metadata.entry_points()

            # Python 3.10+ API
            if hasattr(eps, "select"):
                plugin_eps = eps.select(group=ENTRY_POINT_GROUP)
            else:
                # Python 3.9 fallback
                plugin_eps = eps.get(ENTRY_POINT_GROUP, [])

            for ep in plugin_eps:
                try:
                    # Entry point value should be a module with manifest
                    # or a PluginBase subclass
                    plugin_ref = ep.load()

                    if isinstance(plugin_ref, type) and issubclass(plugin_ref, PluginBase):
                        # Direct class reference - need manifest from module
                        module = importlib.import_module(ep.value.split(":")[0])
                        if hasattr(module, "MANIFEST"):
                            manifest = module.MANIFEST
                            self._manifests[ep.name] = manifest
                            self._discovered[ep.name] = PluginInfo.from_manifest(manifest, f"entry_point:{ep.value}")
                            logger.debug(f"Discovered entry point plugin: {ep.name}")
                    elif hasattr(plugin_ref, "get_manifest"):
                        # Module with get_manifest function
                        manifest = plugin_ref.get_manifest()
                        self._manifests[ep.name] = manifest
                        self._discovered[ep.name] = PluginInfo.from_manifest(manifest, f"entry_point:{ep.value}")
                        logger.debug(f"Discovered entry point plugin: {ep.name}")

                except Exception as e:
                    logger.warning(f"Failed to load entry point {ep.name}: {e}")
                    self._discovered[ep.name] = PluginInfo.failed(ep.name, f"entry_point:{ep.value}", str(e))

        except Exception as e:
            logger.warning(f"Failed to discover entry points: {e}")

    def _load_manifest_info(self, manifest_path: Path, source: str) -> None:
        """Load a manifest and register its info.

        Args:
            manifest_path: Path to manifest file
            source: Source identifier
        """
        try:
            manifest = load_manifest(manifest_path)
            name = manifest.plugin.name

            self._manifests[name] = manifest
            self._plugin_dirs[name] = manifest_path.parent  # Store plugin directory
            self._discovered[name] = PluginInfo.from_manifest(manifest, f"{source}:{manifest_path}")
            logger.debug(f"Discovered {source} plugin: {name}")

        except Exception as e:
            # Extract plugin name from directory
            plugin_name = manifest_path.parent.name
            logger.warning(f"Failed to load manifest {manifest_path}: {e}")
            self._discovered[plugin_name] = PluginInfo.failed(plugin_name, f"{source}:{manifest_path}", str(e))

    def get_manifest(self, plugin_name: str) -> PluginManifest | None:
        """Get a discovered plugin's manifest.

        Args:
            plugin_name: Name of the plugin

        Returns:
            PluginManifest or None if not found
        """
        return self._manifests.get(plugin_name)

    def load_plugin(
        self,
        plugin_name: str,
        config: dict[str, Any] | None = None,
    ) -> ExecutorBase:
        """Load and initialize a plugin.

        Args:
            plugin_name: Name of the plugin to load
            config: Plugin configuration values

        Returns:
            Initialized executor for the plugin

        Raises:
            PluginNotFoundError: If plugin not discovered
            DependencyError: If dependencies not satisfied
            PluginLoadError: If loading fails
        """
        # Check if already loaded
        if plugin_name in self._executors:
            return self._executors[plugin_name]

        # Get manifest
        manifest = self._manifests.get(plugin_name)
        if not manifest:
            raise PluginNotFoundError(
                plugin_name,
                searched_locations=[
                    str(self.builtin_plugins_dir),
                    ENTRY_POINT_GROUP,
                    str(self.user_plugins_dir),
                    str(self.project_plugins_dir),
                ],
            )

        # Validate dependencies
        self._validate_dependencies(manifest)

        # Check if this is a built-in plugin with a pre-created instance
        if plugin_name in self._builtin_instances:
            instance = self._builtin_instances[plugin_name]
            executor = BuiltinExecutor(instance, manifest)
            self._executors[plugin_name] = executor
            logger.info(f"Loaded built-in plugin: {plugin_name}")
            return executor

        # Get plugin directory for local loading
        plugin_dir = self._plugin_dirs.get(plugin_name)

        # Create executor
        executor = create_executor(manifest, config, plugin_dir)

        # Store reference
        self._executors[plugin_name] = executor

        logger.info(f"Loaded plugin: {plugin_name}")
        return executor

    async def initialize_plugin(
        self,
        plugin_name: str,
        config: dict[str, Any] | None = None,
    ) -> ExecutorBase:
        """Load and initialize a plugin asynchronously.

        Args:
            plugin_name: Name of the plugin
            config: Plugin configuration

        Returns:
            Initialized executor
        """
        executor = self.load_plugin(plugin_name, config)
        await executor.initialize()
        return executor

    def unload_plugin(self, plugin_name: str) -> None:
        """Unload a plugin and release resources.

        Args:
            plugin_name: Name of the plugin to unload
        """
        if plugin_name in self._executors:
            del self._executors[plugin_name]
            logger.info(f"Unloaded plugin: {plugin_name}")

    def _validate_dependencies(self, manifest: PluginManifest) -> None:
        """Validate that all plugin dependencies are installed.

        Args:
            manifest: Plugin manifest

        Raises:
            DependencyError: If dependencies not satisfied
        """
        if not manifest.dependencies:
            return

        missing: list[str] = []
        incompatible: list[tuple[str, str, str]] = []

        for dep_str in manifest.dependencies:
            # Parse dependency string (e.g., "requests>=2.28.0")
            name, required_version = self._parse_dependency(dep_str)

            try:
                installed_version = importlib.metadata.version(name)

                if required_version and not self._version_matches(installed_version, required_version):
                    incompatible.append((name, installed_version, required_version))

            except importlib.metadata.PackageNotFoundError:
                missing.append(dep_str)

        if missing or incompatible:
            raise DependencyError(
                manifest.plugin.name,
                missing=missing,
                incompatible=incompatible,
            )

    def _parse_dependency(self, dep_str: str) -> tuple[str, str]:
        """Parse a dependency string into name and version spec.

        Args:
            dep_str: e.g., "requests>=2.28.0" or "pydantic"

        Returns:
            Tuple of (name, version_spec)
        """
        import re

        match = re.match(r"^([a-zA-Z0-9_-]+)(.*)$", dep_str)
        if not match:
            return dep_str, ""
        return match.group(1), match.group(2)

    def _version_matches(self, installed: str, required: str) -> bool:
        """Check if installed version matches requirement.

        Args:
            installed: Installed version string
            required: Version specifier (e.g., ">=2.28.0")

        Returns:
            True if version satisfies requirement
        """
        try:
            from packaging.specifiers import SpecifierSet

            spec = SpecifierSet(required)
            return installed in spec
        except ImportError:
            # packaging not installed, skip version check
            logger.debug("packaging not installed, skipping version check")
            return True
        except Exception:
            return True

    def list_discovered(self) -> dict[str, PluginInfo]:
        """Get all discovered plugins.

        Returns:
            Dict mapping plugin names to PluginInfo
        """
        return self._discovered.copy()

    def is_loaded(self, plugin_name: str) -> bool:
        """Check if a plugin is loaded.

        Args:
            plugin_name: Name of the plugin

        Returns:
            True if plugin is loaded
        """
        return plugin_name in self._executors

    def get_executor(self, plugin_name: str) -> ExecutorBase | None:
        """Get a loaded plugin's executor.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Executor or None if not loaded
        """
        return self._executors.get(plugin_name)
