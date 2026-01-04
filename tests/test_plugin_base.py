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
