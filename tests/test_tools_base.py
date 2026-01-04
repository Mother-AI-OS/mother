"""Tests for the tools base module."""

from unittest.mock import patch

import pytest

from mother.tools.base import ToolParameter, ToolResult, ToolWrapper


class TestToolParameter:
    """Tests for ToolParameter dataclass."""

    def test_basic_creation(self):
        """Test creating a basic parameter."""
        param = ToolParameter(
            name="path",
            type="string",
        )

        assert param.name == "path"
        assert param.type == "string"
        assert param.description == ""
        assert param.required is False
        assert param.flag is None
        assert param.positional is False
        assert param.default is None
        assert param.choices == []

    def test_full_creation(self):
        """Test creating a parameter with all fields."""
        param = ToolParameter(
            name="format",
            type="choice",
            description="Output format",
            required=True,
            flag="--format",
            positional=False,
            default="json",
            choices=["json", "xml", "csv"],
        )

        assert param.name == "format"
        assert param.type == "choice"
        assert param.description == "Output format"
        assert param.required is True
        assert param.flag == "--format"
        assert param.positional is False
        assert param.default == "json"
        assert param.choices == ["json", "xml", "csv"]

    def test_positional_parameter(self):
        """Test positional parameter."""
        param = ToolParameter(
            name="file",
            type="string",
            positional=True,
        )

        assert param.positional is True


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = ToolResult(
            success=True,
            exit_code=0,
            stdout="Hello World",
            stderr="",
        )

        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "Hello World"
        assert result.stderr == ""
        assert result.parsed_data is None
        assert result.error_message is None
        assert result.execution_time == 0.0
        assert result.command == []

    def test_failure_result(self):
        """Test failure result."""
        result = ToolResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="Error: File not found",
            error_message="File not found",
        )

        assert result.success is False
        assert result.exit_code == 1
        assert result.error_message == "File not found"

    def test_result_with_parsed_data(self):
        """Test result with parsed data."""
        result = ToolResult(
            success=True,
            exit_code=0,
            stdout='{"key": "value"}',
            stderr="",
            parsed_data={"key": "value"},
        )

        assert result.parsed_data == {"key": "value"}

    def test_result_with_command(self):
        """Test result with command record."""
        result = ToolResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            command=["ls", "-la", "/tmp"],
            execution_time=0.5,
        )

        assert result.command == ["ls", "-la", "/tmp"]
        assert result.execution_time == 0.5


class ConcreteToolWrapper(ToolWrapper):
    """Concrete implementation for testing."""

    @property
    def name(self) -> str:
        return "testtool"

    def get_commands(self) -> dict[str, dict]:
        return {
            "list": {
                "description": "List items",
                "parameters": [
                    {"name": "path", "type": "string", "description": "Path to list"},
                    {"name": "all", "type": "boolean", "flag": "-a", "description": "Show all"},
                ],
            },
            "search": {
                "description": "Search for items",
                "parameters": [
                    {"name": "query", "type": "string", "required": True, "flag": "-q"},
                    {"name": "limit", "type": "integer", "flag": "-n"},
                ],
            },
            "create.item": {
                "description": "Create an item",
                "parameters": [
                    {"name": "name", "type": "string", "positional": True, "position": 1},
                ],
            },
            "format": {
                "description": "Format output",
                "parameters": [
                    {"name": "type", "type": "choice", "choices": ["json", "xml"], "flag": "-t"},
                ],
            },
            "batch": {
                "description": "Batch operation",
                "parameters": [
                    {"name": "files", "type": "array", "flag": "-f"},
                ],
            },
            "confirm_action": {
                "description": "Action requiring confirmation",
                "confirmation_required": True,
                "parameters": [],
            },
        }

    def parse_output(self, command: str, stdout: str, stderr: str):
        return {"output": stdout}


class TestToolWrapper:
    """Tests for ToolWrapper class."""

    @pytest.fixture
    def wrapper(self):
        """Create test wrapper."""
        return ConcreteToolWrapper(binary="echo")

    def test_init_defaults(self):
        """Test default initialization."""
        wrapper = ConcreteToolWrapper(binary="mytool")

        assert wrapper.binary == "mytool"
        assert wrapper.env_vars == {}
        assert wrapper.cwd is None
        assert wrapper.timeout == 300
        assert wrapper.extra_args == []

    def test_init_custom(self):
        """Test custom initialization."""
        wrapper = ConcreteToolWrapper(
            binary="mytool",
            env_vars={"KEY": "value"},
            cwd="/tmp",
            timeout=60,
            extra_args=["--verbose"],
        )

        assert wrapper.binary == "mytool"
        assert wrapper.env_vars == {"KEY": "value"}
        assert wrapper.cwd == "/tmp"
        assert wrapper.timeout == 60
        assert wrapper.extra_args == ["--verbose"]

    def test_name_property(self, wrapper):
        """Test name property."""
        assert wrapper.name == "testtool"

    def test_description_property(self, wrapper):
        """Test description property."""
        # Uses docstring
        assert "testtool" in wrapper.description.lower() or "implementation" in wrapper.description.lower()


class TestToolWrapperSchemas:
    """Tests for ToolWrapper schema generation."""

    @pytest.fixture
    def wrapper(self):
        """Create test wrapper."""
        return ConcreteToolWrapper(binary="echo")

    def test_get_anthropic_tool_schema_basic(self, wrapper):
        """Test basic schema generation."""
        schema = wrapper.get_anthropic_tool_schema("list")

        assert schema["name"] == "testtool_list"
        assert schema["description"] == "List items"
        assert "input_schema" in schema
        assert schema["input_schema"]["type"] == "object"

    def test_get_anthropic_tool_schema_string(self, wrapper):
        """Test string parameter in schema."""
        schema = wrapper.get_anthropic_tool_schema("list")
        props = schema["input_schema"]["properties"]

        assert "path" in props
        assert props["path"]["type"] == "string"

    def test_get_anthropic_tool_schema_boolean(self, wrapper):
        """Test boolean parameter in schema."""
        schema = wrapper.get_anthropic_tool_schema("list")
        props = schema["input_schema"]["properties"]

        assert "all" in props
        assert props["all"]["type"] == "boolean"

    def test_get_anthropic_tool_schema_integer(self, wrapper):
        """Test integer parameter in schema."""
        schema = wrapper.get_anthropic_tool_schema("search")
        props = schema["input_schema"]["properties"]

        assert "limit" in props
        assert props["limit"]["type"] == "integer"

    def test_get_anthropic_tool_schema_choice(self, wrapper):
        """Test choice parameter in schema."""
        schema = wrapper.get_anthropic_tool_schema("format")
        props = schema["input_schema"]["properties"]

        assert "type" in props
        assert props["type"]["type"] == "string"
        assert props["type"]["enum"] == ["json", "xml"]

    def test_get_anthropic_tool_schema_array(self, wrapper):
        """Test array parameter in schema."""
        schema = wrapper.get_anthropic_tool_schema("batch")
        props = schema["input_schema"]["properties"]

        assert "files" in props
        assert props["files"]["type"] == "array"
        assert props["files"]["items"] == {"type": "string"}

    def test_get_anthropic_tool_schema_required(self, wrapper):
        """Test required parameters in schema."""
        schema = wrapper.get_anthropic_tool_schema("search")

        assert "query" in schema["input_schema"]["required"]

    def test_get_anthropic_tool_schema_unknown_command(self, wrapper):
        """Test unknown command raises error."""
        with pytest.raises(ValueError, match="Unknown command"):
            wrapper.get_anthropic_tool_schema("nonexistent")

    def test_get_anthropic_tool_schema_with_dots(self, wrapper):
        """Test command with dots in name."""
        schema = wrapper.get_anthropic_tool_schema("create.item")

        assert schema["name"] == "testtool_create_item"


class TestToolWrapperBuildCommand:
    """Tests for ToolWrapper build_command method."""

    @pytest.fixture
    def wrapper(self):
        """Create test wrapper."""
        return ConcreteToolWrapper(binary="mytool")

    def test_build_basic_command(self, wrapper):
        """Test building basic command."""
        cmd = wrapper.build_command("list", {"path": "/tmp"})

        assert cmd[0] == "mytool"
        assert "list" in cmd

    def test_build_command_with_flag(self, wrapper):
        """Test building command with flag parameter."""
        cmd = wrapper.build_command("search", {"query": "test"})

        assert "-q" in cmd
        assert "test" in cmd

    def test_build_command_with_boolean_true(self, wrapper):
        """Test building command with boolean flag (true)."""
        cmd = wrapper.build_command("list", {"all": True})

        assert "-a" in cmd

    def test_build_command_with_boolean_false(self, wrapper):
        """Test building command with boolean flag (false)."""
        cmd = wrapper.build_command("list", {"all": False})

        assert "-a" not in cmd

    def test_build_command_with_array(self, wrapper):
        """Test building command with array parameter."""
        cmd = wrapper.build_command("batch", {"files": ["a.txt", "b.txt"]})

        # Each item should be preceded by the flag
        assert cmd.count("-f") == 2
        assert "a.txt" in cmd
        assert "b.txt" in cmd

    def test_build_command_with_positional(self, wrapper):
        """Test building command with positional argument."""
        cmd = wrapper.build_command("create.item", {"name": "myitem"})

        # Positional should be at the end
        assert cmd[-1] == "myitem"

    def test_build_command_with_subcommand(self, wrapper):
        """Test building command with dotted subcommand."""
        cmd = wrapper.build_command("create.item", {"name": "test"})

        # Should split create.item into create and item
        assert "create" in cmd
        assert "item" in cmd

    def test_build_command_with_extra_args(self):
        """Test building command with extra args."""
        wrapper = ConcreteToolWrapper(binary="mytool", extra_args=["--verbose"])
        cmd = wrapper.build_command("list", {})

        assert "--verbose" in cmd

    def test_build_command_missing_required(self, wrapper):
        """Test building command with missing required parameter."""
        with pytest.raises(ValueError, match="Missing required parameter"):
            wrapper.build_command("search", {})

    def test_build_command_unknown(self, wrapper):
        """Test building command for unknown command."""
        with pytest.raises(ValueError, match="Unknown command"):
            wrapper.build_command("nonexistent", {})


class TestToolWrapperExecute:
    """Tests for ToolWrapper execute method."""

    @pytest.fixture
    def wrapper(self):
        """Create test wrapper with echo as binary."""
        return ConcreteToolWrapper(binary="echo")

    def test_execute_success(self, wrapper):
        """Test successful execution."""
        result = wrapper.execute("list", {})

        assert result.success is True
        assert result.exit_code == 0
        # echo will output the command arguments
        assert "list" in result.stdout

    def test_execute_with_env_vars(self):
        """Test execution with environment variables."""
        wrapper = ConcreteToolWrapper(
            binary="echo",
            env_vars={"MY_VAR": "test_value"},
        )

        result = wrapper.execute("list", {})

        assert result.success is True
        # Command should succeed with env vars set

    def test_execute_timeout(self):
        """Test execution timeout."""
        wrapper = ConcreteToolWrapper(binary="sleep", timeout=1)
        wrapper.get_commands = lambda: {"long": {"parameters": []}}

        with patch.object(wrapper, "build_command", return_value=["sleep", "10"]):
            result = wrapper.execute("long", {})

        assert result.success is False
        assert "timed out" in result.error_message.lower()

    def test_execute_binary_not_found(self):
        """Test execution with non-existent binary."""
        wrapper = ConcreteToolWrapper(binary="nonexistent_binary_12345")

        result = wrapper.execute("list", {})

        assert result.success is False
        assert "not found" in result.error_message.lower()

    def test_execute_returns_command(self, wrapper):
        """Test execution returns command."""
        result = wrapper.execute("list", {})

        assert isinstance(result.command, list)
        assert result.command[0] == "echo"

    def test_execute_records_time(self, wrapper):
        """Test execution records execution time."""
        result = wrapper.execute("list", {})

        assert result.execution_time >= 0


class TestToolWrapperExtractError:
    """Tests for ToolWrapper extract_error method."""

    @pytest.fixture
    def wrapper(self):
        """Create test wrapper."""
        return ConcreteToolWrapper(binary="echo")

    def test_extract_error_with_error_prefix(self, wrapper):
        """Test extracting error with Error: prefix."""
        output = "Error: File not found"
        error = wrapper.extract_error(output)

        assert error == "File not found"

    def test_extract_error_with_failed_prefix(self, wrapper):
        """Test extracting error with Failed to prefix."""
        output = "Failed to connect to server"
        error = wrapper.extract_error(output)

        assert error == "connect to server"

    def test_extract_error_lowercase(self, wrapper):
        """Test extracting lowercase error."""
        output = "error: something went wrong"
        error = wrapper.extract_error(output)

        assert error == "something went wrong"

    def test_extract_error_exception(self, wrapper):
        """Test extracting Exception."""
        output = "Exception: Invalid argument"
        error = wrapper.extract_error(output)

        assert error == "Invalid argument"

    def test_extract_error_fallback(self, wrapper):
        """Test fallback to first line."""
        output = "Something unexpected happened"
        error = wrapper.extract_error(output)

        assert "Something unexpected happened" in error

    def test_extract_error_multiline(self, wrapper):
        """Test extracting error from multiline output."""
        output = """Warning: something
Error: The actual error
More output"""
        error = wrapper.extract_error(output)

        assert error == "The actual error"

    def test_extract_error_truncation(self, wrapper):
        """Test error message truncation."""
        long_line = "x" * 500
        output = long_line
        error = wrapper.extract_error(output)

        assert len(error) <= 200


class TestToolWrapperConfirmation:
    """Tests for ToolWrapper confirmation methods."""

    @pytest.fixture
    def wrapper(self):
        """Create test wrapper."""
        return ConcreteToolWrapper(binary="echo")

    def test_confirmation_not_required(self, wrapper):
        """Test command not requiring confirmation."""
        assert wrapper.is_confirmation_required("list") is False

    def test_confirmation_required(self, wrapper):
        """Test command requiring confirmation."""
        assert wrapper.is_confirmation_required("confirm_action") is True

    def test_confirmation_unknown_command(self, wrapper):
        """Test confirmation for unknown command."""
        assert wrapper.is_confirmation_required("nonexistent") is False
