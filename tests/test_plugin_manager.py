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
