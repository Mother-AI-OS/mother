"""Tests for PluginRegistry and CapabilityEntry."""

from unittest.mock import MagicMock

import pytest

from mother.plugins.exceptions import CapabilityNotFoundError
from mother.plugins.manifest import (
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
)
from mother.plugins.registry import CapabilityEntry, PluginRegistry


def create_mock_manifest(
    name: str,
    capabilities: list[tuple[str, str]],
) -> PluginManifest:
    """Create a mock manifest for testing.

    Args:
        name: Plugin name
        capabilities: List of (capability_name, description) tuples
    """
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(name=name, version="1.0.0", description=f"Test {name}", author="Test Author"),
        capabilities=[CapabilitySpec(name=cap_name, description=desc) for cap_name, desc in capabilities],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(module="test", **{"class": "Test"}),
        ),
    )


def create_mock_executor() -> MagicMock:
    """Create a mock executor for testing."""
    return MagicMock()


class TestCapabilityEntry:
    """Tests for CapabilityEntry dataclass."""

    def test_entry_creation(self) -> None:
        """Test creating a capability entry."""
        spec = CapabilitySpec(name="search", description="Search items")
        executor = create_mock_executor()

        entry = CapabilityEntry(
            plugin_name="my-plugin",
            capability_name="search",
            full_name="my-plugin_search",
            spec=spec,
            executor=executor,
        )

        assert entry.plugin_name == "my-plugin"
        assert entry.capability_name == "search"
        assert entry.full_name == "my-plugin_search"
        assert entry.confirmation_required is False

    def test_entry_with_confirmation(self) -> None:
        """Test entry with confirmation required."""
        spec = CapabilitySpec(name="delete", description="Delete items", confirmation_required=True)
        executor = create_mock_executor()

        entry = CapabilityEntry(
            plugin_name="my-plugin",
            capability_name="delete",
            full_name="my-plugin_delete",
            spec=spec,
            executor=executor,
            confirmation_required=True,
        )

        assert entry.confirmation_required is True

    def test_anthropic_schema_property(self) -> None:
        """Test getting Anthropic schema from entry."""
        spec = CapabilitySpec(
            name="search",
            description="Search items",
            parameters=[
                ParameterSpec(name="query", type=ParameterType.STRING, required=True),
            ],
        )
        executor = create_mock_executor()

        entry = CapabilityEntry(
            plugin_name="test-plugin",
            capability_name="search",
            full_name="test-plugin_search",
            spec=spec,
            executor=executor,
        )

        schema = entry.anthropic_schema
        assert schema["name"] == "test-plugin_search"
        assert schema["description"] == "Search items"
        assert "input_schema" in schema


class TestPluginRegistry:
    """Tests for PluginRegistry."""

    def test_registry_creation(self) -> None:
        """Test creating an empty registry."""
        registry = PluginRegistry()
        assert len(registry) == 0

    def test_register_plugin(self) -> None:
        """Test registering a plugin."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("test-plugin", [("action", "Do action")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        assert len(registry) == 1
        assert registry.get_plugin("test-plugin") is executor
        assert registry.get_manifest("test-plugin") is manifest

    def test_register_multiple_capabilities(self) -> None:
        """Test registering plugin with multiple capabilities."""
        registry = PluginRegistry()
        manifest = create_mock_manifest(
            "multi-plugin",
            [("read", "Read data"), ("write", "Write data"), ("delete", "Delete data")],
        )
        executor = create_mock_executor()

        registry.register(manifest, executor)

        assert len(registry) == 3
        assert "multi-plugin_read" in registry
        assert "multi-plugin_write" in registry
        assert "multi-plugin_delete" in registry

    def test_unregister_plugin(self) -> None:
        """Test unregistering a plugin."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("test-plugin", [("action", "Do action")])
        executor = create_mock_executor()

        registry.register(manifest, executor)
        assert len(registry) == 1

        registry.unregister("test-plugin")

        assert len(registry) == 0
        assert registry.get_plugin("test-plugin") is None
        assert registry.get_manifest("test-plugin") is None
        assert "test-plugin_action" not in registry

    def test_unregister_nonexistent(self) -> None:
        """Test unregistering a non-existent plugin (should not raise)."""
        registry = PluginRegistry()
        registry.unregister("nonexistent")  # Should not raise

    def test_get_capability(self) -> None:
        """Test getting capability by full name."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("test-plugin", [("search", "Search")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        entry = registry.get_capability("test-plugin_search")
        assert entry is not None
        assert entry.plugin_name == "test-plugin"
        assert entry.capability_name == "search"

    def test_get_capability_not_found(self) -> None:
        """Test getting non-existent capability."""
        registry = PluginRegistry()
        entry = registry.get_capability("nonexistent_action")
        assert entry is None

    def test_get_capability_by_parts(self) -> None:
        """Test getting capability by plugin and capability names."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("my-plugin", [("do_action", "Action")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        entry = registry.get_capability_by_parts("my-plugin", "do_action")
        assert entry is not None
        assert entry.full_name == "my-plugin_do_action"

    def test_parse_capability_name_simple(self) -> None:
        """Test parsing simple capability name."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("plugin", [("action", "Action")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        plugin_name, cap_name = registry.parse_capability_name("plugin_action")
        assert plugin_name == "plugin"
        assert cap_name == "action"

    def test_parse_capability_name_with_underscore(self) -> None:
        """Test parsing capability name with underscores in capability name."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("my-plugin", [("do_action", "Action")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        plugin_name, cap_name = registry.parse_capability_name("my-plugin_do_action")
        assert plugin_name == "my-plugin"
        assert cap_name == "do_action"

    def test_parse_capability_name_not_found(self) -> None:
        """Test parsing non-existent capability name."""
        registry = PluginRegistry()

        with pytest.raises(CapabilityNotFoundError):
            registry.parse_capability_name("nonexistent_action")

    def test_list_plugins(self) -> None:
        """Test listing all plugins."""
        registry = PluginRegistry()
        manifest1 = create_mock_manifest("plugin-a", [("action", "Action")])
        manifest2 = create_mock_manifest("plugin-b", [("other", "Other")])

        registry.register(manifest1, create_mock_executor())
        registry.register(manifest2, create_mock_executor())

        plugins = registry.list_plugins()
        assert "plugin-a" in plugins
        assert "plugin-b" in plugins

    def test_list_capabilities_all(self) -> None:
        """Test listing all capabilities."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("plugin", [("a", "A"), ("b", "B")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        caps = registry.list_capabilities()
        assert "plugin_a" in caps
        assert "plugin_b" in caps

    def test_list_capabilities_filtered(self) -> None:
        """Test listing capabilities filtered by plugin."""
        registry = PluginRegistry()
        manifest1 = create_mock_manifest("plugin-a", [("x", "X")])
        manifest2 = create_mock_manifest("plugin-b", [("y", "Y")])

        registry.register(manifest1, create_mock_executor())
        registry.register(manifest2, create_mock_executor())

        caps = registry.list_capabilities("plugin-a")
        assert "plugin-a_x" in caps
        assert "plugin-b_y" not in caps

    def test_get_all_anthropic_schemas(self) -> None:
        """Test getting all Anthropic schemas."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("plugin", [("a", "A"), ("b", "B")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        schemas = registry.get_all_anthropic_schemas()
        assert len(schemas) == 2
        names = [s["name"] for s in schemas]
        assert "plugin_a" in names
        assert "plugin_b" in names

    def test_get_plugin_schemas(self) -> None:
        """Test getting schemas for specific plugin."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("my-plugin", [("action", "Action")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        schemas = registry.get_plugin_schemas("my-plugin")
        assert len(schemas) == 1
        assert schemas[0]["name"] == "my-plugin_action"

    def test_requires_confirmation_true(self) -> None:
        """Test checking confirmation requirement (true)."""
        registry = PluginRegistry()
        manifest = PluginManifest(
            schema_version="1.0",
            plugin=PluginMetadata(name="plugin", version="1.0.0", description="Test", author="Test Author"),
            capabilities=[CapabilitySpec(name="delete", description="Delete", confirmation_required=True)],
            execution=ExecutionSpec(
                type=ExecutionType.PYTHON,
                python=PythonExecutionSpec(module="t", **{"class": "T"}),
            ),
        )
        executor = create_mock_executor()

        registry.register(manifest, executor)

        assert registry.requires_confirmation("plugin_delete") is True

    def test_requires_confirmation_false(self) -> None:
        """Test checking confirmation requirement (false)."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("plugin", [("action", "Action")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        assert registry.requires_confirmation("plugin_action") is False

    def test_requires_confirmation_not_found(self) -> None:
        """Test checking confirmation for non-existent capability."""
        registry = PluginRegistry()
        assert registry.requires_confirmation("nonexistent") is False

    def test_search_capabilities_by_name(self) -> None:
        """Test searching capabilities by name."""
        registry = PluginRegistry()
        manifest = create_mock_manifest(
            "plugin",
            [
                ("send_email", "Send an email"),
                ("read_file", "Read a file"),
                ("send_sms", "Send SMS"),
            ],
        )
        executor = create_mock_executor()

        registry.register(manifest, executor)

        results = registry.search_capabilities("send")
        assert len(results) >= 2

        # Both send capabilities should be in results
        result_names = [r.capability_name for r in results]
        assert "send_email" in result_names
        assert "send_sms" in result_names

    def test_search_capabilities_by_description(self) -> None:
        """Test searching capabilities by description."""
        registry = PluginRegistry()
        manifest = create_mock_manifest(
            "plugin",
            [
                ("action_a", "Send an email message"),
                ("action_b", "Read a file"),
            ],
        )
        executor = create_mock_executor()

        registry.register(manifest, executor)

        results = registry.search_capabilities("email")
        assert len(results) >= 1
        assert any(r.capability_name == "action_a" for r in results)

    def test_search_capabilities_limit(self) -> None:
        """Test search with limit."""
        registry = PluginRegistry()
        manifest = create_mock_manifest(
            "plugin",
            [(f"cap_{i}", f"Capability {i}") for i in range(20)],
        )
        executor = create_mock_executor()

        registry.register(manifest, executor)

        results = registry.search_capabilities("cap", limit=5)
        assert len(results) <= 5

    def test_contains(self) -> None:
        """Test __contains__ method."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("plugin", [("action", "Action")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        assert "plugin_action" in registry
        assert "nonexistent" not in registry

    def test_len(self) -> None:
        """Test __len__ method."""
        registry = PluginRegistry()
        assert len(registry) == 0

        manifest = create_mock_manifest("plugin", [("a", "A"), ("b", "B")])
        registry.register(manifest, create_mock_executor())

        assert len(registry) == 2

    def test_parse_capability_name_first_underscore_split(self) -> None:
        """Test parsing where first split matches (covers line 187)."""
        registry = PluginRegistry()
        # Plugin with no underscore, capability with underscore
        manifest = create_mock_manifest("plugin", [("complex_action", "Complex action")])
        executor = create_mock_executor()

        registry.register(manifest, executor)

        # First split: plugin="plugin", cap="complex_action" - should match line 186-187
        plugin_name, cap_name = registry.parse_capability_name("plugin_complex_action")
        assert plugin_name == "plugin"
        assert cap_name == "complex_action"

    def test_parse_capability_name_underscore_plugin_direct(self) -> None:
        """Test parsing with underscore plugin name via direct registry manipulation (covers lines 192-199).

        Plugin names normally can't have underscores (validation enforced at manifest level),
        but this tests the fallback parsing logic by directly populating the registry.
        """
        registry = PluginRegistry()
        spec = CapabilitySpec(name="action", description="Action")
        executor = create_mock_executor()

        # Directly add an entry with underscore plugin name (bypassing manifest validation)
        entry = CapabilityEntry(
            plugin_name="my_plugin",
            capability_name="action",
            full_name="my_plugin_action",
            spec=spec,
            executor=executor,
        )
        registry._capabilities["my_plugin_action"] = entry
        registry._plugin_capabilities["my_plugin"] = ["my_plugin_action"]

        # Now parse - should correctly identify via loop on lines 192-199
        plugin_name, cap_name = registry.parse_capability_name("my_plugin_action")
        assert plugin_name == "my_plugin"
        assert cap_name == "action"

    def test_parse_capability_name_multiple_underscores_direct(self) -> None:
        """Test parsing with multiple underscores in plugin name via direct registry manipulation."""
        registry = PluginRegistry()
        spec = CapabilitySpec(name="do_action", description="Do action")
        executor = create_mock_executor()

        # Directly add an entry with multi-underscore plugin name
        entry = CapabilityEntry(
            plugin_name="my_cool_plugin",
            capability_name="do_action",
            full_name="my_cool_plugin_do_action",
            spec=spec,
            executor=executor,
        )
        registry._capabilities["my_cool_plugin_do_action"] = entry
        registry._plugin_capabilities["my_cool_plugin"] = ["my_cool_plugin_do_action"]

        # Parse - should correctly identify via loop
        plugin_name, cap_name = registry.parse_capability_name("my_cool_plugin_do_action")
        assert plugin_name == "my_cool_plugin"
        assert cap_name == "do_action"

    def test_search_capabilities_by_plugin_name(self) -> None:
        """Test searching capabilities by plugin name (covers line 295)."""
        registry = PluginRegistry()
        manifest1 = create_mock_manifest(
            "mailcraft",
            [("send", "Send mail"), ("receive", "Receive mail")],
        )
        manifest2 = create_mock_manifest(
            "filesystem",
            [("read", "Read file"), ("write", "Write file")],
        )

        registry.register(manifest1, create_mock_executor())
        registry.register(manifest2, create_mock_executor())

        # Search by plugin name - should find mailcraft capabilities
        results = registry.search_capabilities("mailcraft")
        assert len(results) >= 2

        # All results should be from mailcraft plugin
        result_plugins = [r.plugin_name for r in results]
        assert all(p == "mailcraft" for p in result_plugins)

    def test_list_capabilities_nonexistent_plugin(self) -> None:
        """Test listing capabilities for non-existent plugin returns empty list."""
        registry = PluginRegistry()
        manifest = create_mock_manifest("plugin", [("action", "Action")])
        registry.register(manifest, create_mock_executor())

        caps = registry.list_capabilities("nonexistent")
        assert caps == []

    def test_get_plugin_schemas_nonexistent(self) -> None:
        """Test getting schemas for non-existent plugin returns empty list."""
        registry = PluginRegistry()
        schemas = registry.get_plugin_schemas("nonexistent")
        assert schemas == []
