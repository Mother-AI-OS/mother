"""Tests for PluginResult and PluginInfo classes."""

from datetime import datetime

from mother.plugins.base import PluginInfo, PluginResult, ResultStatus


class TestPluginResult:
    """Tests for PluginResult dataclass and factory methods."""

    def test_success_result_minimal(self) -> None:
        """Test creating a minimal success result."""
        result = PluginResult.success_result()
        assert result.success is True
        assert result.status == ResultStatus.SUCCESS
        assert result.data is None
        assert result.error_message is None
        assert result.error_code is None

    def test_success_result_with_data(self) -> None:
        """Test success result with data."""
        data = {"key": "value", "count": 42}
        result = PluginResult.success_result(data=data)
        assert result.success is True
        assert result.data == data

    def test_success_result_with_raw_output(self) -> None:
        """Test success result with raw output."""
        result = PluginResult.success_result(raw_output="Command output here")
        assert result.raw_output == "Command output here"

    def test_success_result_with_execution_time(self) -> None:
        """Test success result with execution time."""
        result = PluginResult.success_result(execution_time=1.5)
        assert result.execution_time == 1.5

    def test_success_result_with_metadata(self) -> None:
        """Test success result with metadata."""
        result = PluginResult.success_result(custom_field="custom_value")
        assert result.metadata["custom_field"] == "custom_value"

    def test_error_result_minimal(self) -> None:
        """Test creating a minimal error result."""
        result = PluginResult.error_result("Something went wrong")
        assert result.success is False
        assert result.status == ResultStatus.ERROR
        assert result.error_message == "Something went wrong"
        assert result.error_code is None

    def test_error_result_with_code(self) -> None:
        """Test error result with error code."""
        result = PluginResult.error_result("Not found", code="NOT_FOUND")
        assert result.error_code == "NOT_FOUND"

    def test_error_result_with_raw_output(self) -> None:
        """Test error result with raw output."""
        result = PluginResult.error_result("Failed", raw_output="stderr content")
        assert result.raw_output == "stderr content"

    def test_timeout_result(self) -> None:
        """Test timeout result creation."""
        result = PluginResult.timeout_result(30)
        assert result.success is False
        assert result.status == ResultStatus.TIMEOUT
        assert "30" in result.error_message
        assert result.error_code == "TIMEOUT"

    def test_timeout_result_with_raw_output(self) -> None:
        """Test timeout result with partial output."""
        result = PluginResult.timeout_result(60, raw_output="Partial output...")
        assert result.raw_output == "Partial output..."

    def test_pending_confirmation(self) -> None:
        """Test pending confirmation result."""
        result = PluginResult.pending_confirmation(action_description="Delete all files", params={"path": "/tmp/test"})
        assert result.success is True
        assert result.status == ResultStatus.PENDING_CONFIRMATION
        assert result.data["action"] == "Delete all files"
        assert result.data["params"] == {"path": "/tmp/test"}

    def test_pending_confirmation_with_metadata(self) -> None:
        """Test pending confirmation with extra metadata."""
        result = PluginResult.pending_confirmation(
            action_description="Send email", params={"to": "test@example.com"}, severity="high"
        )
        assert result.metadata["severity"] == "high"

    def test_result_has_timestamp(self) -> None:
        """Test that results have a timestamp."""
        result = PluginResult.success_result()
        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        result = PluginResult.success_result(data={"key": "value"}, raw_output="output", execution_time=1.0)
        d = result.to_dict()
        assert d["success"] is True
        assert d["status"] == "success"
        assert d["data"] == {"key": "value"}
        assert d["raw_output"] == "output"
        assert d["execution_time"] == 1.0
        assert "timestamp" in d

    def test_str_representation_success(self) -> None:
        """Test string representation for success."""
        result = PluginResult.success_result(data={"test": True})
        s = str(result)
        assert "[OK]" in s

    def test_str_representation_error(self) -> None:
        """Test error string representation."""
        result = PluginResult.error_result("Failed to connect")
        s = str(result)
        assert "Failed to connect" in s

    def test_str_representation_pending(self) -> None:
        """Test pending confirmation string representation."""
        result = PluginResult.pending_confirmation(action_description="Delete files", params={})
        s = str(result)
        assert "PENDING" in s


class TestPluginInfo:
    """Tests for PluginInfo dataclass."""

    def test_plugin_info_creation(self) -> None:
        """Test basic PluginInfo creation."""
        info = PluginInfo(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            source="builtin",
            capabilities=["read", "write"],
        )
        assert info.name == "test-plugin"
        assert info.version == "1.0.0"
        assert info.description == "A test plugin"
        assert info.author == "Test Author"
        assert info.source == "builtin"
        assert info.capabilities == ["read", "write"]
        assert info.loaded is False
        assert info.error is None

    def test_plugin_info_loaded_state(self) -> None:
        """Test loaded plugin info."""
        info = PluginInfo(
            name="active-plugin",
            version="2.0.0",
            description="Active",
            author="Author",
            source="entry_point",
            capabilities=[],
            loaded=True,
        )
        assert info.loaded is True

    def test_plugin_info_failed(self) -> None:
        """Test creating failed plugin info."""
        info = PluginInfo.failed(name="broken-plugin", source="user", error="Module not found")
        assert info.name == "broken-plugin"
        assert info.source == "user"
        assert info.error == "Module not found"
        assert info.loaded is False


class TestResultStatus:
    """Tests for ResultStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values exist."""
        assert ResultStatus.SUCCESS.value == "success"
        assert ResultStatus.ERROR.value == "error"
        assert ResultStatus.TIMEOUT.value == "timeout"
        assert ResultStatus.PENDING_CONFIRMATION.value == "pending_confirmation"

    def test_status_comparison(self) -> None:
        """Test status comparison."""
        assert ResultStatus.SUCCESS == ResultStatus.SUCCESS
        assert ResultStatus.SUCCESS != ResultStatus.ERROR
