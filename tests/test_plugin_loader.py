"""Tests for PluginLoader."""

import tempfile
from pathlib import Path

import pytest

from mother.plugins.loader import (
    DEFAULT_PROJECT_PLUGINS_DIR,
    DEFAULT_USER_PLUGINS_DIR,
    PluginLoader,
)


class TestPluginLoader:
    """Tests for PluginLoader."""

    def test_loader_creation_defaults(self) -> None:
        """Test creating loader with default directories."""
        loader = PluginLoader()

        assert loader.user_plugins_dir == DEFAULT_USER_PLUGINS_DIR
        assert loader.project_plugins_dir == DEFAULT_PROJECT_PLUGINS_DIR
        assert loader.builtin_plugins_dir is not None

    def test_loader_creation_custom_dirs(self) -> None:
        """Test creating loader with custom directories."""
        user_dir = Path("/custom/user")
        project_dir = Path("/custom/project")
        builtin_dir = Path("/custom/builtin")

        loader = PluginLoader(
            user_plugins_dir=user_dir,
            project_plugins_dir=project_dir,
            builtin_plugins_dir=builtin_dir,
        )

        assert loader.user_plugins_dir == user_dir
        assert loader.project_plugins_dir == project_dir
        assert loader.builtin_plugins_dir == builtin_dir

    def test_discover_all_returns_dict(self) -> None:
        """Test that discover_all returns a dictionary."""
        loader = PluginLoader()
        discovered = loader.discover_all()

        assert isinstance(discovered, dict)

    def test_discover_all_finds_builtin(self) -> None:
        """Test that discover_all finds built-in plugins."""
        loader = PluginLoader()
        discovered = loader.discover_all()

        # Should find filesystem plugin at minimum
        assert "filesystem" in discovered

    def test_discover_all_builtin_info(self) -> None:
        """Test that discovered builtin has correct info."""
        loader = PluginLoader()
        discovered = loader.discover_all()

        if "filesystem" in discovered:
            info = discovered["filesystem"]
            assert info.name == "filesystem"
            assert info.version is not None
            # Source includes type information (e.g., "builtin:programmatic")
            assert info.source.startswith("builtin")

    def test_get_manifest_before_discover(self) -> None:
        """Test getting manifest before discovery."""
        loader = PluginLoader()

        manifest = loader.get_manifest("nonexistent")
        assert manifest is None

    def test_get_manifest_after_discover(self) -> None:
        """Test getting manifest after discovery."""
        loader = PluginLoader()
        loader.discover_all()

        manifest = loader.get_manifest("filesystem")
        assert manifest is not None
        assert manifest.plugin.name == "filesystem"

    def test_get_plugin_dir_builtin(self) -> None:
        """Test getting plugin directory for builtin."""
        loader = PluginLoader()
        loader.discover_all()

        # Builtin plugins may not have a directory (programmatic ones)
        # The method returns the stored directory path
        plugin_dir = loader._plugin_dirs.get("filesystem")
        # Can be None for builtin programmatic plugins
        assert plugin_dir is None or isinstance(plugin_dir, Path)

    def test_get_plugin_dir_nonexistent(self) -> None:
        """Test getting plugin directory for nonexistent plugin."""
        loader = PluginLoader()

        plugin_dir = loader._plugin_dirs.get("nonexistent")
        assert plugin_dir is None

    def test_is_loaded_false(self) -> None:
        """Test is_loaded returns False initially."""
        loader = PluginLoader()

        assert loader.is_loaded("filesystem") is False

    def test_get_executor_before_load(self) -> None:
        """Test getting executor before loading."""
        loader = PluginLoader()

        executor = loader.get_executor("filesystem")
        assert executor is None

    def test_discover_empty_directory(self) -> None:
        """Test discovering from empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = PluginLoader(
                user_plugins_dir=Path(tmpdir) / "user",
                project_plugins_dir=Path(tmpdir) / "project",
            )
            discovered = loader.discover_all()

            # Should still find builtin plugins
            assert "filesystem" in discovered

    def test_list_discovered_plugins(self) -> None:
        """Test listing discovered plugins."""
        loader = PluginLoader()
        loader.discover_all()

        # Check that discovered dict has entries
        assert len(loader._discovered) > 0

    def test_unload_not_loaded(self) -> None:
        """Test unloading a plugin that's not loaded."""
        loader = PluginLoader()

        # Should not raise
        loader.unload_plugin("nonexistent")

    def test_unload_after_discover(self) -> None:
        """Test unloading a discovered but not loaded plugin."""
        loader = PluginLoader()
        loader.discover_all()

        # Should not raise
        loader.unload_plugin("filesystem")

    @pytest.mark.asyncio
    async def test_initialize_plugin_builtin(self) -> None:
        """Test initializing a builtin plugin."""
        loader = PluginLoader()
        loader.discover_all()

        executor = await loader.initialize_plugin("filesystem", {})

        assert executor is not None
        assert loader.is_loaded("filesystem") is True
        assert loader.get_executor("filesystem") is executor

    @pytest.mark.asyncio
    async def test_initialize_plugin_not_found(self) -> None:
        """Test initializing a non-existent plugin."""
        from mother.plugins.exceptions import PluginNotFoundError

        loader = PluginLoader()
        loader.discover_all()

        with pytest.raises(PluginNotFoundError):
            await loader.initialize_plugin("nonexistent", {})


class TestPluginLoaderUserPlugins:
    """Tests for user plugin discovery."""

    def test_discover_user_plugin_yaml(self) -> None:
        """Test discovering a plugin from YAML manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "my-plugin"
            plugin_dir.mkdir()

            manifest_path = plugin_dir / "mother-plugin.yaml"
            manifest_path.write_text("""
schema_version: "1.0"
plugin:
  name: my-plugin
  version: 1.0.0
  description: Test plugin
  author: Test
capabilities:
  - name: test
    description: Test action
execution:
  type: python
  python:
    module: my_plugin
    class: MyPlugin
""")

            loader = PluginLoader(user_plugins_dir=Path(tmpdir))
            discovered = loader.discover_all()

            assert "my-plugin" in discovered
            info = discovered["my-plugin"]
            assert info.name == "my-plugin"
            assert info.version == "1.0.0"
            # Source includes the path (e.g., "user:/path/to/manifest.yaml")
            assert info.source.startswith("user")

    def test_discover_multiple_user_plugins(self) -> None:
        """Test discovering multiple user plugins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["plugin-a", "plugin-b"]:
                plugin_dir = Path(tmpdir) / name
                plugin_dir.mkdir()

                manifest_path = plugin_dir / "mother-plugin.yaml"
                manifest_path.write_text(f"""
schema_version: "1.0"
plugin:
  name: {name}
  version: 1.0.0
  description: Test {name}
  author: Test
capabilities:
  - name: action
    description: Action
execution:
  type: python
  python:
    module: {name.replace("-", "_")}
    class: Plugin
""")

            loader = PluginLoader(user_plugins_dir=Path(tmpdir))
            discovered = loader.discover_all()

            assert "plugin-a" in discovered
            assert "plugin-b" in discovered
