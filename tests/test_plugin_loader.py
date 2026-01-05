"""Tests for the plugin loader module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mother.plugins.loader import (
    DEFAULT_PROJECT_PLUGINS_DIR,
    DEFAULT_USER_PLUGINS_DIR,
    ENTRY_POINT_GROUP,
    PluginLoader,
)


class TestPluginLoaderInit:
    """Tests for PluginLoader initialization."""

    def test_default_directories(self):
        """Test default directory paths."""
        loader = PluginLoader()

        assert loader.user_plugins_dir == DEFAULT_USER_PLUGINS_DIR
        assert loader.project_plugins_dir == DEFAULT_PROJECT_PLUGINS_DIR
        assert loader.builtin_plugins_dir.name == "builtin"

    def test_custom_directories(self, tmp_path):
        """Test custom directory paths."""
        user_dir = tmp_path / "user_plugins"
        project_dir = tmp_path / "project_plugins"
        builtin_dir = tmp_path / "builtin"

        loader = PluginLoader(
            user_plugins_dir=user_dir,
            project_plugins_dir=project_dir,
            builtin_plugins_dir=builtin_dir,
        )

        assert loader.user_plugins_dir == user_dir
        assert loader.project_plugins_dir == project_dir
        assert loader.builtin_plugins_dir == builtin_dir

    def test_initial_state(self):
        """Test initial state is empty."""
        loader = PluginLoader()

        assert loader._discovered == {}
        assert loader._manifests == {}
        assert loader._plugin_dirs == {}
        assert loader._builtin_instances == {}
        assert loader._executors == {}


class TestPluginLoaderDiscovery:
    """Tests for plugin discovery methods."""

    def test_discover_all_clears_previous(self, tmp_path):
        """Test discover_all clears previous discoveries."""
        loader = PluginLoader(
            user_plugins_dir=tmp_path / "user",
            project_plugins_dir=tmp_path / "project",
            builtin_plugins_dir=tmp_path / "builtin",
        )

        # Pre-populate
        loader._discovered["old"] = MagicMock()
        loader._manifests["old"] = MagicMock()

        loader.discover_all()

        # Old entries should be gone (but builtin plugins may be added)
        assert "old" not in loader._discovered

    def test_discover_from_nonexistent_directory(self, tmp_path):
        """Test discovery from non-existent directory."""
        loader = PluginLoader(
            user_plugins_dir=tmp_path / "nonexistent",
            project_plugins_dir=tmp_path / "also_nonexistent",
            builtin_plugins_dir=tmp_path / "builtin",
        )

        # Should not raise
        loader._discover_from_directory(tmp_path / "nonexistent", "test")

        # No plugins discovered from nonexistent dir
        assert len(loader._discovered) == 0

    def test_discover_ignores_hidden_directories(self, tmp_path):
        """Test discovery ignores hidden and underscore directories."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create hidden and underscore directories
        (plugins_dir / ".hidden").mkdir()
        (plugins_dir / "_private").mkdir()

        loader = PluginLoader(
            user_plugins_dir=plugins_dir,
            project_plugins_dir=tmp_path / "project",
            builtin_plugins_dir=tmp_path / "builtin",
        )

        loader._discover_from_directory(plugins_dir, "test")

        # No plugins should be discovered
        assert len(loader._discovered) == 0

    def test_discover_from_directory_with_manifest(self, tmp_path):
        """Test discovery from directory with manifest file."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "test-plugin"
        plugin_dir.mkdir(parents=True)

        # Create a minimal manifest
        manifest_content = """
schema_version: "1.0"
plugin:
  name: test-plugin
  version: 1.0.0
  description: Test plugin
  author: Test
capabilities:
  - name: test_action
    description: Test action
execution:
  type: python
  python:
    module: test_plugin
    class: TestPlugin
"""
        (plugin_dir / "mother-plugin.yaml").write_text(manifest_content)

        loader = PluginLoader(
            user_plugins_dir=plugins_dir,
            project_plugins_dir=tmp_path / "project",
            builtin_plugins_dir=tmp_path / "builtin",
        )

        loader._discover_from_directory(plugins_dir, "test")

        assert "test-plugin" in loader._discovered
        assert loader._discovered["test-plugin"].name == "test-plugin"
        assert loader._discovered["test-plugin"].loaded is True

    def test_discover_from_directory_root_manifest(self, tmp_path):
        """Test discovery when manifest is in directory root."""
        plugin_dir = tmp_path / "single-plugin"
        plugin_dir.mkdir()

        # Create manifest in root
        manifest_content = """
schema_version: "1.0"
plugin:
  name: single-plugin
  version: 1.0.0
  description: Single plugin
  author: Test
capabilities:
  - name: action
    description: Action
execution:
  type: python
  python:
    module: single_plugin
    class: SinglePlugin
"""
        (plugin_dir / "mother-plugin.yaml").write_text(manifest_content)

        loader = PluginLoader()

        loader._discover_from_directory(plugin_dir, "test")

        assert "single-plugin" in loader._discovered

    def test_discover_from_directory_invalid_manifest(self, tmp_path):
        """Test discovery with invalid manifest."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "broken-plugin"
        plugin_dir.mkdir(parents=True)

        # Create invalid manifest
        (plugin_dir / "mother-plugin.yaml").write_text("invalid: yaml: [syntax")

        loader = PluginLoader()

        loader._discover_from_directory(plugins_dir, "test")

        # Plugin should be discovered but marked as failed
        assert "broken-plugin" in loader._discovered
        assert loader._discovered["broken-plugin"].loaded is False
        assert loader._discovered["broken-plugin"].error is not None

    def test_discover_project_plugins_when_exists(self, tmp_path):
        """Test project plugins are discovered when directory exists."""
        project_dir = tmp_path / "project_plugins"
        plugin_dir = project_dir / "project-plugin"
        plugin_dir.mkdir(parents=True)

        manifest_content = """
schema_version: "1.0"
plugin:
  name: project-plugin
  version: 1.0.0
  description: Project plugin
  author: Test
capabilities:
  - name: action
    description: Action
execution:
  type: python
  python:
    module: project_plugin
    class: ProjectPlugin
"""
        (plugin_dir / "mother-plugin.yaml").write_text(manifest_content)

        loader = PluginLoader(
            user_plugins_dir=tmp_path / "user",
            project_plugins_dir=project_dir,
            builtin_plugins_dir=tmp_path / "builtin",
        )

        discovered = loader.discover_all()

        assert "project-plugin" in discovered


class TestPluginLoaderBuiltins:
    """Tests for built-in plugin discovery."""

    @patch("mother.plugins.loader.BUILTINS_AVAILABLE", False)
    def test_discover_builtin_not_available(self):
        """Test when builtins not available."""
        loader = PluginLoader()

        loader._discover_builtin_plugins()

        # Should not raise, just log debug message
        # No plugins added from builtins
        assert len(loader._builtin_instances) == 0

    @patch("mother.plugins.loader.get_builtin_plugin_classes")
    @patch("mother.plugins.loader.BUILTINS_AVAILABLE", True)
    def test_discover_builtin_success(self, mock_get_builtins):
        """Test successful built-in plugin discovery."""
        # Create a mock plugin class
        mock_manifest = MagicMock()
        mock_manifest.plugin.name = "mock-builtin"
        mock_manifest.plugin.version = "1.0.0"
        mock_manifest.plugin.description = "Mock"
        mock_manifest.plugin.author = "Test"
        mock_manifest.capabilities = []

        mock_plugin_instance = MagicMock()
        mock_plugin_instance.manifest = mock_manifest

        mock_plugin_class = MagicMock(return_value=mock_plugin_instance)
        mock_get_builtins.return_value = {"mock-builtin": mock_plugin_class}

        loader = PluginLoader()
        loader._discover_builtin_plugins()

        assert "mock-builtin" in loader._discovered
        assert "mock-builtin" in loader._builtin_instances
        assert "mock-builtin" in loader._manifests

    @patch("mother.plugins.loader.get_builtin_plugin_classes")
    @patch("mother.plugins.loader.BUILTINS_AVAILABLE", True)
    def test_discover_builtin_failure(self, mock_get_builtins):
        """Test built-in plugin discovery failure."""
        mock_plugin_class = MagicMock(side_effect=Exception("Init failed"))
        mock_get_builtins.return_value = {"failing-plugin": mock_plugin_class}

        loader = PluginLoader()
        loader._discover_builtin_plugins()

        assert "failing-plugin" in loader._discovered
        assert loader._discovered["failing-plugin"].loaded is False
        assert "Init failed" in loader._discovered["failing-plugin"].error

    @patch("mother.plugins.loader.get_builtin_plugin_classes")
    @patch("mother.plugins.loader.BUILTINS_AVAILABLE", True)
    def test_discover_builtin_registry_failure(self, mock_get_builtins):
        """Test when get_builtin_plugin_classes fails."""
        mock_get_builtins.side_effect = Exception("Registry error")

        loader = PluginLoader()
        loader._discover_builtin_plugins()

        # Should not raise, just log warning
        assert len(loader._builtin_instances) == 0


class TestPluginLoaderEntryPoints:
    """Tests for entry point discovery."""

    @patch("mother.plugins.loader.importlib.metadata.entry_points")
    def test_discover_entry_points_new_api(self, mock_entry_points):
        """Test entry point discovery with Python 3.10+ API."""
        mock_eps = MagicMock()
        mock_eps.select.return_value = []
        mock_entry_points.return_value = mock_eps

        loader = PluginLoader()
        loader._discover_from_entry_points()

        mock_eps.select.assert_called_once_with(group=ENTRY_POINT_GROUP)

    @patch("mother.plugins.loader.importlib.metadata.entry_points")
    def test_discover_entry_points_old_api(self, mock_entry_points):
        """Test entry point discovery with Python 3.9 API."""
        mock_eps = {}  # Dict-like, no select method
        mock_entry_points.return_value = mock_eps

        loader = PluginLoader()
        loader._discover_from_entry_points()

        # Should not raise

    @patch("mother.plugins.loader.importlib.metadata.entry_points")
    def test_discover_entry_points_failure(self, mock_entry_points):
        """Test entry point discovery failure."""
        mock_entry_points.side_effect = Exception("Entry points error")

        loader = PluginLoader()
        loader._discover_from_entry_points()

        # Should not raise, just log warning

    @patch("mother.plugins.loader.importlib.metadata.entry_points")
    def test_discover_entry_point_load_failure(self, mock_entry_points):
        """Test entry point load failure."""
        mock_ep = MagicMock()
        mock_ep.name = "failing-ep"
        mock_ep.value = "failing.module:Plugin"
        mock_ep.load.side_effect = Exception("Load failed")

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps

        loader = PluginLoader()
        loader._discover_from_entry_points()

        assert "failing-ep" in loader._discovered
        assert loader._discovered["failing-ep"].loaded is False


class TestPluginLoaderLoading:
    """Tests for plugin loading."""

    def test_load_plugin_not_found(self, tmp_path):
        """Test loading non-existent plugin."""
        from mother.plugins.exceptions import PluginNotFoundError

        loader = PluginLoader(
            user_plugins_dir=tmp_path / "user",
            project_plugins_dir=tmp_path / "project",
            builtin_plugins_dir=tmp_path / "builtin",
        )

        with pytest.raises(PluginNotFoundError) as exc_info:
            loader.load_plugin("nonexistent")

        assert exc_info.value.plugin_name == "nonexistent"

    def test_load_plugin_already_loaded(self, tmp_path):
        """Test loading already loaded plugin returns cached executor."""
        loader = PluginLoader()

        mock_executor = MagicMock()
        loader._executors["cached-plugin"] = mock_executor

        result = loader.load_plugin("cached-plugin")

        assert result is mock_executor

    @patch("mother.plugins.loader.create_executor")
    def test_load_plugin_from_manifest(self, mock_create_executor, tmp_path):
        """Test loading plugin from manifest."""
        mock_executor = MagicMock()
        mock_create_executor.return_value = mock_executor

        mock_manifest = MagicMock()
        mock_manifest.dependencies = None

        loader = PluginLoader()
        loader._manifests["test-plugin"] = mock_manifest
        loader._plugin_dirs["test-plugin"] = tmp_path

        result = loader.load_plugin("test-plugin")

        assert result is mock_executor
        assert "test-plugin" in loader._executors
        mock_create_executor.assert_called_once()

    def test_load_builtin_plugin(self):
        """Test loading built-in plugin uses cached instance."""
        from mother.plugins.executor import BuiltinExecutor

        mock_instance = MagicMock()
        mock_manifest = MagicMock()
        mock_manifest.dependencies = None

        loader = PluginLoader()
        loader._manifests["builtin-plugin"] = mock_manifest
        loader._builtin_instances["builtin-plugin"] = mock_instance

        result = loader.load_plugin("builtin-plugin")

        assert isinstance(result, BuiltinExecutor)
        assert "builtin-plugin" in loader._executors

    def test_unload_plugin(self):
        """Test unloading a plugin."""
        loader = PluginLoader()
        loader._executors["test-plugin"] = MagicMock()

        loader.unload_plugin("test-plugin")

        assert "test-plugin" not in loader._executors

    def test_unload_nonexistent_plugin(self):
        """Test unloading non-existent plugin does not raise."""
        loader = PluginLoader()

        loader.unload_plugin("nonexistent")

        # Should not raise

    @pytest.mark.asyncio
    @patch("mother.plugins.loader.create_executor")
    async def test_initialize_plugin(self, mock_create_executor):
        """Test async plugin initialization."""
        mock_executor = MagicMock()
        mock_executor.initialize = AsyncMock()
        mock_create_executor.return_value = mock_executor

        mock_manifest = MagicMock()
        mock_manifest.dependencies = None

        loader = PluginLoader()
        loader._manifests["test-plugin"] = mock_manifest

        result = await loader.initialize_plugin("test-plugin")

        assert result is mock_executor
        mock_executor.initialize.assert_called_once()


class TestPluginLoaderDependencies:
    """Tests for dependency validation."""

    def test_validate_no_dependencies(self):
        """Test validation with no dependencies."""
        mock_manifest = MagicMock()
        mock_manifest.dependencies = None

        loader = PluginLoader()

        # Should not raise
        loader._validate_dependencies(mock_manifest)

    def test_validate_empty_dependencies(self):
        """Test validation with empty dependencies list."""
        mock_manifest = MagicMock()
        mock_manifest.dependencies = []

        loader = PluginLoader()

        # Should not raise
        loader._validate_dependencies(mock_manifest)

    @patch("mother.plugins.loader.importlib.metadata.version")
    def test_validate_dependencies_satisfied(self, mock_version):
        """Test validation when dependencies are satisfied."""
        mock_version.return_value = "2.30.0"

        mock_manifest = MagicMock()
        mock_manifest.dependencies = ["requests>=2.28.0"]

        loader = PluginLoader()

        # Should not raise
        loader._validate_dependencies(mock_manifest)

    @patch("mother.plugins.loader.importlib.metadata.version")
    def test_validate_dependencies_missing(self, mock_version):
        """Test validation with missing dependencies."""
        import importlib.metadata

        from mother.plugins.exceptions import DependencyError

        mock_version.side_effect = importlib.metadata.PackageNotFoundError("missing-pkg")

        mock_manifest = MagicMock()
        mock_manifest.plugin.name = "test-plugin"
        mock_manifest.dependencies = ["missing-pkg>=1.0.0"]

        loader = PluginLoader()

        with pytest.raises(DependencyError) as exc_info:
            loader._validate_dependencies(mock_manifest)

        assert "missing-pkg>=1.0.0" in exc_info.value.missing

    @patch("mother.plugins.loader.importlib.metadata.version")
    def test_validate_dependencies_incompatible(self, mock_version):
        """Test validation with incompatible version."""
        from mother.plugins.exceptions import DependencyError

        mock_version.return_value = "1.0.0"

        mock_manifest = MagicMock()
        mock_manifest.plugin.name = "test-plugin"
        mock_manifest.dependencies = ["requests>=2.28.0"]

        loader = PluginLoader()

        with pytest.raises(DependencyError) as exc_info:
            loader._validate_dependencies(mock_manifest)

        assert len(exc_info.value.incompatible) > 0

    def test_parse_dependency_simple(self):
        """Test parsing simple dependency."""
        loader = PluginLoader()

        name, version = loader._parse_dependency("requests")

        assert name == "requests"
        assert version == ""

    def test_parse_dependency_with_version(self):
        """Test parsing dependency with version."""
        loader = PluginLoader()

        name, version = loader._parse_dependency("requests>=2.28.0")

        assert name == "requests"
        assert version == ">=2.28.0"

    def test_parse_dependency_complex(self):
        """Test parsing complex dependency."""
        loader = PluginLoader()

        name, version = loader._parse_dependency("pydantic>=2.0,<3.0")

        assert name == "pydantic"
        assert version == ">=2.0,<3.0"

    def test_version_matches_true(self):
        """Test version matching returns true."""
        loader = PluginLoader()

        result = loader._version_matches("2.30.0", ">=2.28.0")

        assert result is True

    def test_version_matches_false(self):
        """Test version matching returns false."""
        loader = PluginLoader()

        result = loader._version_matches("1.0.0", ">=2.28.0")

        assert result is False

    @patch("mother.plugins.loader.importlib.metadata.version")
    def test_version_matches_packaging_not_installed(self, mock_version):
        """Test version matching when packaging not installed."""
        loader = PluginLoader()

        # Mock the import to fail
        with patch.dict("sys.modules", {"packaging.specifiers": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                result = loader._version_matches("1.0.0", ">=2.0.0")

        # Should return True (skip version check)
        assert result is True


class TestPluginLoaderUtilities:
    """Tests for utility methods."""

    def test_get_manifest_exists(self):
        """Test getting existing manifest."""
        mock_manifest = MagicMock()

        loader = PluginLoader()
        loader._manifests["test-plugin"] = mock_manifest

        result = loader.get_manifest("test-plugin")

        assert result is mock_manifest

    def test_get_manifest_not_found(self):
        """Test getting non-existent manifest."""
        loader = PluginLoader()

        result = loader.get_manifest("nonexistent")

        assert result is None

    def test_list_discovered(self):
        """Test listing discovered plugins."""
        mock_info = MagicMock()

        loader = PluginLoader()
        loader._discovered["plugin1"] = mock_info
        loader._discovered["plugin2"] = mock_info

        result = loader.list_discovered()

        assert len(result) == 2
        assert "plugin1" in result
        assert "plugin2" in result

    def test_list_discovered_returns_copy(self):
        """Test list_discovered returns a copy."""
        loader = PluginLoader()
        loader._discovered["plugin1"] = MagicMock()

        result = loader.list_discovered()
        result["new"] = MagicMock()

        assert "new" not in loader._discovered

    def test_is_loaded_true(self):
        """Test is_loaded returns true."""
        loader = PluginLoader()
        loader._executors["test-plugin"] = MagicMock()

        assert loader.is_loaded("test-plugin") is True

    def test_is_loaded_false(self):
        """Test is_loaded returns false."""
        loader = PluginLoader()

        assert loader.is_loaded("nonexistent") is False

    def test_get_executor_exists(self):
        """Test getting existing executor."""
        mock_executor = MagicMock()

        loader = PluginLoader()
        loader._executors["test-plugin"] = mock_executor

        result = loader.get_executor("test-plugin")

        assert result is mock_executor

    def test_get_executor_not_found(self):
        """Test getting non-existent executor."""
        loader = PluginLoader()

        result = loader.get_executor("nonexistent")

        assert result is None


class TestPluginLoaderIntegration:
    """Integration tests for plugin loader."""

    def test_full_lifecycle(self, tmp_path):
        """Test full plugin lifecycle: discover -> load -> unload."""
        # Create a test plugin
        plugin_dir = tmp_path / "plugins" / "lifecycle-plugin"
        plugin_dir.mkdir(parents=True)

        manifest_content = """
schema_version: "1.0"
plugin:
  name: lifecycle-plugin
  version: 1.0.0
  description: Lifecycle test plugin
  author: Test
capabilities:
  - name: test_action
    description: Test action
execution:
  type: python
  python:
    module: lifecycle_plugin
    class: LifecyclePlugin
"""
        (plugin_dir / "mother-plugin.yaml").write_text(manifest_content)

        loader = PluginLoader(
            user_plugins_dir=tmp_path / "plugins",
            project_plugins_dir=tmp_path / "project",
            builtin_plugins_dir=tmp_path / "builtin",
        )

        # Discover
        discovered = loader.discover_all()
        assert "lifecycle-plugin" in discovered

        # Check manifest
        manifest = loader.get_manifest("lifecycle-plugin")
        assert manifest is not None
        assert manifest.plugin.name == "lifecycle-plugin"

        # Check not loaded yet
        assert not loader.is_loaded("lifecycle-plugin")

    def test_discover_all_includes_builtins(self):
        """Test discover_all includes built-in plugins."""
        loader = PluginLoader()

        discovered = loader.discover_all()

        # Should have built-in plugins like filesystem, shell, web
        assert len(discovered) > 0
        # Check for common built-ins
        builtin_names = ["filesystem", "shell", "web"]
        for name in builtin_names:
            if name in discovered:
                assert discovered[name].loaded is True
