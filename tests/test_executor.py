"""Tests for the plugin executor module."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from mother.plugins.base import PluginBase, PluginResult
from mother.plugins.exceptions import ExecutionError, PluginLoadError
from mother.plugins.executor import (
    BuiltinExecutor,
    CLIExecutor,
    ExecutorBase,
    PythonExecutor,
    _FlexiblePluginWrapper,
    create_executor,
)
from mother.plugins.manifest import (
    CapabilitySpec,
    CLIExecutionSpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
)


@pytest.fixture
def sample_manifest():
    """Create a sample plugin manifest for testing."""
    return PluginManifest(
        plugin=PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
        ),
        capabilities=[
            CapabilitySpec(
                name="test_action",
                description="A test action",
                parameters=[
                    ParameterSpec(
                        name="input",
                        type=ParameterType.STRING,
                        description="Input value",
                        required=True,
                    )
                ],
            ),
            CapabilitySpec(
                name="slow_action",
                description="A slow action",
                parameters=[],
                timeout=1,
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec.model_validate({"module": "test_module", "class": "TestPlugin"}),
        ),
    )


@pytest.fixture
def cli_manifest():
    """Create a CLI plugin manifest for testing."""
    return PluginManifest(
        plugin=PluginMetadata(
            name="cli-plugin",
            version="1.0.0",
            description="CLI test plugin",
            author="Test Author",
        ),
        capabilities=[
            CapabilitySpec(
                name="echo",
                description="Echo input",
                parameters=[
                    ParameterSpec(
                        name="message",
                        type=ParameterType.STRING,
                        description="Message to echo",
                        required=True,
                        positional=True,
                    )
                ],
            ),
            CapabilitySpec(
                name="verbose",
                description="Verbose output",
                parameters=[
                    ParameterSpec(
                        name="level",
                        type=ParameterType.INTEGER,
                        description="Verbosity level",
                        flag="-v",
                    ),
                    ParameterSpec(
                        name="debug",
                        type=ParameterType.BOOLEAN,
                        description="Enable debug",
                        flag="--debug",
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.CLI,
            cli=CLIExecutionSpec(
                binary="echo",
                env={"TEST_VAR": "value"},
            ),
        ),
    )


class TestFlexiblePluginWrapper:
    """Tests for _FlexiblePluginWrapper class."""

    @pytest.fixture
    def mock_instance(self):
        """Create a mock plugin instance."""
        instance = MagicMock()
        instance.execute = MagicMock(return_value={"result": "test"})
        return instance

    @pytest.fixture
    def manifest(self, sample_manifest):
        return sample_manifest

    def test_init(self, mock_instance, manifest):
        """Test wrapper initialization."""
        wrapper = _FlexiblePluginWrapper(mock_instance, manifest)
        assert wrapper._instance == mock_instance

    @pytest.mark.asyncio
    async def test_initialize_with_sync_init(self, mock_instance, manifest):
        """Test initialize calls sync initialize on instance."""
        mock_instance.initialize = MagicMock()
        wrapper = _FlexiblePluginWrapper(mock_instance, manifest)
        await wrapper.initialize()
        mock_instance.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_with_async_init(self, mock_instance, manifest):
        """Test initialize calls async initialize on instance."""
        mock_instance.initialize = AsyncMock()
        wrapper = _FlexiblePluginWrapper(mock_instance, manifest)
        await wrapper.initialize()
        mock_instance.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_without_init(self, mock_instance, manifest):
        """Test initialize when instance has no initialize method."""
        del mock_instance.initialize
        wrapper = _FlexiblePluginWrapper(mock_instance, manifest)
        # Should not raise
        await wrapper.initialize()

    @pytest.mark.asyncio
    async def test_execute_returns_dict(self, mock_instance, manifest):
        """Test execute with dict return value."""
        mock_instance.execute = MagicMock(return_value={"data": "test"})
        wrapper = _FlexiblePluginWrapper(mock_instance, manifest)
        result = await wrapper.execute("test", {})
        assert result.success is True
        assert result.data == {"data": "test"}

    @pytest.mark.asyncio
    async def test_execute_returns_plugin_result(self, mock_instance, manifest):
        """Test execute with PluginResult return value."""
        expected = PluginResult.success_result(data={"test": True})
        mock_instance.execute = MagicMock(return_value=expected)
        wrapper = _FlexiblePluginWrapper(mock_instance, manifest)
        result = await wrapper.execute("test", {})
        assert result == expected

    @pytest.mark.asyncio
    async def test_execute_returns_other(self, mock_instance, manifest):
        """Test execute with non-dict, non-PluginResult return."""
        mock_instance.execute = MagicMock(return_value="string result")
        wrapper = _FlexiblePluginWrapper(mock_instance, manifest)
        result = await wrapper.execute("test", {})
        assert result.success is True
        assert result.data == {"result": "string result"}

    @pytest.mark.asyncio
    async def test_execute_async(self, mock_instance, manifest):
        """Test execute with async execute method."""
        mock_instance.execute = AsyncMock(return_value={"async": True})
        wrapper = _FlexiblePluginWrapper(mock_instance, manifest)
        result = await wrapper.execute("test", {})
        assert result.data == {"async": True}

    @pytest.mark.asyncio
    async def test_shutdown_with_sync_shutdown(self, mock_instance, manifest):
        """Test shutdown calls sync shutdown on instance."""
        mock_instance.shutdown = MagicMock()
        wrapper = _FlexiblePluginWrapper(mock_instance, manifest)
        await wrapper.shutdown()
        mock_instance.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_async_shutdown(self, mock_instance, manifest):
        """Test shutdown calls async shutdown on instance."""
        mock_instance.shutdown = AsyncMock()
        wrapper = _FlexiblePluginWrapper(mock_instance, manifest)
        await wrapper.shutdown()
        mock_instance.shutdown.assert_called_once()


class TestExecutorBase:
    """Tests for ExecutorBase abstract class."""

    def test_plugin_name(self, sample_manifest):
        """Test plugin_name property."""

        class ConcreteExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, capability, params):
                pass

        executor = ConcreteExecutor(sample_manifest)
        assert executor.plugin_name == "test-plugin"

    def test_config_defaults_to_empty(self, sample_manifest):
        """Test config defaults to empty dict."""

        class ConcreteExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, capability, params):
                pass

        executor = ConcreteExecutor(sample_manifest)
        assert executor.config == {}

    def test_config_with_values(self, sample_manifest):
        """Test config with provided values."""

        class ConcreteExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, capability, params):
                pass

        executor = ConcreteExecutor(sample_manifest, {"key": "value"})
        assert executor.config == {"key": "value"}

    def test_get_timeout_from_capability(self, sample_manifest):
        """Test get_timeout returns capability-specific timeout."""

        class ConcreteExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, capability, params):
                pass

        executor = ConcreteExecutor(sample_manifest)
        assert executor.get_timeout("slow_action") == 1

    def test_get_timeout_from_config(self, sample_manifest):
        """Test get_timeout returns config timeout when capability has none."""

        class ConcreteExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, capability, params):
                pass

        executor = ConcreteExecutor(sample_manifest, {"timeout": 60})
        assert executor.get_timeout("test_action") == 60

    def test_get_timeout_default(self, sample_manifest):
        """Test get_timeout returns default 300."""

        class ConcreteExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, capability, params):
                pass

        executor = ConcreteExecutor(sample_manifest)
        assert executor.get_timeout("test_action") == 300

    @pytest.mark.asyncio
    async def test_shutdown_calls_plugin_shutdown(self, sample_manifest):
        """Test shutdown calls plugin's shutdown method."""

        class ConcreteExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, capability, params):
                pass

        executor = ConcreteExecutor(sample_manifest)
        mock_plugin = MagicMock()
        mock_plugin.shutdown = AsyncMock()
        executor._plugin = mock_plugin

        await executor.shutdown()
        mock_plugin.shutdown.assert_called_once()


class TestBuiltinExecutor:
    """Tests for BuiltinExecutor class."""

    @pytest.fixture(autouse=True)
    def mock_policy(self, monkeypatch):
        """Mock policy check to allow all actions in tests."""
        monkeypatch.setattr(BuiltinExecutor, "check_policy", lambda self, cap, params, ctx=None: None)

    @pytest.fixture
    def mock_plugin(self, sample_manifest):
        """Create a mock plugin instance."""
        plugin = MagicMock(spec=PluginBase)
        plugin.initialize = AsyncMock()
        plugin.execute = AsyncMock(return_value=PluginResult.success_result(data={"test": True}))
        plugin.shutdown = AsyncMock()
        return plugin

    def test_init(self, mock_plugin, sample_manifest):
        """Test initialization sets plugin instance."""
        executor = BuiltinExecutor(mock_plugin, sample_manifest)
        assert executor._plugin == mock_plugin

    @pytest.mark.asyncio
    async def test_initialize(self, mock_plugin, sample_manifest):
        """Test initialize calls plugin's initialize."""
        executor = BuiltinExecutor(mock_plugin, sample_manifest)
        await executor.initialize()
        mock_plugin.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_plugin, sample_manifest):
        """Test successful execution."""
        executor = BuiltinExecutor(mock_plugin, sample_manifest)
        result = await executor.execute("test_action", {"input": "test"})
        assert result.success is True
        mock_plugin.execute.assert_called_once_with("test_action", {"input": "test"})

    @pytest.mark.asyncio
    async def test_execute_sets_execution_time(self, mock_plugin, sample_manifest):
        """Test execution time is set."""
        executor = BuiltinExecutor(mock_plugin, sample_manifest)
        result = await executor.execute("test_action", {})
        assert result.execution_time is not None
        assert result.execution_time >= 0

    @pytest.mark.asyncio
    async def test_execute_not_initialized(self, sample_manifest):
        """Test execute when plugin not initialized."""
        executor = BuiltinExecutor.__new__(BuiltinExecutor)
        executor.manifest = sample_manifest
        executor.config = {}
        executor._plugin = None

        result = await executor.execute("test", {})
        assert result.success is False
        assert result.error_code == "NOT_INITIALIZED"

    @pytest.mark.asyncio
    async def test_execute_timeout(self, mock_plugin, sample_manifest):
        """Test execution timeout."""

        async def slow_execute(*args):
            await asyncio.sleep(10)
            return PluginResult.success_result()

        mock_plugin.execute = slow_execute
        executor = BuiltinExecutor(mock_plugin, sample_manifest)

        result = await executor.execute("slow_action", {})
        assert result.success is False
        assert result.error_message is not None
        assert "timed out" in result.error_message.lower() or "timeout" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_exception(self, mock_plugin, sample_manifest):
        """Test exception handling during execution."""
        mock_plugin.execute = AsyncMock(side_effect=ValueError("Test error"))
        executor = BuiltinExecutor(mock_plugin, sample_manifest)

        # Provide valid params so schema validation passes
        result = await executor.execute("test_action", {"input": "test"})
        assert result.success is False
        assert result.error_code == "EXECUTION_ERROR"


class TestCLIExecutor:
    """Tests for CLIExecutor class."""

    @pytest.fixture(autouse=True)
    def mock_policy(self, monkeypatch):
        """Mock policy check to allow all actions in tests."""
        monkeypatch.setattr(CLIExecutor, "check_policy", lambda self, cap, params, ctx=None: None)

    @pytest.mark.asyncio
    async def test_initialize_finds_binary_in_path(self, cli_manifest):
        """Test initialize finds binary in PATH."""
        executor = CLIExecutor(
            cli_manifest,
            cli_manifest.execution.cli,
        )
        await executor.initialize()
        assert executor._binary_path is not None
        assert "echo" in executor._binary_path

    @pytest.mark.asyncio
    async def test_initialize_binary_not_found(self):
        """Test initialize raises error when binary not found."""
        manifest = PluginManifest(
            plugin=PluginMetadata(name="missing", version="1.0.0", description="Missing", author="Test"),
            capabilities=[CapabilitySpec(name="test", description="Test capability", parameters=[])],
            execution=ExecutionSpec(
                type=ExecutionType.CLI,
                cli=CLIExecutionSpec(binary="nonexistent_binary_xyz"),
            ),
        )
        executor = CLIExecutor(manifest, manifest.execution.cli)

        with pytest.raises(PluginLoadError):
            await executor.initialize()

    @pytest.mark.asyncio
    async def test_execute_success(self, cli_manifest):
        """Test successful CLI execution."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)
        await executor.initialize()

        result = await executor.execute("echo", {"message": "hello"})
        assert result.success is True
        assert "hello" in result.raw_output

    @pytest.mark.asyncio
    async def test_execute_not_initialized(self, cli_manifest):
        """Test execute raises error when not initialized."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)

        with pytest.raises(ExecutionError):
            await executor.execute("echo", {"message": "test"})

    @pytest.mark.asyncio
    async def test_execute_unknown_capability(self, cli_manifest):
        """Test execute with unknown capability."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)
        await executor.initialize()

        with pytest.raises(ExecutionError):
            await executor.execute("unknown", {})

    def test_build_command_positional(self, cli_manifest):
        """Test command building with positional arguments."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)
        executor._binary_path = "/bin/echo"

        cap = cli_manifest.get_capability("echo")
        cmd = executor._build_command("echo", cap, {"message": "hello"})

        assert cmd[0] == "/bin/echo"
        assert "echo" in cmd
        assert "hello" in cmd

    def test_build_command_flags(self, cli_manifest):
        """Test command building with flags."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)
        executor._binary_path = "/bin/test"

        cap = cli_manifest.get_capability("verbose")
        cmd = executor._build_command("verbose", cap, {"level": 3, "debug": True})

        assert "-v" in cmd
        assert "3" in cmd
        assert "--debug" in cmd

    def test_build_command_boolean_false(self, cli_manifest):
        """Test boolean flag when False."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)
        executor._binary_path = "/bin/test"

        cap = cli_manifest.get_capability("verbose")
        cmd = executor._build_command("verbose", cap, {"debug": False})

        assert "--debug" not in cmd

    def test_build_environment(self, cli_manifest):
        """Test environment building."""
        executor = CLIExecutor(
            cli_manifest,
            cli_manifest.execution.cli,
            config={"API_KEY": "secret123"},
        )

        env = executor._build_environment()
        assert env["TEST_VAR"] == "value"
        assert "MOTHER_PLUGIN_API_KEY" in env

    def test_build_environment_variable_substitution(self):
        """Test environment variable substitution."""
        manifest = PluginManifest(
            plugin=PluginMetadata(name="env-test", version="1.0.0", description="Test", author="Test"),
            capabilities=[CapabilitySpec(name="test", description="Test capability", parameters=[])],
            execution=ExecutionSpec(
                type=ExecutionType.CLI,
                cli=CLIExecutionSpec(
                    binary="echo",
                    env={
                        "FROM_CONFIG": "${secrets.api_key}",
                        "FROM_ENV": "${env.HOME}",
                    },
                ),
            ),
        )
        executor = CLIExecutor(manifest, manifest.execution.cli, config={"API_KEY": "test_key"})

        env = executor._build_environment()
        assert env["FROM_CONFIG"] == "test_key"
        assert env["FROM_ENV"] == os.environ.get("HOME", "")

    def test_parse_output_json(self, cli_manifest):
        """Test JSON output parsing."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)

        result = executor._parse_output('{"key": "value"}', "test")
        assert result == {"key": "value"}

    def test_parse_output_json_array(self, cli_manifest):
        """Test JSON array output parsing."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)

        result = executor._parse_output("[1, 2, 3]", "test")
        assert result == [1, 2, 3]

    def test_parse_output_text(self, cli_manifest):
        """Test plain text output parsing."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)

        result = executor._parse_output("plain text", "test")
        assert result == {"output": "plain text"}

    def test_parse_output_empty(self, cli_manifest):
        """Test empty output parsing."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)

        result = executor._parse_output("", "test")
        assert result is None


class TestPythonExecutor:
    """Tests for PythonExecutor class."""

    @pytest.fixture(autouse=True)
    def mock_policy(self, monkeypatch):
        """Mock policy check to allow all actions in tests."""
        monkeypatch.setattr(PythonExecutor, "check_policy", lambda self, cap, params, ctx=None: None)

    @pytest.mark.asyncio
    async def test_initialize_plugin_base_subclass(self, sample_manifest, tmp_path):
        """Test initialization with PluginBase subclass."""
        # Create a test module
        module_code = """
from mother.plugins.base import PluginBase, PluginResult

class TestPlugin(PluginBase):
    async def execute(self, capability, params):
        return PluginResult.success_result(data={"test": True})
"""
        module_file = tmp_path / "test_module.py"
        module_file.write_text(module_code)

        spec = PythonExecutionSpec.model_validate({"module": "test_module", "class": "TestPlugin"})
        executor = PythonExecutor(sample_manifest, spec, plugin_dir=tmp_path)

        await executor.initialize()
        assert executor._plugin is not None

        await executor.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_module_not_found(self, sample_manifest):
        """Test initialization with non-existent module."""
        spec = PythonExecutionSpec.model_validate({"module": "nonexistent_module_xyz", "class": "TestPlugin"})
        executor = PythonExecutor(sample_manifest, spec)

        with pytest.raises(PluginLoadError) as exc_info:
            await executor.initialize()
        assert "Failed to import" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_initialize_class_not_found(self, sample_manifest, tmp_path):
        """Test initialization with non-existent class."""
        module_code = "class OtherClass: pass"
        module_file = tmp_path / "test_module2.py"
        module_file.write_text(module_code)

        spec = PythonExecutionSpec.model_validate({"module": "test_module2", "class": "MissingClass"})
        executor = PythonExecutor(sample_manifest, spec, plugin_dir=tmp_path)

        with pytest.raises(PluginLoadError) as exc_info:
            await executor.initialize()
        assert "not found in module" in str(exc_info.value)

        # Clean up sys.path
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))

    @pytest.mark.asyncio
    async def test_shutdown_removes_from_path(self, sample_manifest, tmp_path):
        """Test shutdown removes plugin dir from sys.path."""
        module_code = """
from mother.plugins.base import PluginBase, PluginResult

class TestPlugin(PluginBase):
    async def execute(self, capability, params):
        return PluginResult.success_result()
"""
        module_file = tmp_path / "test_mod_cleanup.py"
        module_file.write_text(module_code)

        spec = PythonExecutionSpec.model_validate({"module": "test_mod_cleanup", "class": "TestPlugin"})
        executor = PythonExecutor(sample_manifest, spec, plugin_dir=tmp_path)

        await executor.initialize()
        assert str(tmp_path) in sys.path

        await executor.shutdown()
        assert str(tmp_path) not in sys.path


class TestCreateExecutor:
    """Tests for create_executor factory function."""

    def test_create_python_executor(self, sample_manifest):
        """Test creating Python executor."""
        executor = create_executor(sample_manifest)
        assert isinstance(executor, PythonExecutor)

    def test_create_cli_executor(self, cli_manifest):
        """Test creating CLI executor."""
        executor = create_executor(cli_manifest)
        assert isinstance(executor, CLIExecutor)

    # Note: Tests for missing configs removed as PluginManifest validates
    # at construction time, preventing these scenarios from occurring

    def test_create_with_config(self, sample_manifest):
        """Test creating executor with config."""
        config = {"timeout": 60, "api_key": "test"}
        executor = create_executor(sample_manifest, config=config)
        assert executor.config == config

    def test_create_with_plugin_dir(self, sample_manifest, tmp_path):
        """Test creating executor with plugin directory."""
        executor = create_executor(sample_manifest, plugin_dir=tmp_path)
        assert isinstance(executor, PythonExecutor)
        assert executor.plugin_dir == tmp_path

    def test_create_docker_executor_not_implemented(self):
        """Test Docker executor raises not implemented error."""
        from unittest.mock import MagicMock

        # Create a mock manifest that bypasses pydantic validation
        mock_manifest = MagicMock()
        mock_manifest.plugin.name = "docker-plugin"
        mock_manifest.execution.type = ExecutionType.DOCKER

        with pytest.raises(PluginLoadError) as exc_info:
            create_executor(mock_manifest)
        assert "Docker execution not yet implemented" in str(exc_info.value)

    def test_create_http_executor_not_implemented(self):
        """Test HTTP executor raises not implemented error."""
        from unittest.mock import MagicMock

        # Create a mock manifest that bypasses pydantic validation
        mock_manifest = MagicMock()
        mock_manifest.plugin.name = "http-plugin"
        mock_manifest.execution.type = ExecutionType.HTTP

        with pytest.raises(PluginLoadError) as exc_info:
            create_executor(mock_manifest)
        assert "HTTP execution not yet implemented" in str(exc_info.value)


class TestPythonExecutorAdditional:
    """Additional tests for PythonExecutor class."""

    @pytest.fixture(autouse=True)
    def mock_policy(self, monkeypatch):
        """Mock policy check to allow all actions in tests."""
        monkeypatch.setattr(PythonExecutor, "check_policy", lambda self, cap, params, ctx=None: None)

    @pytest.fixture
    def sample_manifest(self):
        """Create a sample plugin manifest."""
        return PluginManifest(
            plugin=PluginMetadata(
                name="test-plugin",
                version="1.0.0",
                description="Test plugin",
                author="Test",
            ),
            capabilities=[
                CapabilitySpec(
                    name="test_action",
                    description="Test action",
                    parameters=[],
                    timeout=1,
                )
            ],
            execution=ExecutionSpec(
                type=ExecutionType.PYTHON,
                python=PythonExecutionSpec.model_validate({"module": "test_module", "class": "TestPlugin"}),
            ),
        )

    @pytest.mark.asyncio
    async def test_initialize_class_without_execute(self, sample_manifest, tmp_path):
        """Test initialization with class that has no execute method."""
        module_code = """
class TestPlugin:
    def __init__(self, config):
        pass
    # No execute method
"""
        module_file = tmp_path / "no_execute_module.py"
        module_file.write_text(module_code)

        spec = PythonExecutionSpec.model_validate({"module": "no_execute_module", "class": "TestPlugin"})
        executor = PythonExecutor(sample_manifest, spec, plugin_dir=tmp_path)

        with pytest.raises(PluginLoadError) as exc_info:
            await executor.initialize()
        assert "must extend PluginBase or have execute() method" in str(exc_info.value)

        # Cleanup
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))

    @pytest.mark.asyncio
    async def test_initialize_flexible_plugin(self, sample_manifest, tmp_path):
        """Test initialization with flexible plugin (has execute but not PluginBase)."""
        module_code = """
class TestPlugin:
    def __init__(self, config):
        self.config = config

    def execute(self, capability, params):
        return {"capability": capability, "params": params}
"""
        module_file = tmp_path / "flexible_module.py"
        module_file.write_text(module_code)

        spec = PythonExecutionSpec.model_validate({"module": "flexible_module", "class": "TestPlugin"})
        executor = PythonExecutor(sample_manifest, spec, plugin_dir=tmp_path)

        await executor.initialize()
        assert executor._plugin is not None

        await executor.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_general_exception(self, sample_manifest, tmp_path):
        """Test initialization handles general exceptions."""
        module_code = """
from mother.plugins.base import PluginBase

class TestPlugin(PluginBase):
    def __init__(self, manifest, config):
        raise RuntimeError("Init failed")

    async def execute(self, capability, params):
        pass
"""
        module_file = tmp_path / "error_module.py"
        module_file.write_text(module_code)

        spec = PythonExecutionSpec.model_validate({"module": "error_module", "class": "TestPlugin"})
        executor = PythonExecutor(sample_manifest, spec, plugin_dir=tmp_path)

        with pytest.raises(PluginLoadError) as exc_info:
            await executor.initialize()
        assert "Failed to initialize plugin" in str(exc_info.value)

        # Cleanup
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))

    @pytest.mark.asyncio
    async def test_execute_not_initialized(self, sample_manifest):
        """Test execute raises error when not initialized."""
        spec = PythonExecutionSpec.model_validate({"module": "test", "class": "Test"})
        executor = PythonExecutor(sample_manifest, spec)

        with pytest.raises(ExecutionError) as exc_info:
            await executor.execute("test", {})
        assert "not initialized" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_timeout(self, sample_manifest, tmp_path):
        """Test execute handles timeout."""
        from mother.plugins.exceptions import PluginTimeoutError

        module_code = """
import asyncio
from mother.plugins.base import PluginBase, PluginResult

class TestPlugin(PluginBase):
    async def execute(self, capability, params):
        await asyncio.sleep(10)
        return PluginResult.success_result()
"""
        module_file = tmp_path / "slow_module.py"
        module_file.write_text(module_code)

        spec = PythonExecutionSpec.model_validate({"module": "slow_module", "class": "TestPlugin"})
        executor = PythonExecutor(sample_manifest, spec, plugin_dir=tmp_path)

        await executor.initialize()

        with pytest.raises(PluginTimeoutError):
            await executor.execute("test_action", {})

        await executor.shutdown()

    @pytest.mark.asyncio
    async def test_execute_exception(self, sample_manifest, tmp_path):
        """Test execute handles exceptions."""
        module_code = """
from mother.plugins.base import PluginBase, PluginResult

class TestPlugin(PluginBase):
    async def execute(self, capability, params):
        raise ValueError("Execution failed")
"""
        module_file = tmp_path / "error_exec_module.py"
        module_file.write_text(module_code)

        spec = PythonExecutionSpec.model_validate({"module": "error_exec_module", "class": "TestPlugin"})
        executor = PythonExecutor(sample_manifest, spec, plugin_dir=tmp_path)

        await executor.initialize()

        with pytest.raises(ExecutionError):
            await executor.execute("test_action", {})

        await executor.shutdown()


class TestCLIExecutorAdditional:
    """Additional tests for CLIExecutor class."""

    @pytest.fixture(autouse=True)
    def mock_policy(self, monkeypatch):
        """Mock policy check to allow all actions in tests."""
        monkeypatch.setattr(CLIExecutor, "check_policy", lambda self, cap, params, ctx=None: None)

    @pytest.fixture
    def cli_manifest(self):
        """Create a CLI manifest for testing."""
        return PluginManifest(
            plugin=PluginMetadata(
                name="cli-test",
                version="1.0.0",
                description="CLI test",
                author="Test",
            ),
            capabilities=[
                CapabilitySpec(
                    name="test",
                    description="Test command",
                    parameters=[
                        ParameterSpec(
                            name="items",
                            type=ParameterType.ARRAY,
                            description="List of items",
                            positional=True,
                        ),
                        ParameterSpec(
                            name="values",
                            type=ParameterType.ARRAY,
                            description="List of values",
                            flag="--value",
                        ),
                        ParameterSpec(
                            name="count",
                            type=ParameterType.INTEGER,
                            description="Count",
                        ),
                        ParameterSpec(
                            name="enabled",
                            type=ParameterType.BOOLEAN,
                            description="Enable flag",
                        ),
                    ],
                    timeout=1,
                )
            ],
            execution=ExecutionSpec(
                type=ExecutionType.CLI,
                cli=CLIExecutionSpec(binary="echo"),
            ),
        )

    @pytest.mark.asyncio
    async def test_initialize_absolute_path_not_executable(self, tmp_path):
        """Test initialize fails for non-executable absolute path."""
        binary_path = tmp_path / "not_executable"
        binary_path.touch()  # Create file but don't make it executable

        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="abs-test",
                version="1.0.0",
                description="Test",
                author="Test",
            ),
            capabilities=[CapabilitySpec(name="test", description="Test", parameters=[])],
            execution=ExecutionSpec(
                type=ExecutionType.CLI,
                cli=CLIExecutionSpec(binary=str(binary_path)),
            ),
        )
        executor = CLIExecutor(manifest, manifest.execution.cli)

        with pytest.raises(PluginLoadError) as exc_info:
            await executor.initialize()
        assert "not found or not executable" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_initialize_finds_in_common_paths(self, tmp_path, monkeypatch):
        """Test initialize finds binary in common paths."""
        from pathlib import Path as PathLib

        # Create a mock binary in .local/bin
        local_bin = tmp_path / ".local" / "bin"
        local_bin.mkdir(parents=True)
        binary = local_bin / "test_binary"
        binary.touch()
        binary.chmod(0o755)

        monkeypatch.setattr(PathLib, "home", lambda: tmp_path)

        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="common-path-test",
                version="1.0.0",
                description="Test",
                author="Test",
            ),
            capabilities=[CapabilitySpec(name="test", description="Test", parameters=[])],
            execution=ExecutionSpec(
                type=ExecutionType.CLI,
                cli=CLIExecutionSpec(binary="test_binary"),
            ),
        )
        executor = CLIExecutor(manifest, manifest.execution.cli)

        await executor.initialize()
        assert executor._binary_path == str(binary)

    @pytest.mark.asyncio
    async def test_execute_timeout(self, tmp_path):
        """Test CLI execute handles timeout."""
        # Create a simple script that sleeps
        script = tmp_path / "slow_script.sh"
        script.write_text("#!/bin/bash\nsleep 10\n")
        script.chmod(0o755)

        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="timeout-test",
                version="1.0.0",
                description="Test",
                author="Test",
            ),
            capabilities=[
                CapabilitySpec(
                    name="run",
                    description="Run slow script",
                    parameters=[],
                    timeout=1,
                )
            ],
            execution=ExecutionSpec(
                type=ExecutionType.CLI,
                cli=CLIExecutionSpec(binary=str(script)),
            ),
        )
        executor = CLIExecutor(manifest, manifest.execution.cli)
        await executor.initialize()

        result = await executor.execute("run", {})
        assert result.success is False
        assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_non_zero_exit(self):
        """Test CLI execute with non-zero exit code."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="exit-test",
                version="1.0.0",
                description="Test",
                author="Test",
            ),
            capabilities=[
                CapabilitySpec(
                    name="false",
                    description="Always fails",
                    parameters=[],
                )
            ],
            execution=ExecutionSpec(
                type=ExecutionType.CLI,
                cli=CLIExecutionSpec(binary="false"),
            ),
        )
        executor = CLIExecutor(manifest, manifest.execution.cli)
        await executor.initialize()

        result = await executor.execute("false", {})
        assert result.success is False
        assert result.error_code.startswith("EXIT_")

    def test_build_command_list_positional(self, cli_manifest):
        """Test command building with list positional arguments."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)
        executor._binary_path = "/bin/test"

        cap = cli_manifest.get_capability("test")
        cmd = executor._build_command("test", cap, {"items": ["a", "b", "c"]})

        assert "a" in cmd
        assert "b" in cmd
        assert "c" in cmd

    def test_build_command_list_flag(self, cli_manifest):
        """Test command building with list flag arguments."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)
        executor._binary_path = "/bin/test"

        cap = cli_manifest.get_capability("test")
        cmd = executor._build_command("test", cap, {"values": ["x", "y"]})

        # Should have --value x --value y
        value_indices = [i for i, c in enumerate(cmd) if c == "--value"]
        assert len(value_indices) == 2

    def test_build_command_default_flag_format(self, cli_manifest):
        """Test command building with default --param-name format."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)
        executor._binary_path = "/bin/test"

        cap = cli_manifest.get_capability("test")
        cmd = executor._build_command("test", cap, {"count": 5})

        assert "--count" in cmd
        assert "5" in cmd

    def test_build_command_default_boolean_flag(self, cli_manifest):
        """Test command building with default boolean flag."""
        executor = CLIExecutor(cli_manifest, cli_manifest.execution.cli)
        executor._binary_path = "/bin/test"

        cap = cli_manifest.get_capability("test")
        cmd = executor._build_command("test", cap, {"enabled": True})

        assert "--enabled" in cmd

    def test_build_command_default_list_flag(self, cli_manifest):
        """Test command building with default list flag format."""
        # Create a manifest with a list param without explicit flag
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="list-test",
                version="1.0.0",
                description="Test",
                author="Test",
            ),
            capabilities=[
                CapabilitySpec(
                    name="test",
                    description="Test",
                    parameters=[
                        ParameterSpec(
                            name="tags",
                            type=ParameterType.ARRAY,
                            description="Tags",
                        )
                    ],
                )
            ],
            execution=ExecutionSpec(
                type=ExecutionType.CLI,
                cli=CLIExecutionSpec(binary="echo"),
            ),
        )
        executor = CLIExecutor(manifest, manifest.execution.cli)
        executor._binary_path = "/bin/test"

        cap = manifest.get_capability("test")
        cmd = executor._build_command("test", cap, {"tags": ["tag1", "tag2"]})

        # Should have --tags tag1 --tags tag2
        assert cmd.count("--tags") == 2

    def test_build_environment_direct_env_ref(self):
        """Test environment with direct env variable reference."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="env-test",
                version="1.0.0",
                description="Test",
                author="Test",
            ),
            capabilities=[CapabilitySpec(name="test", description="Test", parameters=[])],
            execution=ExecutionSpec(
                type=ExecutionType.CLI,
                cli=CLIExecutionSpec(
                    binary="echo",
                    env={"MY_VAR": "${PATH}"},
                ),
            ),
        )
        executor = CLIExecutor(manifest, manifest.execution.cli)

        env = executor._build_environment()
        assert env.get("MY_VAR") == os.environ.get("PATH")

    def test_parse_output_invalid_json(self):
        """Test parsing invalid JSON output."""
        manifest = PluginManifest(
            plugin=PluginMetadata(
                name="parse-test",
                version="1.0.0",
                description="Test",
                author="Test",
            ),
            capabilities=[CapabilitySpec(name="test", description="Test", parameters=[])],
            execution=ExecutionSpec(
                type=ExecutionType.CLI,
                cli=CLIExecutionSpec(binary="echo"),
            ),
        )
        executor = CLIExecutor(manifest, manifest.execution.cli)

        # Starts with { but is not valid JSON
        result = executor._parse_output("{invalid json", "test")
        assert result == {"output": "{invalid json"}
