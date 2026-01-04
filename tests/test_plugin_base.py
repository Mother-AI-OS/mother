"""Tests for PluginBase and related base classes."""

from typing import Any

import pytest

from mother.plugins.base import PluginBase, PluginInfo, PluginResult, ResultStatus
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


def create_test_manifest() -> PluginManifest:
    """Create a test manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
        ),
        capabilities=[
            CapabilitySpec(
                name="do_action",
                description="Do an action",
                parameters=[
                    ParameterSpec(name="input", type=ParameterType.STRING),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(module="test", **{"class": "TestPlugin"}),
        ),
    )


class TestPluginInfo:
    """Tests for PluginInfo class."""

    def test_from_manifest(self) -> None:
        """Test creating PluginInfo from manifest."""
        manifest = create_test_manifest()
        info = PluginInfo.from_manifest(manifest, "test")

        assert info.name == "test-plugin"
        assert info.version == "1.0.0"
        assert info.description == "Test plugin"
        assert info.author == "Test Author"
        assert info.source == "test"
        assert "do_action" in info.capabilities
        assert info.loaded is True
        assert info.error is None

    def test_failed(self) -> None:
        """Test creating failed PluginInfo."""
        info = PluginInfo.failed("broken-plugin", "test", "Something went wrong")

        assert info.name == "broken-plugin"
        assert info.source == "test"
        assert info.loaded is False
        assert info.error == "Something went wrong"
        assert info.capabilities == []


class TestResultStatus:
    """Tests for ResultStatus enum."""

    def test_all_statuses(self) -> None:
        """Test all status values."""
        assert ResultStatus.SUCCESS.value == "success"
        assert ResultStatus.ERROR.value == "error"
        assert ResultStatus.TIMEOUT.value == "timeout"
        assert ResultStatus.PENDING_CONFIRMATION.value == "pending_confirmation"


class TestPluginBase:
    """Tests for PluginBase abstract class."""

    def test_plugin_creation(self) -> None:
        """Test creating a plugin subclass."""

        class TestPlugin(PluginBase):
            async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
                if capability == "do_action":
                    return PluginResult.success_result(data={"done": True})
                return PluginResult.error_result("Unknown", code="UNKNOWN")

        manifest = create_test_manifest()
        plugin = TestPlugin(manifest)

        assert plugin.manifest is manifest
        assert plugin.name == "test-plugin"

    def test_plugin_with_config(self) -> None:
        """Test creating a plugin with config."""

        class TestPlugin(PluginBase):
            async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
                return PluginResult.success_result()

        manifest = create_test_manifest()
        config = {"key": "value"}
        plugin = TestPlugin(manifest, config)

        assert plugin._config == config

    @pytest.mark.asyncio
    async def test_plugin_execute(self) -> None:
        """Test plugin execution."""

        class TestPlugin(PluginBase):
            async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
                if capability == "do_action":
                    input_val = params.get("input", "")
                    return PluginResult.success_result(data={"result": f"Processed: {input_val}"})
                return PluginResult.error_result("Unknown", code="UNKNOWN")

        manifest = create_test_manifest()
        plugin = TestPlugin(manifest)

        result = await plugin.execute("do_action", {"input": "test"})

        assert result.success is True
        assert result.data["result"] == "Processed: test"

    @pytest.mark.asyncio
    async def test_plugin_initialize_and_shutdown(self) -> None:
        """Test plugin lifecycle methods."""

        class TestPlugin(PluginBase):
            def __init__(self, manifest: PluginManifest, config: dict | None = None):
                super().__init__(manifest, config)
                self.initialized = False
                self.shutdown_called = False

            async def initialize(self) -> None:
                self.initialized = True

            async def shutdown(self) -> None:
                self.shutdown_called = True

            async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
                return PluginResult.success_result()

        manifest = create_test_manifest()
        plugin = TestPlugin(manifest)

        await plugin.initialize()
        assert plugin.initialized is True

        await plugin.shutdown()
        assert plugin.shutdown_called is True


class TestPluginResultMethods:
    """Additional tests for PluginResult methods."""

    def test_success_result_all_params(self) -> None:
        """Test success result with all parameters."""
        result = PluginResult.success_result(
            data={"key": "value"},
            raw_output="Raw output text",
            execution_time=1.5,
            extra_meta="extra",
        )

        assert result.success is True
        assert result.status == ResultStatus.SUCCESS
        assert result.data == {"key": "value"}
        assert result.raw_output == "Raw output text"
        assert result.execution_time == 1.5
        assert result.metadata["extra_meta"] == "extra"

    def test_error_result_all_params(self) -> None:
        """Test error result with all parameters."""
        result = PluginResult.error_result(
            "Error message",
            code="ERROR_CODE",
            raw_output="stderr",
        )

        assert result.success is False
        assert result.status == ResultStatus.ERROR
        assert result.error_message == "Error message"
        assert result.error_code == "ERROR_CODE"
        assert result.raw_output == "stderr"

    def test_timeout_result(self) -> None:
        """Test timeout result."""
        result = PluginResult.timeout_result(60)

        assert result.success is False
        assert result.status == ResultStatus.TIMEOUT
        assert result.error_code == "TIMEOUT"
        assert "60" in result.error_message

    def test_pending_confirmation_all_params(self) -> None:
        """Test pending confirmation with all parameters."""
        result = PluginResult.pending_confirmation(
            action_description="Delete all files",
            params={"path": "/tmp"},
            severity="high",
        )

        assert result.success is True
        assert result.status == ResultStatus.PENDING_CONFIRMATION
        assert result.data["action"] == "Delete all files"
        assert result.data["params"] == {"path": "/tmp"}
        assert result.metadata["severity"] == "high"

    def test_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = PluginResult.success_result(data={"key": "value"})
        d = result.to_dict()

        assert d["success"] is True
        assert d["status"] == "success"
        assert d["data"] == {"key": "value"}
        assert "timestamp" in d


class TestPluginBaseProperties:
    """Tests for PluginBase property accessors."""

    def create_plugin(self):
        """Create a test plugin instance."""
        class TestPlugin(PluginBase):
            async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
                return PluginResult.success_result()

        manifest = PluginManifest(
            schema_version="1.0",
            plugin=PluginMetadata(
                name="property-test",
                version="2.0.0",
                description="Property test plugin",
                author="Test Author",
            ),
            capabilities=[
                CapabilitySpec(
                    name="test_cap",
                    description="Test capability",
                    confirmation_required=True,
                    parameters=[
                        ParameterSpec(name="required_str", type=ParameterType.STRING, required=True),
                        ParameterSpec(name="optional_int", type=ParameterType.INTEGER),
                        ParameterSpec(name="number_val", type=ParameterType.NUMBER),
                        ParameterSpec(name="bool_val", type=ParameterType.BOOLEAN),
                        ParameterSpec(name="array_val", type=ParameterType.ARRAY),
                        ParameterSpec(name="object_val", type=ParameterType.OBJECT),
                        ParameterSpec(name="choice_val", type=ParameterType.STRING, choices=["a", "b"]),
                    ],
                ),
            ],
            execution=ExecutionSpec(
                type=ExecutionType.PYTHON,
                python=PythonExecutionSpec(module="test", **{"class": "TestPlugin"}),
            ),
        )
        return TestPlugin(manifest, config={"setting": "value"})

    def test_version_property(self):
        """Test version property."""
        plugin = self.create_plugin()
        assert plugin.version == "2.0.0"

    def test_config_property(self):
        """Test config property."""
        plugin = self.create_plugin()
        assert plugin.config == {"setting": "value"}

    def test_get_capabilities(self):
        """Test get_capabilities method."""
        plugin = self.create_plugin()
        caps = plugin.get_capabilities()
        assert len(caps) == 1
        assert caps[0].name == "test_cap"

    def test_get_capability(self):
        """Test get_capability method."""
        plugin = self.create_plugin()
        cap = plugin.get_capability("test_cap")
        assert cap is not None
        assert cap.name == "test_cap"

    def test_get_capability_not_found(self):
        """Test get_capability returns None for unknown."""
        plugin = self.create_plugin()
        cap = plugin.get_capability("unknown")
        assert cap is None

    def test_has_capability_true(self):
        """Test has_capability returns True."""
        plugin = self.create_plugin()
        assert plugin.has_capability("test_cap") is True

    def test_has_capability_false(self):
        """Test has_capability returns False."""
        plugin = self.create_plugin()
        assert plugin.has_capability("unknown") is False

    def test_get_anthropic_schemas(self):
        """Test get_anthropic_schemas."""
        plugin = self.create_plugin()
        schemas = plugin.get_anthropic_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "property-test_test_cap"

    def test_requires_confirmation_true(self):
        """Test requires_confirmation returns True."""
        plugin = self.create_plugin()
        assert plugin.requires_confirmation("test_cap") is True

    def test_requires_confirmation_false(self):
        """Test requires_confirmation returns False for unknown."""
        plugin = self.create_plugin()
        assert plugin.requires_confirmation("unknown") is False

    def test_repr(self):
        """Test __repr__ method."""
        plugin = self.create_plugin()
        assert repr(plugin) == "<Plugin property-test@2.0.0>"


class TestPluginBaseValidateParams:
    """Tests for PluginBase.validate_params method."""

    def create_plugin(self):
        """Create a test plugin instance."""
        class TestPlugin(PluginBase):
            async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
                return PluginResult.success_result()

        manifest = PluginManifest(
            schema_version="1.0",
            plugin=PluginMetadata(
                name="validate-test",
                version="1.0.0",
                description="Validation test plugin",
                author="Test Author",
            ),
            capabilities=[
                CapabilitySpec(
                    name="validate_cap",
                    description="Validation capability",
                    parameters=[
                        ParameterSpec(name="required_str", type=ParameterType.STRING, required=True),
                        ParameterSpec(name="optional_int", type=ParameterType.INTEGER),
                        ParameterSpec(name="number_val", type=ParameterType.NUMBER),
                        ParameterSpec(name="bool_val", type=ParameterType.BOOLEAN),
                        ParameterSpec(name="array_val", type=ParameterType.ARRAY),
                        ParameterSpec(name="object_val", type=ParameterType.OBJECT),
                        ParameterSpec(name="choice_val", type=ParameterType.STRING, choices=["a", "b"]),
                    ],
                ),
            ],
            execution=ExecutionSpec(
                type=ExecutionType.PYTHON,
                python=PythonExecutionSpec(module="test", **{"class": "TestPlugin"}),
            ),
        )
        return TestPlugin(manifest)

    def test_validate_unknown_capability(self):
        """Test validation returns error for unknown capability."""
        plugin = self.create_plugin()
        errors = plugin.validate_params("unknown", {})
        assert len(errors) == 1
        assert "Unknown capability" in errors[0]

    def test_validate_missing_required(self):
        """Test validation catches missing required parameter."""
        plugin = self.create_plugin()
        errors = plugin.validate_params("validate_cap", {})
        assert any("required_str" in e for e in errors)

    def test_validate_valid_params(self):
        """Test validation passes for valid params."""
        plugin = self.create_plugin()
        errors = plugin.validate_params("validate_cap", {"required_str": "hello"})
        assert len(errors) == 0

    def test_validate_wrong_string_type(self):
        """Test validation catches wrong string type."""
        plugin = self.create_plugin()
        errors = plugin.validate_params("validate_cap", {"required_str": 123})
        assert any("must be a string" in e for e in errors)

    def test_validate_wrong_integer_type(self):
        """Test validation catches wrong integer type."""
        plugin = self.create_plugin()
        errors = plugin.validate_params("validate_cap", {"required_str": "ok", "optional_int": "bad"})
        assert any("must be an integer" in e for e in errors)

    def test_validate_wrong_number_type(self):
        """Test validation catches wrong number type."""
        plugin = self.create_plugin()
        errors = plugin.validate_params("validate_cap", {"required_str": "ok", "number_val": "bad"})
        assert any("must be a number" in e for e in errors)

    def test_validate_wrong_boolean_type(self):
        """Test validation catches wrong boolean type."""
        plugin = self.create_plugin()
        errors = plugin.validate_params("validate_cap", {"required_str": "ok", "bool_val": "bad"})
        assert any("must be a boolean" in e for e in errors)

    def test_validate_wrong_array_type(self):
        """Test validation catches wrong array type."""
        plugin = self.create_plugin()
        errors = plugin.validate_params("validate_cap", {"required_str": "ok", "array_val": "bad"})
        assert any("must be an array" in e for e in errors)

    def test_validate_wrong_object_type(self):
        """Test validation catches wrong object type."""
        plugin = self.create_plugin()
        errors = plugin.validate_params("validate_cap", {"required_str": "ok", "object_val": "bad"})
        assert any("must be an object" in e for e in errors)

    def test_validate_invalid_choice(self):
        """Test validation catches invalid choice."""
        plugin = self.create_plugin()
        errors = plugin.validate_params("validate_cap", {"required_str": "ok", "choice_val": "c"})
        assert any("must be one of" in e for e in errors)
