"""Tests for plugin system exceptions."""

from mother.plugins.exceptions import (
    CapabilityNotFoundError,
    ConfigurationError,
    DependencyError,
    ExecutionError,
    ManifestError,
    ManifestNotFoundError,
    PermissionError,
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginTimeoutError,
    PluginValidationError,
)


class TestPluginError:
    """Tests for base PluginError."""

    def test_error_with_plugin_name(self) -> None:
        """Test error with plugin name."""
        error = PluginError("Something failed", plugin_name="my-plugin")
        assert error.plugin_name == "my-plugin"
        assert error.message == "Something failed"
        assert "[my-plugin]" in str(error)
        assert "Something failed" in str(error)

    def test_error_without_plugin_name(self) -> None:
        """Test error without plugin name."""
        error = PluginError("Generic error")
        assert error.plugin_name is None
        assert str(error) == "Generic error"


class TestPluginNotFoundError:
    """Tests for PluginNotFoundError."""

    def test_basic_not_found(self) -> None:
        """Test basic not found error."""
        error = PluginNotFoundError("missing-plugin")
        assert error.plugin_name == "missing-plugin"
        assert "not found" in str(error).lower()

    def test_with_searched_locations(self) -> None:
        """Test with searched locations."""
        error = PluginNotFoundError(
            "missing-plugin",
            searched_locations=["/path/a", "/path/b"],
        )
        assert error.searched_locations == ["/path/a", "/path/b"]
        assert "/path/a" in str(error)
        assert "/path/b" in str(error)

    def test_empty_searched_locations(self) -> None:
        """Test with empty searched locations."""
        error = PluginNotFoundError("missing-plugin", searched_locations=[])
        assert error.searched_locations == []
        assert "default locations" in str(error)


class TestPluginLoadError:
    """Tests for PluginLoadError."""

    def test_load_error_basic(self) -> None:
        """Test basic load error."""
        error = PluginLoadError("broken-plugin", "Module not found")
        assert error.plugin_name == "broken-plugin"
        assert error.reason == "Module not found"
        assert "Failed to load" in str(error)

    def test_load_error_with_cause(self) -> None:
        """Test load error with cause exception."""
        cause = ImportError("No module named 'foo'")
        error = PluginLoadError("broken-plugin", "Import failed", cause=cause)
        assert error.cause is cause
        assert isinstance(error.cause, ImportError)


class TestManifestError:
    """Tests for ManifestError."""

    def test_manifest_error_single(self) -> None:
        """Test manifest error with single error."""
        error = ManifestError("my-plugin", "Missing required field 'name'")
        assert error.errors == ["Missing required field 'name'"]
        assert "Invalid manifest" in str(error)

    def test_manifest_error_multiple(self) -> None:
        """Test manifest error with multiple errors."""
        errors = ["Missing field 'name'", "Invalid version format"]
        error = ManifestError("my-plugin", errors)
        assert len(error.errors) == 2
        assert "Missing field 'name'" in str(error)
        assert "Invalid version format" in str(error)


class TestManifestNotFoundError:
    """Tests for ManifestNotFoundError."""

    def test_manifest_not_found(self) -> None:
        """Test manifest not found error."""
        error = ManifestNotFoundError("my-plugin", "/path/to/manifest.yaml")
        assert error.plugin_name == "my-plugin"
        assert error.manifest_path == "/path/to/manifest.yaml"
        assert "not found" in str(error).lower()
        assert "/path/to/manifest.yaml" in str(error)


class TestDependencyError:
    """Tests for DependencyError."""

    def test_missing_dependencies(self) -> None:
        """Test error with missing dependencies."""
        error = DependencyError("my-plugin", missing=["requests", "numpy"])
        assert error.missing == ["requests", "numpy"]
        assert error.incompatible == []
        assert "missing" in str(error)
        assert "requests" in str(error)

    def test_incompatible_dependencies(self) -> None:
        """Test error with incompatible dependencies."""
        incompatible = [("requests", "2.0.0", ">=3.0.0")]
        error = DependencyError("my-plugin", incompatible=incompatible)
        assert error.missing == []
        assert len(error.incompatible) == 1
        assert "incompatible" in str(error)

    def test_both_missing_and_incompatible(self) -> None:
        """Test error with both missing and incompatible."""
        error = DependencyError(
            "my-plugin",
            missing=["numpy"],
            incompatible=[("requests", "2.0", ">=3.0")],
        )
        assert len(error.missing) == 1
        assert len(error.incompatible) == 1


class TestCapabilityNotFoundError:
    """Tests for CapabilityNotFoundError."""

    def test_capability_not_found_basic(self) -> None:
        """Test basic capability not found."""
        error = CapabilityNotFoundError("send_email")
        assert error.capability_name == "send_email"
        assert "send_email" in str(error)
        assert "not found" in str(error).lower()

    def test_capability_not_found_with_plugin(self) -> None:
        """Test capability not found with plugin name."""
        error = CapabilityNotFoundError("send_email", plugin_name="mailcraft")
        assert error.capability_name == "send_email"
        assert error.plugin_name == "mailcraft"
        assert "[mailcraft]" in str(error)


class TestExecutionError:
    """Tests for ExecutionError."""

    def test_execution_error_basic(self) -> None:
        """Test basic execution error."""
        error = ExecutionError("my-plugin", "do_action", "Command failed")
        assert error.plugin_name == "my-plugin"
        assert error.capability == "do_action"
        assert error.reason == "Command failed"
        assert "do_action" in str(error)
        assert "failed" in str(error).lower()

    def test_execution_error_with_exit_code(self) -> None:
        """Test execution error with exit code."""
        error = ExecutionError(
            "cli-plugin",
            "run_command",
            "Non-zero exit",
            exit_code=1,
        )
        assert error.exit_code == 1

    def test_execution_error_with_output(self) -> None:
        """Test execution error with stdout/stderr."""
        error = ExecutionError(
            "cli-plugin",
            "run_command",
            "Failed",
            stdout="Some output",
            stderr="Error output",
        )
        assert error.stdout == "Some output"
        assert error.stderr == "Error output"


class TestPermissionError:
    """Tests for PermissionError."""

    def test_permission_error_basic(self) -> None:
        """Test basic permission error."""
        error = PermissionError(
            "my-plugin",
            action="write_file",
            required_permission="filesystem:write",
        )
        assert error.action == "write_file"
        assert error.required_permission == "filesystem:write"
        assert "Permission denied" in str(error)
        assert "write_file" in str(error)

    def test_permission_error_with_target(self) -> None:
        """Test permission error with target."""
        error = PermissionError(
            "my-plugin",
            action="delete",
            required_permission="filesystem:write",
            target="/etc/passwd",
        )
        assert error.target == "/etc/passwd"
        assert "/etc/passwd" in str(error)


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_configuration_error(self) -> None:
        """Test configuration error."""
        error = ConfigurationError(
            "my-plugin",
            field="api_key",
            reason="Must not be empty",
        )
        assert error.field == "api_key"
        assert error.reason == "Must not be empty"
        assert "api_key" in str(error)
        assert "Must not be empty" in str(error)


class TestPluginTimeoutError:
    """Tests for PluginTimeoutError."""

    def test_timeout_error(self) -> None:
        """Test timeout error."""
        error = PluginTimeoutError("slow-plugin", "long_task", 30)
        assert error.capability == "long_task"
        assert error.timeout_seconds == 30
        assert "timed out" in str(error)
        assert "30" in str(error)


class TestPluginValidationError:
    """Tests for PluginValidationError."""

    def test_validation_error_input(self) -> None:
        """Test input validation error."""
        validation_errors = [{"field": "email", "error": "Invalid format"}]
        error = PluginValidationError(
            "my-plugin",
            "send_email",
            validation_errors,
            stage="input",
        )
        assert error.capability == "send_email"
        assert error.validation_errors == validation_errors
        assert error.stage == "input"
        assert "Validation failed" in str(error)

    def test_validation_error_output(self) -> None:
        """Test output validation error."""
        error = PluginValidationError(
            "my-plugin",
            "get_data",
            [{"error": "Missing field"}],
            stage="output",
        )
        assert error.stage == "output"
        assert "output" in str(error)


class TestExceptionHierarchy:
    """Tests for exception inheritance."""

    def test_all_inherit_from_plugin_error(self) -> None:
        """Test all exceptions inherit from PluginError."""
        exceptions = [
            PluginNotFoundError("test"),
            PluginLoadError("test", "reason"),
            ManifestError("test", "error"),
            ManifestNotFoundError("test", "/path"),
            DependencyError("test"),
            CapabilityNotFoundError("test"),
            ExecutionError("test", "cap", "reason"),
            PermissionError("test", "action", "perm"),
            ConfigurationError("test", "field", "reason"),
            PluginTimeoutError("test", "cap", 10),
            PluginValidationError("test", "cap", []),
        ]

        for exc in exceptions:
            assert isinstance(exc, PluginError)
            assert isinstance(exc, Exception)

    def test_manifest_not_found_inherits_from_manifest_error(self) -> None:
        """Test ManifestNotFoundError inherits from ManifestError."""
        error = ManifestNotFoundError("test", "/path")
        assert isinstance(error, ManifestError)
        assert isinstance(error, PluginError)
