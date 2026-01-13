"""Tests for the tools registry module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mother.tools.registry import ToolRegistry


class TestToolRegistryInit:
    """Tests for ToolRegistry initialization."""

    def test_init_without_settings_or_plugins(self):
        """Test initialization without settings, plugins disabled."""
        registry = ToolRegistry(enable_plugins=False)

        assert registry.wrappers == {}
        assert registry._settings is None
        assert registry._plugin_manager is None
        assert registry._plugins_enabled is False

    def test_init_with_plugins_disabled(self):
        """Test initialization with plugins explicitly disabled."""
        registry = ToolRegistry(enable_plugins=False)

        assert registry._plugins_enabled is False
        assert registry._plugin_manager is None

    def test_init_with_plugins_enabled(self):
        """Test initialization with plugins enabled."""
        with patch.object(ToolRegistry, "_init_plugins") as mock_init_plugins:
            with patch("mother.tools.registry.PLUGINS_AVAILABLE", True):
                registry = ToolRegistry(enable_plugins=True)

        assert registry._plugins_enabled is True
        mock_init_plugins.assert_called_once()

    def test_init_with_settings(self):
        """Test initialization with settings."""
        mock_settings = MagicMock()
        registry = ToolRegistry(settings=mock_settings, enable_plugins=False)

        assert registry._settings is mock_settings


class TestToolRegistryPlugins:
    """Tests for plugin-related methods."""

    def test_init_plugins_when_not_available(self):
        """Test _init_plugins when plugins not available."""
        with patch("mother.tools.registry.PLUGINS_AVAILABLE", False):
            registry = ToolRegistry(enable_plugins=False)
            registry._init_plugins(None)

        assert registry._plugin_manager is None

    def test_init_plugins_success(self):
        """Test _init_plugins creates plugin manager."""
        mock_plugin_manager = MagicMock()
        mock_plugin_config = MagicMock()

        with patch("mother.tools.registry.PLUGINS_AVAILABLE", True):
            with patch("mother.tools.registry.PluginManager", return_value=mock_plugin_manager):
                with patch("mother.tools.registry.PluginConfig", return_value=mock_plugin_config):
                    registry = ToolRegistry(enable_plugins=False)
                    registry._init_plugins(None)

        assert registry._plugin_manager is mock_plugin_manager

    def test_init_plugins_with_config(self):
        """Test _init_plugins with custom config."""
        mock_plugin_manager = MagicMock()
        custom_config = MagicMock()

        with patch("mother.tools.registry.PLUGINS_AVAILABLE", True):
            with patch(
                "mother.tools.registry.PluginManager", return_value=mock_plugin_manager
            ) as mock_pm_class:
                registry = ToolRegistry(enable_plugins=False)
                registry._init_plugins(custom_config)

        mock_pm_class.assert_called_once_with(custom_config)

    def test_init_plugins_handles_exception(self):
        """Test _init_plugins handles exceptions gracefully."""
        with patch("mother.tools.registry.PLUGINS_AVAILABLE", True):
            with patch("mother.tools.registry.PluginManager", side_effect=Exception("Init failed")):
                with patch("mother.tools.registry.PluginConfig"):
                    registry = ToolRegistry(enable_plugins=False)
                    registry._init_plugins(None)

        assert registry._plugin_manager is None

    @pytest.mark.asyncio
    async def test_initialize_plugins(self):
        """Test async plugin initialization."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.initialize = AsyncMock()
        mock_plugin_manager.__len__ = MagicMock(return_value=5)

        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_plugin_manager

        await registry.initialize_plugins()

        mock_plugin_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_plugins_no_manager(self):
        """Test initialize_plugins when no manager."""
        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = None

        # Should not raise
        await registry.initialize_plugins()

    @pytest.mark.asyncio
    async def test_initialize_plugins_handles_exception(self):
        """Test initialize_plugins handles exception."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.initialize = AsyncMock(side_effect=Exception("Failed"))

        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_plugin_manager

        # Should not raise
        await registry.initialize_plugins()

    def test_plugin_manager_property(self):
        """Test plugin_manager property."""
        mock_pm = MagicMock()
        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_pm

        assert registry.plugin_manager is mock_pm


class TestToolRegistryGetWrapper:
    """Tests for get_wrapper method."""

    def test_get_wrapper_not_exists(self):
        """Test getting a non-existent wrapper returns None."""
        registry = ToolRegistry(enable_plugins=False)

        result = registry.get_wrapper("nonexistent")
        assert result is None


class TestToolRegistrySchemas:
    """Tests for schema-related methods."""

    def test_get_all_anthropic_schemas_empty(self):
        """Test getting schemas when no plugins."""
        registry = ToolRegistry(enable_plugins=False)

        schemas = registry.get_all_anthropic_schemas()
        assert schemas == []

    def test_get_all_anthropic_schemas_with_plugins(self):
        """Test getting schemas from plugins."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.get_all_schemas.return_value = [
            {"name": "plugin_cap1", "description": "Capability 1"},
            {"name": "plugin_cap2", "description": "Capability 2"},
        ]

        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_plugin_manager

        schemas = registry.get_all_anthropic_schemas()
        assert len(schemas) == 2
        assert schemas[0]["name"] == "plugin_cap1"
        assert schemas[1]["name"] == "plugin_cap2"


class TestToolRegistryListTools:
    """Tests for list_tools method."""

    def test_list_tools_empty(self):
        """Test listing when no tools."""
        registry = ToolRegistry(enable_plugins=False)

        result = registry.list_tools()
        assert result == {}

    def test_list_tools_with_plugins(self):
        """Test listing with plugins."""
        mock_plugin_info = MagicMock()
        mock_plugin_info.description = "Plugin tool"
        mock_plugin_info.capabilities = ["cap1", "cap2"]
        mock_plugin_info.version = "1.0.0"
        mock_plugin_info.author = "Test Author"

        mock_plugin_manager = MagicMock()
        mock_plugin_manager.list_plugins.return_value = {"plugin_tool": mock_plugin_info}

        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_plugin_manager

        result = registry.list_tools()
        assert "plugin_tool" in result
        assert result["plugin_tool"]["description"] == "Plugin tool"
        assert result["plugin_tool"]["source"] == "plugin"
        assert result["plugin_tool"]["version"] == "1.0.0"


class TestToolRegistryGetToolDetails:
    """Tests for get_tool_details method."""

    def test_get_tool_details_returns_none(self):
        """Test getting details always returns None (legacy removed)."""
        registry = ToolRegistry(enable_plugins=False)

        result = registry.get_tool_details("any_tool")
        assert result is None


class TestToolRegistryParseToolName:
    """Tests for parse_tool_name method."""

    def test_parse_tool_name_plugin_match(self):
        """Test parsing when plugin matches."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.__contains__ = MagicMock(return_value=True)
        mock_plugin_manager.parse_capability_name.return_value = ("plugin", "capability")

        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_plugin_manager

        wrapper_name, command = registry.parse_tool_name("plugin_capability")
        assert wrapper_name == "plugin"
        assert command == "capability"

    def test_parse_tool_name_plugin_exception(self):
        """Test parsing handles plugin exception."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.__contains__ = MagicMock(return_value=True)
        mock_plugin_manager.parse_capability_name.side_effect = Exception("Parse failed")

        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_plugin_manager

        # Should return None since legacy tools are removed
        wrapper_name, command = registry.parse_tool_name("test_cmd")
        assert wrapper_name is None
        assert command is None

    def test_parse_tool_name_no_match(self):
        """Test parsing when no tool matches."""
        registry = ToolRegistry(enable_plugins=False)

        wrapper_name, command = registry.parse_tool_name("unknown_tool")
        assert wrapper_name is None
        assert command is None


class TestToolRegistryIsPluginCapability:
    """Tests for is_plugin_capability method."""

    def test_is_plugin_capability_no_manager(self):
        """Test when no plugin manager."""
        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = None

        assert registry.is_plugin_capability("any_name") is False

    def test_is_plugin_capability_true(self):
        """Test when capability exists in plugin."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.__contains__ = MagicMock(return_value=True)

        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_plugin_manager

        assert registry.is_plugin_capability("plugin_cap") is True

    def test_is_plugin_capability_false(self):
        """Test when capability not in plugin."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.__contains__ = MagicMock(return_value=False)

        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_plugin_manager

        assert registry.is_plugin_capability("unknown") is False


class TestToolRegistryExecutePlugin:
    """Tests for execute_plugin method."""

    @pytest.mark.asyncio
    async def test_execute_plugin_no_manager(self):
        """Test execute when no plugin manager."""
        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = None

        with pytest.raises(ValueError, match="Plugin system not available"):
            await registry.execute_plugin("any_name", {})

    @pytest.mark.asyncio
    async def test_execute_plugin_success(self):
        """Test successful plugin execution."""
        mock_result = MagicMock()
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.execute = AsyncMock(return_value=mock_result)

        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_plugin_manager

        result = await registry.execute_plugin("plugin_cap", {"param": "value"})

        assert result is mock_result
        mock_plugin_manager.execute.assert_called_once_with("plugin_cap", {"param": "value"})


class TestToolRegistryRequiresConfirmation:
    """Tests for requires_confirmation method."""

    def test_requires_confirmation_plugin(self):
        """Test confirmation check for plugin."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.__contains__ = MagicMock(return_value=True)
        mock_plugin_manager.requires_confirmation.return_value = True

        registry = ToolRegistry(enable_plugins=False)
        registry._plugin_manager = mock_plugin_manager

        assert registry.requires_confirmation("plugin_cap") is True

    def test_requires_confirmation_unknown_tool(self):
        """Test confirmation check for unknown tool."""
        registry = ToolRegistry(enable_plugins=False)

        assert registry.requires_confirmation("unknown_tool") is False
