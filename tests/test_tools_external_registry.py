"""Tests for the external tool registry module."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest
import yaml

from mother.tools.catalog import ToolCatalog
from mother.tools.exceptions import (
    ToolAlreadyInstalledError,
    ToolInstallError,
    ToolNotFoundError,
    ToolNotInstalledError,
)
from mother.tools.external_registry import (
    ExternalToolRegistry,
    InstallSource,
    ToolInfo,
    ToolStatus,
)
from mother.tools.store import ToolStore


@pytest.fixture
def temp_registry():
    """Create a temporary registry for testing."""
    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        store_path = tmpdir_path / "store" / "tools.json"
        tools_dir = tmpdir_path / "tools"

        # Create catalog with test entries
        catalog_path = tmpdir_path / "catalog.yaml"
        catalog_data = {
            "version": "1.0",
            "tools": [
                {
                    "name": "test-catalog-tool",
                    "description": "A tool from catalog",
                    "repository": "https://github.com/test/repo",
                    "version": "1.0.0",
                    "risk_level": "low",
                    "integration_types": ["cli"],
                },
                {
                    "name": "high-risk-catalog-tool",
                    "description": "A high risk tool",
                    "repository": "https://github.com/test/highrisk",
                    "version": "1.0.0",
                    "risk_level": "high",
                    "integration_types": ["python"],
                },
            ],
        }
        with open(catalog_path, "w") as f:
            yaml.dump(catalog_data, f)

        store = ToolStore(store_path=store_path)
        catalog = ToolCatalog(catalog_path=catalog_path)

        registry = ExternalToolRegistry(
            store=store,
            catalog=catalog,
            tools_dir=tools_dir,
        )

        yield registry, tmpdir_path


@pytest.fixture
def sample_tool_dir():
    """Create a sample tool directory with manifest."""
    with TemporaryDirectory() as tmpdir:
        manifest_data = {
            "schema_version": "1.0",
            "tool": {
                "name": "sample-local-tool",
                "version": "1.0.0",
                "description": "A sample local tool",
            },
            "integration": {
                "type": "cli",
                "cli": {"binary": "sample-tool"},
            },
        }

        manifest_path = Path(tmpdir) / "mother-tool.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f)

        yield Path(tmpdir)


class TestInstallSource:
    """Tests for InstallSource enum and parsing."""

    def test_parse_local_explicit(self, temp_registry):
        """Test parsing explicit local source."""
        registry, _ = temp_registry
        source_type, path = registry._parse_source("local:/path/to/tool")

        assert source_type == InstallSource.LOCAL
        assert path == "/path/to/tool"

    def test_parse_local_implicit_absolute(self, temp_registry):
        """Test parsing implicit local source from absolute path."""
        registry, _ = temp_registry
        source_type, path = registry._parse_source("/path/to/tool")

        assert source_type == InstallSource.LOCAL
        assert path == "/path/to/tool"

    def test_parse_local_implicit_relative(self, temp_registry):
        """Test parsing implicit local source from relative path."""
        registry, _ = temp_registry
        source_type, path = registry._parse_source("./path/to/tool")

        assert source_type == InstallSource.LOCAL
        assert path == "./path/to/tool"

    def test_parse_local_implicit_home(self, temp_registry):
        """Test parsing implicit local source from home path."""
        registry, _ = temp_registry
        source_type, path = registry._parse_source("~/projects/tool")

        assert source_type == InstallSource.LOCAL
        assert path == "~/projects/tool"

    def test_parse_git_explicit(self, temp_registry):
        """Test parsing explicit git source."""
        registry, _ = temp_registry
        source_type, url = registry._parse_source("git:https://github.com/org/repo")

        assert source_type == InstallSource.GIT
        assert url == "https://github.com/org/repo"

    def test_parse_git_implicit_https(self, temp_registry):
        """Test parsing implicit git source from HTTPS URL."""
        registry, _ = temp_registry
        source_type, url = registry._parse_source("https://github.com/org/repo")

        assert source_type == InstallSource.GIT
        assert url == "https://github.com/org/repo"

    def test_parse_git_implicit_ssh(self, temp_registry):
        """Test parsing implicit git source from SSH URL."""
        registry, _ = temp_registry
        source_type, url = registry._parse_source("git@github.com:org/repo.git")

        assert source_type == InstallSource.GIT
        assert url == "git@github.com:org/repo.git"

    def test_parse_catalog_explicit(self, temp_registry):
        """Test parsing explicit catalog source."""
        registry, _ = temp_registry
        source_type, name = registry._parse_source("catalog:contentcraft")

        assert source_type == InstallSource.CATALOG
        assert name == "contentcraft"

    def test_parse_catalog_implicit(self, temp_registry):
        """Test parsing implicit catalog source from name."""
        registry, _ = temp_registry
        source_type, name = registry._parse_source("contentcraft")

        assert source_type == InstallSource.CATALOG
        assert name == "contentcraft"


class TestExternalToolRegistry:
    """Tests for ExternalToolRegistry class."""

    def test_list_all_empty(self, temp_registry):
        """Test listing when no tools installed."""
        registry, _ = temp_registry

        tools = registry.list_all()

        # Should have catalog entries only
        assert len(tools) >= 2
        names = [t.name for t in tools]
        assert "test-catalog-tool" in names
        assert "high-risk-catalog-tool" in names

        # All should be not installed
        for tool in tools:
            assert tool.status == ToolStatus.NOT_INSTALLED

    def test_list_installed_empty(self, temp_registry):
        """Test listing installed when none installed."""
        registry, _ = temp_registry
        installed = registry.list_installed()
        assert installed == []

    def test_list_available(self, temp_registry):
        """Test listing available tools."""
        registry, _ = temp_registry
        available = registry.list_available()

        assert len(available) >= 2
        names = [e.name for e in available]
        assert "test-catalog-tool" in names

    def test_install_from_local(self, temp_registry, sample_tool_dir):
        """Test installing from local path."""
        registry, _ = temp_registry

        tool = registry.install(str(sample_tool_dir))

        assert tool.name == "sample-local-tool"
        assert tool.version == "1.0.0"
        assert tool.enabled is False
        assert tool.source.startswith("local:")
        assert registry.is_installed("sample-local-tool")

    def test_install_from_local_enabled(self, temp_registry, sample_tool_dir):
        """Test installing from local path with enabled=True."""
        registry, _ = temp_registry

        tool = registry.install(str(sample_tool_dir), enabled=True)

        assert tool.enabled is True
        assert registry.is_enabled("sample-local-tool")

    def test_install_already_installed(self, temp_registry, sample_tool_dir):
        """Test installing an already installed tool."""
        registry, _ = temp_registry

        registry.install(str(sample_tool_dir))

        with pytest.raises(ToolAlreadyInstalledError):
            registry.install(str(sample_tool_dir))

    def test_install_nonexistent_path(self, temp_registry):
        """Test installing from non-existent path."""
        registry, _ = temp_registry

        with pytest.raises(ToolInstallError):
            registry.install("/nonexistent/path")

    def test_install_no_manifest(self, temp_registry):
        """Test installing from path without manifest."""
        registry, tmpdir = temp_registry

        # Create empty directory
        empty_dir = tmpdir / "empty"
        empty_dir.mkdir()

        with pytest.raises(ToolInstallError) as exc_info:
            registry.install(str(empty_dir))
        assert "mother-tool.yaml" in str(exc_info.value)

    def test_uninstall(self, temp_registry, sample_tool_dir):
        """Test uninstalling a tool."""
        registry, _ = temp_registry

        registry.install(str(sample_tool_dir))
        assert registry.is_installed("sample-local-tool")

        registry.uninstall("sample-local-tool")
        assert not registry.is_installed("sample-local-tool")

    def test_uninstall_not_installed(self, temp_registry):
        """Test uninstalling a non-installed tool."""
        registry, _ = temp_registry

        with pytest.raises(ToolNotInstalledError):
            registry.uninstall("nonexistent")

    def test_enable_disable(self, temp_registry, sample_tool_dir):
        """Test enabling and disabling a tool."""
        registry, _ = temp_registry

        registry.install(str(sample_tool_dir))
        assert not registry.is_enabled("sample-local-tool")

        registry.enable("sample-local-tool")
        assert registry.is_enabled("sample-local-tool")

        registry.disable("sample-local-tool")
        assert not registry.is_enabled("sample-local-tool")

    def test_enable_not_installed(self, temp_registry):
        """Test enabling a non-installed tool."""
        registry, _ = temp_registry

        with pytest.raises(ToolNotInstalledError):
            registry.enable("nonexistent")

    def test_get_status_installed(self, temp_registry, sample_tool_dir):
        """Test getting status of installed tool."""
        registry, _ = temp_registry

        registry.install(str(sample_tool_dir), enabled=True)

        info = registry.get_status("sample-local-tool")

        assert info.name == "sample-local-tool"
        assert info.status == ToolStatus.INSTALLED_ENABLED
        assert info.version == "1.0.0"
        assert info.installed is not None

    def test_get_status_not_installed_catalog(self, temp_registry):
        """Test getting status of catalog tool not installed."""
        registry, _ = temp_registry

        info = registry.get_status("test-catalog-tool")

        assert info.name == "test-catalog-tool"
        assert info.status == ToolStatus.NOT_INSTALLED
        assert info.catalog_entry is not None
        assert info.installed is None

    def test_get_status_not_found(self, temp_registry):
        """Test getting status of unknown tool."""
        registry, _ = temp_registry

        with pytest.raises(ToolNotFoundError):
            registry.get_status("totally-unknown")

    def test_search_catalog(self, temp_registry):
        """Test searching the catalog."""
        registry, _ = temp_registry

        results = registry.search_catalog("catalog")

        assert len(results) >= 1
        names = [e.name for e in results]
        assert "test-catalog-tool" in names

    def test_get_manifest_installed(self, temp_registry, sample_tool_dir):
        """Test getting manifest for installed tool."""
        registry, _ = temp_registry

        registry.install(str(sample_tool_dir))

        manifest = registry.get_manifest("sample-local-tool")

        assert manifest is not None
        assert manifest.name == "sample-local-tool"
        assert manifest.version == "1.0.0"

    def test_get_manifest_not_installed(self, temp_registry):
        """Test getting manifest for non-installed tool."""
        registry, _ = temp_registry

        manifest = registry.get_manifest("nonexistent")
        assert manifest is None


class TestToolInfo:
    """Tests for ToolInfo dataclass."""

    def test_to_dict(self):
        """Test converting ToolInfo to dict."""
        info = ToolInfo(
            name="test-tool",
            version="1.0.0",
            description="A test tool",
            status=ToolStatus.INSTALLED_ENABLED,
            source="local:/path",
            risk_level="low",
            integration_types=["cli"],
        )

        data = info.to_dict()

        assert data["name"] == "test-tool"
        assert data["version"] == "1.0.0"
        assert data["status"] == "installed_enabled"
        assert data["risk_level"] == "low"


class TestInstallFromGit:
    """Tests for git installation (mocked)."""

    def test_install_from_git_success(self, temp_registry):
        """Test installing from git URL (mocked)."""
        registry, tmpdir = temp_registry

        # Create a mock tool directory that git would clone
        mock_clone_dir = tmpdir / "mock_clone"

        manifest_data = {
            "schema_version": "1.0",
            "tool": {
                "name": "git-tool",
                "version": "2.0.0",
                "description": "A tool from git",
            },
            "integration": {
                "type": "cli",
                "cli": {"binary": "git-tool"},
            },
        }

        def mock_run(cmd, **kwargs):
            # Create the clone directory with manifest
            clone_path = Path(cmd[-1])
            clone_path.mkdir(parents=True, exist_ok=True)
            manifest_path = clone_path / "mother-tool.yaml"
            with open(manifest_path, "w") as f:
                yaml.dump(manifest_data, f)

            result = MagicMock()
            result.returncode = 0
            return result

        with patch("subprocess.run", side_effect=mock_run):
            tool = registry.install("https://github.com/test/git-tool")

        assert tool.name == "git-tool"
        assert tool.version == "2.0.0"
        assert tool.source.startswith("git:")
        assert registry.is_installed("git-tool")

    def test_install_from_catalog(self, temp_registry):
        """Test installing from catalog (mocked git)."""
        registry, tmpdir = temp_registry

        manifest_data = {
            "schema_version": "1.0",
            "tool": {
                "name": "test-catalog-tool",
                "version": "1.0.0",
                "description": "Catalog tool",
            },
            "integration": {
                "type": "cli",
                "cli": {"binary": "test-tool"},
            },
        }

        def mock_run(cmd, **kwargs):
            clone_path = Path(cmd[-1])
            clone_path.mkdir(parents=True, exist_ok=True)
            manifest_path = clone_path / "mother-tool.yaml"
            with open(manifest_path, "w") as f:
                yaml.dump(manifest_data, f)

            result = MagicMock()
            result.returncode = 0
            return result

        with patch("subprocess.run", side_effect=mock_run):
            tool = registry.install("test-catalog-tool")

        assert tool.name == "test-catalog-tool"
        assert registry.is_installed("test-catalog-tool")

    def test_install_from_catalog_not_found(self, temp_registry):
        """Test installing non-existent catalog entry."""
        registry, _ = temp_registry

        with pytest.raises(ToolNotFoundError):
            registry.install("nonexistent-catalog-tool")
