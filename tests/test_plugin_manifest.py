"""Tests for PluginManifest and related classes."""

import tempfile
from pathlib import Path

from mother.plugins.manifest import (
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
    ReturnSpec,
    find_manifest,
    load_manifest,
)


class TestParameterType:
    """Tests for ParameterType enum."""

    def test_all_types_exist(self) -> None:
        """Test all parameter types are defined."""
        assert ParameterType.STRING.value == "string"
        assert ParameterType.INTEGER.value == "integer"
        assert ParameterType.NUMBER.value == "number"
        assert ParameterType.BOOLEAN.value == "boolean"
        assert ParameterType.ARRAY.value == "array"
        assert ParameterType.OBJECT.value == "object"


class TestExecutionType:
    """Tests for ExecutionType enum."""

    def test_all_types_exist(self) -> None:
        """Test all execution types are defined."""
        assert ExecutionType.PYTHON.value == "python"
        assert ExecutionType.CLI.value == "cli"
        assert ExecutionType.DOCKER.value == "docker"
        assert ExecutionType.HTTP.value == "http"


class TestParameterSpec:
    """Tests for ParameterSpec."""

    def test_string_parameter(self) -> None:
        """Test string parameter spec."""
        param = ParameterSpec(name="message", type=ParameterType.STRING, description="The message")
        assert param.name == "message"
        assert param.type == ParameterType.STRING
        assert param.required is False

    def test_required_parameter(self) -> None:
        """Test required parameter."""
        param = ParameterSpec(name="path", type=ParameterType.STRING, required=True)
        assert param.required is True

    def test_parameter_with_default(self) -> None:
        """Test parameter with default value."""
        param = ParameterSpec(name="count", type=ParameterType.INTEGER, default=10)
        assert param.default == 10

    def test_parameter_with_choices(self) -> None:
        """Test parameter with choices."""
        param = ParameterSpec(name="format", type=ParameterType.STRING, choices=["json", "xml", "csv"])
        assert param.choices == ["json", "xml", "csv"]

    def test_array_parameter(self) -> None:
        """Test array parameter."""
        param = ParameterSpec(name="files", type=ParameterType.ARRAY, items_type=ParameterType.STRING)
        assert param.items_type == ParameterType.STRING

    def test_to_json_schema_string(self) -> None:
        """Test JSON schema for string."""
        param = ParameterSpec(name="name", type=ParameterType.STRING, description="User name")
        schema = param.to_json_schema()
        assert schema["type"] == "string"
        assert schema["description"] == "User name"

    def test_to_json_schema_integer(self) -> None:
        """Test JSON schema for integer."""
        param = ParameterSpec(name="age", type=ParameterType.INTEGER, description="Age")
        schema = param.to_json_schema()
        assert schema["type"] == "integer"

    def test_to_json_schema_number(self) -> None:
        """Test JSON schema for number."""
        param = ParameterSpec(name="price", type=ParameterType.NUMBER, description="Price")
        schema = param.to_json_schema()
        assert schema["type"] == "number"

    def test_to_json_schema_boolean(self) -> None:
        """Test JSON schema for boolean."""
        param = ParameterSpec(name="enabled", type=ParameterType.BOOLEAN, description="Enabled")
        schema = param.to_json_schema()
        assert schema["type"] == "boolean"

    def test_to_json_schema_with_choices(self) -> None:
        """Test JSON schema with enum."""
        param = ParameterSpec(name="color", type=ParameterType.STRING, choices=["red", "green"])
        schema = param.to_json_schema()
        assert schema["enum"] == ["red", "green"]

    def test_to_json_schema_array(self) -> None:
        """Test JSON schema for array."""
        param = ParameterSpec(name="tags", type=ParameterType.ARRAY, items_type=ParameterType.STRING)
        schema = param.to_json_schema()
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "string"

    def test_to_json_schema_object(self) -> None:
        """Test JSON schema for object."""
        param = ParameterSpec(
            name="config",
            type=ParameterType.OBJECT,
            properties={"key": {"type": "string"}},
        )
        schema = param.to_json_schema()
        assert schema["type"] == "object"
        assert "properties" in schema

    def test_to_json_schema_with_default(self) -> None:
        """Test JSON schema with default."""
        param = ParameterSpec(name="limit", type=ParameterType.INTEGER, default=100)
        schema = param.to_json_schema()
        assert schema["default"] == 100

    def test_cli_flag_parameter(self) -> None:
        """Test CLI flag parameter."""
        param = ParameterSpec(name="output", type=ParameterType.STRING, flag="--output")
        assert param.flag == "--output"

    def test_positional_parameter(self) -> None:
        """Test positional parameter."""
        param = ParameterSpec(name="file", type=ParameterType.STRING, positional=True)
        assert param.positional is True


class TestReturnSpec:
    """Tests for ReturnSpec."""

    def test_simple_return(self) -> None:
        """Test simple return spec."""
        ret = ReturnSpec(type=ParameterType.STRING, description="Result string")
        assert ret.type == ParameterType.STRING

    def test_object_return(self) -> None:
        """Test object return spec."""
        ret = ReturnSpec(
            type=ParameterType.OBJECT,
            description="Result object",
            properties={"count": {"type": "integer"}},
        )
        assert ret.properties is not None


class TestCapabilitySpec:
    """Tests for CapabilitySpec."""

    def test_minimal_capability(self) -> None:
        """Test minimal capability."""
        cap = CapabilitySpec(name="ping", description="Ping the service")
        assert cap.name == "ping"
        assert cap.parameters == []

    def test_capability_with_parameters(self) -> None:
        """Test capability with parameters."""
        cap = CapabilitySpec(
            name="search",
            description="Search items",
            parameters=[
                ParameterSpec(name="query", type=ParameterType.STRING, required=True),
                ParameterSpec(name="limit", type=ParameterType.INTEGER, default=10),
            ],
        )
        assert len(cap.parameters) == 2

    def test_capability_confirmation_required(self) -> None:
        """Test capability requiring confirmation."""
        cap = CapabilitySpec(name="delete_all", description="Delete everything", confirmation_required=True)
        assert cap.confirmation_required is True

    def test_capability_timeout(self) -> None:
        """Test capability with timeout."""
        cap = CapabilitySpec(name="long_task", description="Long running task", timeout=300)
        assert cap.timeout == 300

    def test_to_anthropic_schema(self) -> None:
        """Test Anthropic schema generation."""
        cap = CapabilitySpec(
            name="search",
            description="Search for items",
            parameters=[
                ParameterSpec(name="query", type=ParameterType.STRING, required=True, description="Search query"),
            ],
        )
        schema = cap.to_anthropic_schema("my-plugin")

        assert schema["name"] == "my-plugin_search"
        assert schema["description"] == "Search for items"
        assert "input_schema" in schema
        assert schema["input_schema"]["type"] == "object"
        assert "query" in schema["input_schema"]["properties"]
        assert "query" in schema["input_schema"]["required"]

    def test_to_anthropic_schema_no_required(self) -> None:
        """Test Anthropic schema with no required params."""
        cap = CapabilitySpec(
            name="list",
            description="List items",
            parameters=[
                ParameterSpec(name="limit", type=ParameterType.INTEGER, required=False),
            ],
        )
        schema = cap.to_anthropic_schema("plugin")

        # When there are no required params, the 'required' key is not present
        assert "required" not in schema["input_schema"]


class TestPluginMetadata:
    """Tests for PluginMetadata."""

    def test_minimal_metadata(self) -> None:
        """Test minimal metadata (author is required)."""
        meta = PluginMetadata(name="test-plugin", version="1.0.0", description="Test", author="Test Author")
        assert meta.name == "test-plugin"
        assert meta.version == "1.0.0"
        assert meta.author == "Test Author"

    def test_metadata_with_author(self) -> None:
        """Test metadata with author."""
        meta = PluginMetadata(name="my-plugin", version="1.0.0", description="My plugin", author="John Doe")
        assert meta.author == "John Doe"


class TestPluginManifest:
    """Tests for PluginManifest."""

    def test_manifest_creation(self) -> None:
        """Test creating manifest."""
        manifest = PluginManifest(
            schema_version="1.0",
            plugin=PluginMetadata(name="test-plugin", version="1.0.0", description="Test", author="Test Author"),
            capabilities=[CapabilitySpec(name="hello", description="Say hello")],
            execution=ExecutionSpec(
                type=ExecutionType.PYTHON, python=PythonExecutionSpec(module="test", **{"class": "Test"})
            ),
        )
        assert manifest.plugin.name == "test-plugin"
        assert len(manifest.capabilities) == 1

    def test_get_capability(self) -> None:
        """Test getting capability by name."""
        manifest = PluginManifest(
            schema_version="1.0",
            plugin=PluginMetadata(name="test", version="1.0.0", description="Test", author="Test Author"),
            capabilities=[
                CapabilitySpec(name="read", description="Read"),
                CapabilitySpec(name="write", description="Write"),
            ],
            execution=ExecutionSpec(type=ExecutionType.PYTHON, python=PythonExecutionSpec(module="t", **{"class": "T"})),
        )

        assert manifest.get_capability("read") is not None
        assert manifest.get_capability("write") is not None
        assert manifest.get_capability("delete") is None

    def test_get_all_anthropic_schemas(self) -> None:
        """Test getting all schemas."""
        manifest = PluginManifest(
            schema_version="1.0",
            plugin=PluginMetadata(name="multi", version="1.0.0", description="Multi", author="Test Author"),
            capabilities=[
                CapabilitySpec(name="a", description="A"),
                CapabilitySpec(name="b", description="B"),
            ],
            execution=ExecutionSpec(type=ExecutionType.PYTHON, python=PythonExecutionSpec(module="m", **{"class": "M"})),
        )

        schemas = manifest.get_all_anthropic_schemas()
        assert len(schemas) == 2
        names = [s["name"] for s in schemas]
        assert "multi_a" in names
        assert "multi_b" in names


class TestManifestLoading:
    """Tests for manifest file operations."""

    def test_load_manifest_yaml(self) -> None:
        """Test loading manifest from YAML."""
        yaml_content = """
schema_version: "1.0"
plugin:
  name: yaml-plugin
  version: 1.0.0
  description: YAML plugin
  author: Test Author
capabilities:
  - name: test
    description: Test action
execution:
  type: python
  python:
    module: yaml_plugin
    class: YamlPlugin
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            manifest = load_manifest(f.name)
            assert manifest.plugin.name == "yaml-plugin"
            assert len(manifest.capabilities) == 1

            Path(f.name).unlink()

    def test_find_manifest_mother_plugin_yaml(self) -> None:
        """Test finding mother-plugin.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "mother-plugin.yaml"
            manifest_path.write_text("""
schema_version: "1.0"
plugin:
  name: found
  version: 1.0.0
  description: Found
  author: Test Author
capabilities: []
execution:
  type: python
  python:
    module: found
    class: Found
""")
            found = find_manifest(Path(tmpdir))
            assert found is not None
            assert found.name == "mother-plugin.yaml"

    def test_find_manifest_not_found(self) -> None:
        """Test finding manifest in empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            found = find_manifest(Path(tmpdir))
            assert found is None
