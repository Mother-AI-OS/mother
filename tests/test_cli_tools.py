"""Tests for the tools CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
import yaml

from mother.cli.tools_cmd import (
    cmd_disable,
    cmd_enable,
    cmd_health,
    cmd_install,
    cmd_list,
    cmd_search,
    cmd_status,
    cmd_uninstall,
)
from mother.tools import ExternalToolRegistry, ToolCatalog, ToolStore


@pytest.fixture
def temp_env():
    """Create a temporary environment for testing."""
    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        store_path = tmpdir_path / "store" / "tools.json"
        tools_dir = tmpdir_path / "tools"
        catalog_path = tmpdir_path / "catalog.yaml"

        # Create catalog
        catalog_data = {
            "version": "1.0",
            "tools": [
                {
                    "name": "test-tool",
                    "description": "A test tool",
                    "repository": "https://github.com/test/repo",
                    "version": "1.0.0",
                    "risk_level": "low",
                    "integration_types": ["cli"],
                },
                {
                    "name": "high-risk-tool",
                    "description": "A dangerous tool",
                    "repository": "https://github.com/test/dangerous",
                    "version": "2.0.0",
                    "risk_level": "high",
                    "integration_types": ["python"],
                },
            ],
        }
        with open(catalog_path, "w") as f:
            yaml.dump(catalog_data, f)

        yield {
            "tmpdir": tmpdir_path,
            "store_path": store_path,
            "tools_dir": tools_dir,
            "catalog_path": catalog_path,
        }


@pytest.fixture
def mock_registry(temp_env):
    """Create a mock registry with the temp environment."""
    store = ToolStore(store_path=temp_env["store_path"])
    catalog = ToolCatalog(catalog_path=temp_env["catalog_path"])
    registry = ExternalToolRegistry(
        store=store,
        catalog=catalog,
        tools_dir=temp_env["tools_dir"],
    )
    return registry


@pytest.fixture
def sample_tool_dir(temp_env):
    """Create a sample tool directory with manifest."""
    tool_dir = temp_env["tmpdir"] / "sample-tool"
    tool_dir.mkdir(parents=True)

    manifest_data = {
        "schema_version": "1.0",
        "tool": {
            "name": "sample-tool",
            "version": "1.0.0",
            "description": "A sample tool for testing",
        },
        "integration": {
            "type": "cli",
            "cli": {"binary": "sample-tool"},
        },
    }

    manifest_path = tool_dir / "mother-tool.yaml"
    with open(manifest_path, "w") as f:
        yaml.dump(manifest_data, f)

    return tool_dir


class TestListCommand:
    """Tests for the list command."""

    def test_list_all(self, mock_registry, capsys):
        """Test listing all tools."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_list()

        assert result == 0
        captured = capsys.readouterr()
        assert "test-tool" in captured.out
        assert "high-risk-tool" in captured.out

    def test_list_json(self, mock_registry, capsys):
        """Test listing all tools as JSON."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_list(json_output=True)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) >= 2
        names = [t["name"] for t in data]
        assert "test-tool" in names

    def test_list_installed_empty(self, mock_registry, capsys):
        """Test listing installed when none installed."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_list(show_installed=True)

        assert result == 0
        captured = capsys.readouterr()
        assert "No tools installed" in captured.out

    def test_list_available(self, mock_registry, capsys):
        """Test listing available tools."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_list(show_available=True)

        assert result == 0
        captured = capsys.readouterr()
        assert "test-tool" in captured.out


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_not_installed(self, mock_registry, capsys):
        """Test status of catalog tool not installed."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_status("test-tool")

        assert result == 0
        captured = capsys.readouterr()
        assert "test-tool" in captured.out
        assert "not installed" in captured.out

    def test_status_not_found(self, mock_registry, capsys):
        """Test status of unknown tool."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_status("unknown-tool")

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_status_json(self, mock_registry, capsys):
        """Test status output as JSON."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_status("test-tool", json_output=True)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["name"] == "test-tool"
        assert data["status"] == "not_installed"


class TestInstallCommand:
    """Tests for the install command."""

    def test_install_from_local(self, mock_registry, sample_tool_dir, capsys):
        """Test installing from local path."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_install(str(sample_tool_dir))

        assert result == 0
        captured = capsys.readouterr()
        assert "Installed" in captured.out
        assert "sample-tool" in captured.out

    def test_install_already_installed(self, mock_registry, sample_tool_dir, capsys):
        """Test installing an already installed tool."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            cmd_install(str(sample_tool_dir))
            result = cmd_install(str(sample_tool_dir))

        assert result == 1
        captured = capsys.readouterr()
        assert "already installed" in captured.err

    def test_install_not_found(self, mock_registry, capsys):
        """Test installing non-existent tool."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_install("/nonexistent/path")

        assert result == 1
        captured = capsys.readouterr()
        assert "failed" in captured.err.lower() or "error" in captured.err.lower()

    def test_install_json(self, mock_registry, sample_tool_dir, capsys):
        """Test install with JSON output."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_install(str(sample_tool_dir), json_output=True)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["name"] == "sample-tool"
        assert data["message"] == "installed"


class TestUninstallCommand:
    """Tests for the uninstall command."""

    def test_uninstall_not_installed(self, mock_registry, capsys):
        """Test uninstalling a non-installed tool."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_uninstall("nonexistent", yes=True)

        assert result == 1
        captured = capsys.readouterr()
        assert "not installed" in captured.err

    def test_uninstall_success(self, mock_registry, sample_tool_dir, capsys):
        """Test successful uninstall."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            cmd_install(str(sample_tool_dir))
            result = cmd_uninstall("sample-tool", yes=True)

        assert result == 0
        captured = capsys.readouterr()
        assert "Uninstalled" in captured.out


class TestEnableDisableCommands:
    """Tests for enable and disable commands."""

    def test_enable_not_installed(self, mock_registry, capsys):
        """Test enabling a non-installed tool."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_enable("nonexistent")

        assert result == 1
        captured = capsys.readouterr()
        assert "not installed" in captured.err

    def test_disable_not_installed(self, mock_registry, capsys):
        """Test disabling a non-installed tool."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_disable("nonexistent")

        assert result == 1
        captured = capsys.readouterr()
        assert "not installed" in captured.err

    def test_enable_success(self, mock_registry, sample_tool_dir, capsys):
        """Test successful enable."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            cmd_install(str(sample_tool_dir))
            result = cmd_enable("sample-tool")

        assert result == 0
        captured = capsys.readouterr()
        assert "Enabled" in captured.out

    def test_disable_success(self, mock_registry, sample_tool_dir, capsys):
        """Test successful disable."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            cmd_install(str(sample_tool_dir), enable=True)
            result = cmd_disable("sample-tool")

        assert result == 0
        captured = capsys.readouterr()
        assert "Disabled" in captured.out


class TestSearchCommand:
    """Tests for the search command."""

    def test_search_found(self, mock_registry, capsys):
        """Test searching for existing tools."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_search("test")

        assert result == 0
        captured = capsys.readouterr()
        assert "test-tool" in captured.out

    def test_search_not_found(self, mock_registry, capsys):
        """Test searching with no results."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_search("nonexistent-query-xyz")

        assert result == 0
        captured = capsys.readouterr()
        assert "No tools found" in captured.out

    def test_search_json(self, mock_registry, capsys):
        """Test search with JSON output."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_search("test", json_output=True)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)


class TestHealthCommand:
    """Tests for the health command."""

    def test_health_not_installed(self, mock_registry, capsys):
        """Test health check on non-installed tool."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            result = cmd_health("nonexistent")

        assert result == 1
        captured = capsys.readouterr()
        assert "not installed" in captured.err

    def test_health_installed(self, mock_registry, sample_tool_dir, capsys):
        """Test health check on installed tool."""
        with patch("mother.cli.tools_cmd._get_registry", return_value=mock_registry):
            cmd_install(str(sample_tool_dir))
            # Note: Health may fail due to missing binary, but that's expected
            result = cmd_health("sample-tool")

        # Result may be 0 or 1 depending on binary availability
        captured = capsys.readouterr()
        assert "sample-tool" in captured.out


class TestCLIParser:
    """Tests for CLI argument parsing."""

    def test_tools_help(self, capsys):
        """Test tools command help."""
        from mother.cli import main

        # argparse exits with SystemExit(0) on --help
        with pytest.raises(SystemExit) as exc_info:
            main(["tools", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Install, uninstall, enable, and disable" in captured.out

    def test_tools_list_args(self):
        """Test tools list argument parsing."""
        from mother.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["tools", "list", "--installed", "--json"])

        assert args.command == "tools"
        assert args.tools_command == "list"
        assert args.installed is True
        assert args.json_output is True

    def test_tools_install_args(self):
        """Test tools install argument parsing."""
        from mother.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["tools", "install", "/path/to/tool", "--enable", "-y"])

        assert args.command == "tools"
        assert args.tools_command == "install"
        assert args.source == "/path/to/tool"
        assert args.enable is True
        assert args.yes is True

    def test_tools_status_args(self):
        """Test tools status argument parsing."""
        from mother.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["tools", "status", "my-tool", "--json"])

        assert args.command == "tools"
        assert args.tools_command == "status"
        assert args.name == "my-tool"
        assert args.json_output is True
