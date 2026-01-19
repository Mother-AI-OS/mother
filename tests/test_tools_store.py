"""Tests for the tool store module."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from mother.tools.exceptions import ToolNotInstalledError
from mother.tools.store import InstalledTool, ToolStore


class TestInstalledTool:
    """Tests for InstalledTool dataclass."""

    def test_create_basic(self):
        """Test basic tool creation."""
        tool = InstalledTool.create(
            name="test-tool",
            version="1.0.0",
            source="local:/path/to/tool",
            manifest_path="/path/to/manifest.yaml",
            integration_type="cli",
        )

        assert tool.name == "test-tool"
        assert tool.version == "1.0.0"
        assert tool.source == "local:/path/to/tool"
        assert tool.enabled is False  # Default disabled
        assert tool.integration_type == "cli"
        assert tool.risk_level == "low"
        assert tool.installed_at is not None

    def test_create_with_options(self):
        """Test tool creation with all options."""
        tool = InstalledTool.create(
            name="full-tool",
            version="2.0.0",
            source="git:https://github.com/org/repo",
            manifest_path="/path/manifest.yaml",
            integration_type="python",
            risk_level="high",
            description="A test tool",
            enabled=True,
            config_values={"api_key": "secret"},
        )

        assert tool.name == "full-tool"
        assert tool.enabled is True
        assert tool.risk_level == "high"
        assert tool.description == "A test tool"
        assert tool.config_values == {"api_key": "secret"}

    def test_to_dict(self):
        """Test serialization to dict."""
        tool = InstalledTool.create(
            name="test-tool",
            version="1.0.0",
            source="local:/path",
            manifest_path="/manifest.yaml",
            integration_type="cli",
        )

        data = tool.to_dict()

        assert data["name"] == "test-tool"
        assert data["version"] == "1.0.0"
        assert data["source"] == "local:/path"
        assert "installed_at" in data

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "name": "test-tool",
            "version": "1.0.0",
            "source": "local:/path",
            "installed_at": "2026-01-19T12:00:00",
            "enabled": True,
            "manifest_path": "/manifest.yaml",
            "integration_type": "cli",
            "risk_level": "medium",
            "description": "Test",
            "config_values": {"key": "value"},
        }

        tool = InstalledTool.from_dict(data)

        assert tool.name == "test-tool"
        assert tool.enabled is True
        assert tool.risk_level == "medium"
        assert tool.config_values == {"key": "value"}

    def test_from_dict_defaults(self):
        """Test deserialization with missing optional fields."""
        data = {
            "name": "test-tool",
            "version": "1.0.0",
            "source": "local:/path",
            "installed_at": "2026-01-19T12:00:00",
            "manifest_path": "/manifest.yaml",
            "integration_type": "cli",
        }

        tool = InstalledTool.from_dict(data)

        assert tool.enabled is False
        assert tool.risk_level == "low"
        assert tool.description == ""
        assert tool.config_values == {}


class TestToolStore:
    """Tests for ToolStore class."""

    def test_init_default_path(self):
        """Test initialization with default path."""
        store = ToolStore()
        assert store.store_path == Path.home() / ".local" / "share" / "mother" / "tools" / "tools.json"

    def test_init_custom_path(self):
        """Test initialization with custom path."""
        custom_path = Path("/custom/path/tools.json")
        store = ToolStore(store_path=custom_path)
        assert store.store_path == custom_path

    def test_load_empty(self):
        """Test loading when file doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)
            store.load()

            assert store.list_tools() == []

    def test_save_and_load(self):
        """Test saving and loading tools."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)

            # Add a tool
            tool = InstalledTool.create(
                name="test-tool",
                version="1.0.0",
                source="local:/path",
                manifest_path="/manifest.yaml",
                integration_type="cli",
            )
            store.add_tool(tool)

            # Create new store instance and load
            store2 = ToolStore(store_path=store_path)
            store2.load()

            loaded_tools = store2.list_tools()
            assert len(loaded_tools) == 1
            assert loaded_tools[0].name == "test-tool"
            assert loaded_tools[0].version == "1.0.0"

    def test_get_tool(self):
        """Test getting a specific tool."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)

            tool = InstalledTool.create(
                name="my-tool",
                version="1.0.0",
                source="local:/path",
                manifest_path="/manifest.yaml",
                integration_type="cli",
            )
            store.add_tool(tool)

            # Get existing
            result = store.get_tool("my-tool")
            assert result is not None
            assert result.name == "my-tool"

            # Get non-existing
            result = store.get_tool("nonexistent")
            assert result is None

    def test_has_tool(self):
        """Test checking if tool exists."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)

            tool = InstalledTool.create(
                name="my-tool",
                version="1.0.0",
                source="local:/path",
                manifest_path="/manifest.yaml",
                integration_type="cli",
            )
            store.add_tool(tool)

            assert store.has_tool("my-tool") is True
            assert store.has_tool("nonexistent") is False

    def test_remove_tool(self):
        """Test removing a tool."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)

            tool = InstalledTool.create(
                name="my-tool",
                version="1.0.0",
                source="local:/path",
                manifest_path="/manifest.yaml",
                integration_type="cli",
            )
            store.add_tool(tool)
            assert store.has_tool("my-tool") is True

            store.remove_tool("my-tool")
            assert store.has_tool("my-tool") is False

    def test_remove_nonexistent_tool(self):
        """Test removing a non-existent tool."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)

            with pytest.raises(ToolNotInstalledError):
                store.remove_tool("nonexistent")

    def test_enable_disable_tool(self):
        """Test enabling and disabling a tool."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)

            tool = InstalledTool.create(
                name="my-tool",
                version="1.0.0",
                source="local:/path",
                manifest_path="/manifest.yaml",
                integration_type="cli",
                enabled=False,
            )
            store.add_tool(tool)

            # Enable
            store.enable_tool("my-tool")
            assert store.get_tool("my-tool").enabled is True

            # Disable
            store.disable_tool("my-tool")
            assert store.get_tool("my-tool").enabled is False

    def test_enable_nonexistent_tool(self):
        """Test enabling a non-existent tool."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)

            with pytest.raises(ToolNotInstalledError):
                store.enable_tool("nonexistent")

    def test_update_config(self):
        """Test updating tool configuration."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)

            tool = InstalledTool.create(
                name="my-tool",
                version="1.0.0",
                source="local:/path",
                manifest_path="/manifest.yaml",
                integration_type="cli",
                config_values={"key1": "value1"},
            )
            store.add_tool(tool)

            store.update_config("my-tool", {"key2": "value2"})

            result = store.get_tool("my-tool")
            assert result.config_values == {"key1": "value1", "key2": "value2"}

    def test_list_enabled_disabled(self):
        """Test listing enabled and disabled tools."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)

            # Add enabled tool
            tool1 = InstalledTool.create(
                name="enabled-tool",
                version="1.0.0",
                source="local:/path1",
                manifest_path="/manifest1.yaml",
                integration_type="cli",
                enabled=True,
            )
            store.add_tool(tool1)

            # Add disabled tool
            tool2 = InstalledTool.create(
                name="disabled-tool",
                version="1.0.0",
                source="local:/path2",
                manifest_path="/manifest2.yaml",
                integration_type="cli",
                enabled=False,
            )
            store.add_tool(tool2)

            enabled = store.list_enabled()
            assert len(enabled) == 1
            assert enabled[0].name == "enabled-tool"

            disabled = store.list_disabled()
            assert len(disabled) == 1
            assert disabled[0].name == "disabled-tool"

    def test_clear(self):
        """Test clearing all tools."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store = ToolStore(store_path=store_path)

            tool = InstalledTool.create(
                name="my-tool",
                version="1.0.0",
                source="local:/path",
                manifest_path="/manifest.yaml",
                integration_type="cli",
            )
            store.add_tool(tool)

            store.clear()
            assert store.list_tools() == []

    def test_load_corrupted_json(self):
        """Test loading a corrupted JSON file."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"
            store_path.write_text("not valid json {")

            store = ToolStore(store_path=store_path)
            store.load()

            # Should gracefully handle and return empty
            assert store.list_tools() == []

    def test_auto_load_on_operations(self):
        """Test that store auto-loads when needed."""
        with TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tools.json"

            # Save a tool directly
            data = {
                "version": "1.0",
                "tools": {
                    "test-tool": {
                        "name": "test-tool",
                        "version": "1.0.0",
                        "source": "local:/path",
                        "installed_at": "2026-01-19T12:00:00",
                        "enabled": True,
                        "manifest_path": "/manifest.yaml",
                        "integration_type": "cli",
                    }
                },
            }
            with open(store_path, "w") as f:
                json.dump(data, f)

            # Create store without explicit load
            store = ToolStore(store_path=store_path)

            # Operations should auto-load
            assert store.has_tool("test-tool") is True
            assert store.get_tool("test-tool") is not None
