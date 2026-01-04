"""Tests for PluginManager and PluginConfig."""

from pathlib import Path

import pytest

from mother.plugins import (
    PluginConfig,
    PluginManager,
)


class TestPluginConfig:
    """Tests for PluginConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = PluginConfig()

        assert config.enabled is True
        assert config.user_plugins_dir == Path.home() / ".mother" / "plugins"
        assert config.project_plugins_dir is None
        assert config.builtin_plugins_dir is None
        assert config.disabled_plugins == []
        assert config.enabled_plugins is None
        assert config.plugin_settings == {}
        assert config.require_permissions is True
        assert config.default_timeout == 300
        assert config.auto_discover is True
        assert config.auto_load is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = PluginConfig(
            enabled=False,
            user_plugins_dir=Path("/custom/plugins"),
            disabled_plugins=["disabled-plugin"],
            enabled_plugins=["only-this"],
            plugin_settings={"my-plugin": {"key": "value"}},
            require_permissions=False,
            default_timeout=600,
            auto_discover=False,
            auto_load=False,
        )

        assert config.enabled is False
        assert config.user_plugins_dir == Path("/custom/plugins")
        assert config.disabled_plugins == ["disabled-plugin"]
        assert config.enabled_plugins == ["only-this"]
        assert config.plugin_settings == {"my-plugin": {"key": "value"}}
        assert config.require_permissions is False
        assert config.default_timeout == 600
        assert config.auto_discover is False
        assert config.auto_load is False

    def test_config_with_project_dir(self) -> None:
        """Test configuration with project plugins directory."""
        config = PluginConfig(
            project_plugins_dir=Path("/project/plugins"),
            builtin_plugins_dir=Path("/builtin/plugins"),
        )

        assert config.project_plugins_dir == Path("/project/plugins")
        assert config.builtin_plugins_dir == Path("/builtin/plugins")


class TestPluginManager:
    """Tests for PluginManager."""

    def test_manager_creation_default_config(self) -> None:
        """Test creating manager with default config."""
        manager = PluginManager()

        assert manager.config is not None
        assert manager.config.enabled is True
        assert manager._initialized is False

    def test_manager_creation_custom_config(self) -> None:
        """Test creating manager with custom config."""
        config = PluginConfig(
            enabled=True,
            disabled_plugins=["disabled"],
            default_timeout=600,
        )
        manager = PluginManager(config)

        assert manager.config is config
        assert manager.config.disabled_plugins == ["disabled"]
        assert manager.config.default_timeout == 600

    def test_manager_registry_property(self) -> None:
        """Test registry property."""
        manager = PluginManager()

        registry = manager.registry
        assert registry is not None
        assert len(registry) == 0

    def test_manager_loader_property(self) -> None:
        """Test loader property."""
        manager = PluginManager()

        loader = manager.loader
        assert loader is not None

    def test_manager_len(self) -> None:
        """Test __len__ method."""
        manager = PluginManager()
        assert len(manager) == 0

    def test_manager_contains(self) -> None:
        """Test __contains__ method."""
        manager = PluginManager()
        assert "nonexistent_capability" not in manager

    def test_list_plugins_empty(self) -> None:
        """Test listing plugins when empty."""
        manager = PluginManager()
        plugins = manager.list_plugins()
        assert plugins == {}

    def test_list_discovered_empty(self) -> None:
        """Test listing discovered plugins when empty."""
        manager = PluginManager()
        discovered = manager.list_discovered()
        assert discovered == {}

    def test_list_capabilities_empty(self) -> None:
        """Test listing capabilities when empty."""
        manager = PluginManager()
        caps = manager.list_capabilities()
        assert caps == []

    def test_get_capability_not_found(self) -> None:
        """Test getting non-existent capability."""
        manager = PluginManager()
        entry = manager.get_capability("nonexistent_action")
        assert entry is None

    def test_get_plugin_info_not_found(self) -> None:
        """Test getting info for non-existent plugin."""
        manager = PluginManager()
        info = manager.get_plugin_info("nonexistent")
        assert info is None

    def test_requires_confirmation_nonexistent(self) -> None:
        """Test requires_confirmation for non-existent capability."""
        manager = PluginManager()
        assert manager.requires_confirmation("nonexistent") is False

    def test_search_capabilities_empty(self) -> None:
        """Test searching capabilities when empty."""
        manager = PluginManager()
        results = manager.search_capabilities("query")
        assert results == []

    def test_get_all_schemas_empty(self) -> None:
        """Test getting schemas when empty."""
        manager = PluginManager()
        schemas = manager.get_all_schemas()
        assert schemas == []

    def test_is_loaded_false(self) -> None:
        """Test is_loaded for non-loaded plugin."""
        manager = PluginManager()
        assert manager.is_loaded("nonexistent") is False

    @pytest.mark.asyncio
    async def test_initialize_disabled(self) -> None:
        """Test initialize when disabled."""
        config = PluginConfig(enabled=False)
        manager = PluginManager(config)

        await manager.initialize()

        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_empty(self) -> None:
        """Test shutdown with no plugins."""
        manager = PluginManager()
        await manager.shutdown()

        assert manager._initialized is False

    def test_discover_returns_copy(self) -> None:
        """Test that discover returns a copy."""
        manager = PluginManager()

        # First discover
        discovered1 = manager.discover()

        # Modify the returned dict
        discovered1["fake"] = None

        # Second discover should not be affected
        discovered2 = manager.discover()
        assert "fake" not in discovered2


class TestPluginManagerIntegration:
    """Integration tests for PluginManager."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        """Test full plugin lifecycle: discover -> load -> execute -> unload."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        # Initialize
        await manager.initialize()

        # Should have plugins loaded
        plugins = manager.list_plugins()
        assert len(plugins) > 0

        # Should have capabilities
        caps = manager.list_capabilities()
        assert len(caps) > 0

        # Search for a capability
        results = manager.search_capabilities("read")
        assert isinstance(results, list)

        # Shutdown
        await manager.shutdown()
        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_execute_filesystem_list(self) -> None:
        """Test executing filesystem list_directory capability."""
        import tempfile

        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        # Create a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await manager.execute(
                "filesystem_list_directory",
                {"path": tmpdir},
            )

            assert result.success is True
            assert result.data is not None

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_all_schemas(self) -> None:
        """Test getting all schemas."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        schemas = manager.get_all_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_plugin_info(self) -> None:
        """Test getting plugin info."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        info = manager.get_plugin_info("filesystem")
        assert info is not None
        assert info.name == "filesystem"

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_reload_plugin(self) -> None:
        """Test reloading a plugin."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        # Reload filesystem
        await manager.reload("filesystem")

        # Should still be loaded
        assert manager.is_loaded("filesystem")

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_list_discovered(self) -> None:
        """Test listing discovered plugins."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        discovered = manager.list_discovered()
        assert isinstance(discovered, dict)
        assert len(discovered) > 0

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_parse_capability_name(self) -> None:
        """Test parsing capability names."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        # Parse an existing capability name
        plugin, cap = manager.parse_capability_name("filesystem_read_file")
        assert plugin == "filesystem"
        assert cap == "read_file"

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_contains_capability(self) -> None:
        """Test __contains__ for capabilities."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        assert "filesystem_list_directory" in manager
        assert "nonexistent_capability" not in manager

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_len(self) -> None:
        """Test __len__ returns capability count."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        assert len(manager) > 0

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_requires_confirmation(self) -> None:
        """Test checking if capability requires confirmation."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        # filesystem_read_file should not require confirmation
        assert manager.requires_confirmation("filesystem_read_file") is False

        # shell_run_command should require confirmation
        assert manager.requires_confirmation("shell_run_command") is True

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_capability(self) -> None:
        """Test getting a capability entry."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        entry = manager.get_capability("filesystem_read_file")
        assert entry is not None
        assert entry.plugin_name == "filesystem"

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_list_capabilities_filtered(self) -> None:
        """Test listing capabilities filtered by plugin."""
        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        caps = manager.list_capabilities("filesystem")
        assert len(caps) > 0
        for cap in caps:
            assert cap.startswith("filesystem_")

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_load_and_unload(self) -> None:
        """Test loading and unloading a plugin."""
        config = PluginConfig(require_permissions=False, auto_load=False)
        manager = PluginManager(config)

        # Discover but don't load
        manager.discover()

        # Manually load filesystem
        await manager.load("filesystem")
        assert manager.is_loaded("filesystem")

        # Unload
        await manager.unload("filesystem")
        assert not manager.is_loaded("filesystem")

    @pytest.mark.asyncio
    async def test_load_all_after_discover(self) -> None:
        """Test load_all loads all discovered plugins."""
        config = PluginConfig(require_permissions=False, auto_load=False, auto_discover=False)
        manager = PluginManager(config)

        # Discover plugins
        discovered = manager.discover()
        assert len(discovered) > 0

        # Load all
        loaded = await manager.load_all()
        assert len(loaded) > 0

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_discover_with_enabled_plugins_filter(self) -> None:
        """Test discover filters by enabled_plugins list."""
        config = PluginConfig(
            enabled_plugins=["filesystem"],
            auto_discover=False,
            auto_load=False,
            require_permissions=False,
        )
        manager = PluginManager(config)

        discovered = manager.discover()

        # Should only have filesystem
        assert "filesystem" in discovered
        assert "shell" not in discovered
        assert "web" not in discovered

    @pytest.mark.asyncio
    async def test_discover_with_disabled_plugins_filter(self) -> None:
        """Test discover filters out disabled_plugins."""
        config = PluginConfig(
            disabled_plugins=["web"],
            auto_discover=False,
            auto_load=False,
            require_permissions=False,
        )
        manager = PluginManager(config)

        discovered = manager.discover()

        # web should be filtered out
        assert "web" not in discovered
        # but others should be there
        assert "filesystem" in discovered

    @pytest.mark.asyncio
    async def test_execute_with_permission_check(self) -> None:
        """Test execute with permission checking enabled."""
        config = PluginConfig(require_permissions=True)
        manager = PluginManager(config)

        await manager.initialize()

        # Create a temp directory
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await manager.execute(
                "filesystem_list_directory",
                {"path": tmpdir},
            )

            # Should succeed (filesystem has appropriate permissions)
            assert result.success is True

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_execute_confirmation_required(self) -> None:
        """Test execute returns pending confirmation for destructive action."""
        from mother.plugins import ResultStatus

        config = PluginConfig(require_permissions=False)
        manager = PluginManager(config)

        await manager.initialize()

        # shell_run_command requires confirmation
        result = await manager.execute(
            "shell_run_command",
            {"command": "echo hello"},
        )

        # Should return pending confirmation
        assert result.status == ResultStatus.PENDING_CONFIRMATION

        await manager.shutdown()
