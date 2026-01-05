"""Tests for the tools registry module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mother.tools.registry import ToolRegistry


class TestToolRegistryInit:
    """Tests for ToolRegistry initialization."""

    def test_init_without_settings_or_plugins(self):
        """Test initialization without settings, plugins disabled."""
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)

        assert registry.wrappers == {}
        assert registry._settings is None
        assert registry._plugin_manager is None
        assert registry._plugins_enabled is False

    def test_init_with_plugins_disabled(self):
        """Test initialization with plugins explicitly disabled."""
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)

        assert registry._plugins_enabled is False
        assert registry._plugin_manager is None

    def test_init_calls_load_tools(self):
        """Test that init calls _load_tools."""
        with patch.object(ToolRegistry, "_load_tools") as mock_load:
            ToolRegistry(enable_plugins=False)

        mock_load.assert_called_once()

    def test_init_with_plugins_enabled(self):
        """Test initialization with plugins enabled."""
        with patch.object(ToolRegistry, "_load_tools"):
            with patch.object(ToolRegistry, "_init_plugins") as mock_init_plugins:
                with patch("mother.tools.registry.PLUGINS_AVAILABLE", True):
                    registry = ToolRegistry(enable_plugins=True)

        assert registry._plugins_enabled is True
        mock_init_plugins.assert_called_once()

    def test_init_with_settings(self):
        """Test initialization with settings."""
        mock_settings = MagicMock()
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(settings=mock_settings, enable_plugins=False)

        assert registry._settings is mock_settings


class TestToolRegistryPlugins:
    """Tests for plugin-related methods."""

    def test_init_plugins_when_not_available(self):
        """Test _init_plugins when plugins not available."""
        with patch.object(ToolRegistry, "_load_tools"):
            with patch("mother.tools.registry.PLUGINS_AVAILABLE", False):
                registry = ToolRegistry(enable_plugins=False)
                registry._init_plugins(None)

        assert registry._plugin_manager is None

    def test_init_plugins_success(self):
        """Test _init_plugins creates plugin manager."""
        mock_plugin_manager = MagicMock()
        mock_plugin_config = MagicMock()

        with patch.object(ToolRegistry, "_load_tools"):
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

        with patch.object(ToolRegistry, "_load_tools"):
            with patch("mother.tools.registry.PLUGINS_AVAILABLE", True):
                with patch("mother.tools.registry.PluginManager", return_value=mock_plugin_manager) as mock_pm_class:
                    registry = ToolRegistry(enable_plugins=False)
                    registry._init_plugins(custom_config)

        mock_pm_class.assert_called_once_with(custom_config)

    def test_init_plugins_handles_exception(self):
        """Test _init_plugins handles exceptions gracefully."""
        with patch.object(ToolRegistry, "_load_tools"):
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

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = mock_plugin_manager

            await registry.initialize_plugins()

        mock_plugin_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_plugins_no_manager(self):
        """Test initialize_plugins when no manager."""
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = None

            # Should not raise
            await registry.initialize_plugins()

    @pytest.mark.asyncio
    async def test_initialize_plugins_handles_exception(self):
        """Test initialize_plugins handles exception."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.initialize = AsyncMock(side_effect=Exception("Failed"))

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = mock_plugin_manager

            # Should not raise
            await registry.initialize_plugins()

    def test_plugin_manager_property(self):
        """Test plugin_manager property."""
        mock_pm = MagicMock()
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = mock_pm

        assert registry.plugin_manager is mock_pm


class TestToolRegistryLoadTools:
    """Tests for tool loading methods."""

    def test_load_tools_with_settings(self):
        """Test _load_tools uses settings when available."""
        mock_settings = MagicMock()

        with patch.object(ToolRegistry, "_load_from_settings") as mock_from_settings:
            with patch.object(ToolRegistry, "_load_defaults") as mock_defaults:
                registry = ToolRegistry(settings=mock_settings, enable_plugins=False)

        mock_from_settings.assert_called_once()
        mock_defaults.assert_not_called()
        assert registry._settings is mock_settings

    def test_load_tools_without_settings(self):
        """Test _load_tools uses defaults when no settings."""
        with patch.object(ToolRegistry, "_load_defaults") as mock_defaults:
            with patch.object(ToolRegistry, "_load_from_settings") as mock_from_settings:
                ToolRegistry(settings=None, enable_plugins=False)

        mock_defaults.assert_called_once()
        mock_from_settings.assert_not_called()

    def test_load_defaults_no_tools_exist(self, tmp_path):
        """Test _load_defaults when no tool binaries exist."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        # No wrappers should be loaded if binaries don't exist
        assert len(registry.wrappers) == 0

    def test_load_defaults_mailcraft_exists(self, tmp_path):
        """Test _load_defaults loads mailcraft when binary exists."""
        # Create mock binary
        bin_dir = tmp_path / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        mailcraft_bin = bin_dir / "mailcraft"
        mailcraft_bin.touch()

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        assert "mailcraft" in registry.wrappers

    def test_load_defaults_leads_exists(self, tmp_path):
        """Test _load_defaults loads leads when binary exists."""
        bin_dir = tmp_path / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        leads_bin = bin_dir / "leads"
        leads_bin.touch()

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        assert "leads" in registry.wrappers

    def test_load_defaults_taxlord_exists(self, tmp_path):
        """Test _load_defaults loads taxlord when directory exists."""
        taxlord_dir = tmp_path / "projects" / "taxlord"
        taxlord_dir.mkdir(parents=True)

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        assert "taxlord" in registry.wrappers

    def test_load_defaults_gcp_draft_exists(self, tmp_path):
        """Test _load_defaults loads gcp_draft when binary exists."""
        bin_dir = tmp_path / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        gcp_draft_bin = bin_dir / "gcp-draft"
        gcp_draft_bin.touch()

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        assert "gcp_draft" in registry.wrappers

    def test_load_defaults_acnjxn_bin_exists(self, tmp_path):
        """Test _load_defaults loads acnjxn when bin exists."""
        bin_dir = tmp_path / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        acnjxn_bin = bin_dir / "acnjxn"
        acnjxn_bin.touch()

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        assert "acnjxn" in registry.wrappers

    def test_load_defaults_acnjxn_venv_exists(self, tmp_path):
        """Test _load_defaults loads acnjxn from venv."""
        venv_dir = tmp_path / "projects" / "acnjxn" / ".venv" / "bin"
        venv_dir.mkdir(parents=True)
        acnjxn_venv = venv_dir / "acnjxn"
        acnjxn_venv.touch()

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        assert "acnjxn" in registry.wrappers

    def test_load_defaults_datacraft_bin_exists(self, tmp_path):
        """Test _load_defaults loads datacraft when bin exists."""
        bin_dir = tmp_path / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        datacraft_bin = bin_dir / "datacraft"
        datacraft_bin.touch()

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        assert "datacraft" in registry.wrappers

    def test_load_defaults_datacraft_dir_exists(self, tmp_path):
        """Test _load_defaults loads datacraft from project dir."""
        datacraft_dir = tmp_path / "projects" / "datacraft"
        datacraft_dir.mkdir(parents=True)

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        assert "datacraft" in registry.wrappers

    def test_load_defaults_pdf_merge_exists(self, tmp_path):
        """Test _load_defaults loads pdf_merge when binary exists."""
        bin_dir = tmp_path / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        pdf_merge_bin = bin_dir / "pdf-merge"
        pdf_merge_bin.touch()

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        assert "pdf_merge" in registry.wrappers

    def test_load_defaults_transmit_exists(self, tmp_path):
        """Test _load_defaults loads transmit when binary exists."""
        bin_dir = tmp_path / ".local" / "bin"
        bin_dir.mkdir(parents=True)
        transmit_bin = bin_dir / "transmit"
        transmit_bin.touch()

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(enable_plugins=False)

        assert "transmit" in registry.wrappers


class TestToolRegistryLoadFromSettings:
    """Tests for _load_from_settings method."""

    def test_load_from_settings_mailcraft(self, tmp_path):
        """Test loading mailcraft from settings."""
        mock_settings = MagicMock()
        mock_settings.mailcraft_bin = tmp_path / "mailcraft"
        mock_settings.mailcraft_bin.touch()
        mock_settings.mailcraft_password = "secret"
        mock_settings.tool_timeout = 30
        mock_settings.leads_bin = tmp_path / "nonexistent"
        mock_settings.taxlord_dir = tmp_path / "nonexistent"
        mock_settings.gcp_draft_bin = tmp_path / "nonexistent"

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(settings=mock_settings, enable_plugins=False)

        assert "mailcraft" in registry.wrappers

    def test_load_from_settings_leads(self, tmp_path):
        """Test loading leads from settings."""
        mock_settings = MagicMock()
        mock_settings.mailcraft_bin = tmp_path / "nonexistent"
        mock_settings.leads_bin = tmp_path / "leads"
        mock_settings.leads_bin.touch()
        mock_settings.tool_timeout = 30
        mock_settings.taxlord_dir = tmp_path / "nonexistent"
        mock_settings.gcp_draft_bin = tmp_path / "nonexistent"

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(settings=mock_settings, enable_plugins=False)

        assert "leads" in registry.wrappers

    def test_load_from_settings_taxlord(self, tmp_path):
        """Test loading taxlord from settings."""
        mock_settings = MagicMock()
        mock_settings.mailcraft_bin = tmp_path / "nonexistent"
        mock_settings.leads_bin = tmp_path / "nonexistent"
        mock_settings.taxlord_dir = tmp_path / "taxlord"
        mock_settings.taxlord_dir.mkdir()
        mock_settings.tool_timeout = 30
        mock_settings.gcp_draft_bin = tmp_path / "nonexistent"

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(settings=mock_settings, enable_plugins=False)

        assert "taxlord" in registry.wrappers

    def test_load_from_settings_gcp_draft(self, tmp_path):
        """Test loading gcp_draft from settings."""
        mock_settings = MagicMock()
        mock_settings.mailcraft_bin = tmp_path / "nonexistent"
        mock_settings.leads_bin = tmp_path / "nonexistent"
        mock_settings.taxlord_dir = tmp_path / "nonexistent"
        mock_settings.gcp_draft_bin = tmp_path / "gcp-draft"
        mock_settings.gcp_draft_bin.touch()
        mock_settings.tool_timeout = 30

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch.object(ToolRegistry, "_init_plugins"):
                registry = ToolRegistry(settings=mock_settings, enable_plugins=False)

        assert "gcp_draft" in registry.wrappers


class TestToolRegistryGetWrapper:
    """Tests for get_wrapper method."""

    def test_get_wrapper_exists(self):
        """Test getting an existing wrapper."""
        mock_wrapper = MagicMock()
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry.wrappers["test_tool"] = mock_wrapper

        result = registry.get_wrapper("test_tool")
        assert result is mock_wrapper

    def test_get_wrapper_not_exists(self):
        """Test getting a non-existent wrapper."""
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)

        result = registry.get_wrapper("nonexistent")
        assert result is None


class TestToolRegistrySchemas:
    """Tests for schema-related methods."""

    def test_get_all_anthropic_schemas_empty(self):
        """Test getting schemas when no tools."""
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)

        schemas = registry.get_all_anthropic_schemas()
        assert schemas == []

    def test_get_all_anthropic_schemas_legacy_only(self):
        """Test getting schemas from legacy tools."""
        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = {"cmd1": {}, "cmd2": {}}
        mock_wrapper.get_anthropic_tool_schema.side_effect = [
            {"name": "tool_cmd1", "description": "Cmd 1"},
            {"name": "tool_cmd2", "description": "Cmd 2"},
        ]

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry.wrappers["tool"] = mock_wrapper

        schemas = registry.get_all_anthropic_schemas()
        assert len(schemas) == 2
        assert schemas[0]["name"] == "tool_cmd1"
        assert schemas[1]["name"] == "tool_cmd2"

    def test_get_all_anthropic_schemas_with_plugins(self):
        """Test getting schemas from both plugins and legacy."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.get_all_schemas.return_value = [
            {"name": "plugin_cap", "description": "Plugin capability"}
        ]

        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = {"cmd": {}}
        mock_wrapper.get_anthropic_tool_schema.return_value = {"name": "legacy_cmd", "description": "Legacy"}

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = mock_plugin_manager
            registry.wrappers["legacy"] = mock_wrapper

        schemas = registry.get_all_anthropic_schemas()
        # Plugins first, then legacy
        assert len(schemas) == 2
        assert schemas[0]["name"] == "plugin_cap"
        assert schemas[1]["name"] == "legacy_cmd"

    def test_get_all_anthropic_schemas_skips_duplicates(self):
        """Test that plugin schemas take precedence."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.get_all_schemas.return_value = [
            {"name": "shared_name", "description": "Plugin version"}
        ]

        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = {"cmd": {}}
        mock_wrapper.get_anthropic_tool_schema.return_value = {"name": "shared_name", "description": "Legacy version"}

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = mock_plugin_manager
            registry.wrappers["legacy"] = mock_wrapper

        schemas = registry.get_all_anthropic_schemas()
        # Should only have plugin version
        assert len(schemas) == 1
        assert schemas[0]["description"] == "Plugin version"

    def test_get_all_anthropic_schemas_handles_exception(self):
        """Test schema generation handles exceptions."""
        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = {"good": {}, "bad": {}}
        mock_wrapper.get_anthropic_tool_schema.side_effect = [
            {"name": "good_cmd", "description": "Good"},
            Exception("Schema generation failed"),
        ]

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry.wrappers["tool"] = mock_wrapper

        schemas = registry.get_all_anthropic_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "good_cmd"


class TestToolRegistryListTools:
    """Tests for list_tools method."""

    def test_list_tools_empty(self):
        """Test listing when no tools."""
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)

        result = registry.list_tools()
        assert result == {}

    def test_list_tools_legacy_only(self):
        """Test listing legacy tools."""
        mock_wrapper = MagicMock()
        mock_wrapper.description = "Test tool"
        mock_wrapper.get_commands.return_value = {"cmd1": {}, "cmd2": {}}

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry.wrappers["test"] = mock_wrapper

        result = registry.list_tools()
        assert "test" in result
        assert result["test"]["description"] == "Test tool"
        assert result["test"]["commands"] == ["cmd1", "cmd2"]
        assert result["test"]["source"] == "legacy"

    def test_list_tools_with_plugins(self):
        """Test listing with plugins."""
        mock_plugin_info = MagicMock()
        mock_plugin_info.description = "Plugin tool"
        mock_plugin_info.capabilities = ["cap1", "cap2"]
        mock_plugin_info.version = "1.0.0"
        mock_plugin_info.author = "Test Author"

        mock_plugin_manager = MagicMock()
        mock_plugin_manager.list_plugins.return_value = {"plugin_tool": mock_plugin_info}

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = mock_plugin_manager

        result = registry.list_tools()
        assert "plugin_tool" in result
        assert result["plugin_tool"]["description"] == "Plugin tool"
        assert result["plugin_tool"]["source"] == "plugin"
        assert result["plugin_tool"]["version"] == "1.0.0"


class TestToolRegistryGetToolDetails:
    """Tests for get_tool_details method."""

    def test_get_tool_details_not_found(self):
        """Test getting details for non-existent tool."""
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)

        result = registry.get_tool_details("nonexistent")
        assert result is None

    def test_get_tool_details_exists(self):
        """Test getting details for existing tool."""
        mock_wrapper = MagicMock()
        mock_wrapper.description = "Test tool description"
        mock_wrapper.get_commands.return_value = {
            "cmd1": {
                "description": "Command 1",
                "parameters": [{"name": "param1"}],
                "confirmation_required": True,
            },
            "cmd2": {
                "description": "Command 2",
            },
        }

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry.wrappers["test"] = mock_wrapper

        result = registry.get_tool_details("test")
        assert result is not None
        assert result["name"] == "test"
        assert result["description"] == "Test tool description"
        assert "cmd1" in result["commands"]
        assert result["commands"]["cmd1"]["confirmation_required"] is True
        assert result["commands"]["cmd2"]["confirmation_required"] is False


class TestToolRegistryParseToolName:
    """Tests for parse_tool_name method."""

    def test_parse_tool_name_plugin_match(self):
        """Test parsing when plugin matches."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.__contains__ = MagicMock(return_value=True)
        mock_plugin_manager.parse_capability_name.return_value = ("plugin", "capability")

        with patch.object(ToolRegistry, "_load_tools"):
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

        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = {"cmd": {}}

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = mock_plugin_manager
            registry.wrappers["test"] = mock_wrapper

        # Should fall through to legacy check
        wrapper_name, command = registry.parse_tool_name("test_cmd")
        assert wrapper_name == "test"
        assert command == "cmd"

    def test_parse_tool_name_legacy_direct_match(self):
        """Test parsing legacy tool with direct command match."""
        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = {"send": {}, "list": {}}

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry.wrappers["mailcraft"] = mock_wrapper

        wrapper_name, command = registry.parse_tool_name("mailcraft_send")
        assert wrapper_name == "mailcraft"
        assert command == "send"

    def test_parse_tool_name_legacy_dotted(self):
        """Test parsing legacy tool with dotted command."""
        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = {"elster.vat": {}}

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry.wrappers["taxlord"] = mock_wrapper

        wrapper_name, command = registry.parse_tool_name("taxlord_elster_vat")
        assert wrapper_name == "taxlord"
        assert command == "elster.vat"

    def test_parse_tool_name_no_match(self):
        """Test parsing when no tool matches."""
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)

        wrapper_name, command = registry.parse_tool_name("unknown_tool")
        assert wrapper_name is None
        assert command is None


class TestToolRegistryIsPluginCapability:
    """Tests for is_plugin_capability method."""

    def test_is_plugin_capability_no_manager(self):
        """Test when no plugin manager."""
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = None

        assert registry.is_plugin_capability("any_name") is False

    def test_is_plugin_capability_true(self):
        """Test when capability exists in plugin."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.__contains__ = MagicMock(return_value=True)

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = mock_plugin_manager

        assert registry.is_plugin_capability("plugin_cap") is True

    def test_is_plugin_capability_false(self):
        """Test when capability not in plugin."""
        mock_plugin_manager = MagicMock()
        mock_plugin_manager.__contains__ = MagicMock(return_value=False)

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = mock_plugin_manager

        assert registry.is_plugin_capability("unknown") is False


class TestToolRegistryExecutePlugin:
    """Tests for execute_plugin method."""

    @pytest.mark.asyncio
    async def test_execute_plugin_no_manager(self):
        """Test execute when no plugin manager."""
        with patch.object(ToolRegistry, "_load_tools"):
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

        with patch.object(ToolRegistry, "_load_tools"):
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

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry._plugin_manager = mock_plugin_manager

        assert registry.requires_confirmation("plugin_cap") is True

    def test_requires_confirmation_legacy_true(self):
        """Test confirmation check for legacy tool requiring confirmation."""
        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = {
            "delete": {"confirmation_required": True}
        }

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry.wrappers["mailcraft"] = mock_wrapper

        assert registry.requires_confirmation("mailcraft_delete") is True

    def test_requires_confirmation_legacy_false(self):
        """Test confirmation check for legacy tool not requiring confirmation."""
        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = {
            "list": {"confirmation_required": False}
        }

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry.wrappers["mailcraft"] = mock_wrapper

        assert registry.requires_confirmation("mailcraft_list") is False

    def test_requires_confirmation_unknown_tool(self):
        """Test confirmation check for unknown tool."""
        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)

        assert registry.requires_confirmation("unknown_tool") is False

    def test_requires_confirmation_no_cmd_def(self):
        """Test confirmation when command definition missing field."""
        mock_wrapper = MagicMock()
        mock_wrapper.get_commands.return_value = {"cmd": {}}

        with patch.object(ToolRegistry, "_load_tools"):
            registry = ToolRegistry(enable_plugins=False)
            registry.wrappers["tool"] = mock_wrapper

        # Should default to False
        assert registry.requires_confirmation("tool_cmd") is False
