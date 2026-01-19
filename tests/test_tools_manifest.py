"""Tests for the tool manifest module."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest
import yaml

from mother.tools.exceptions import ToolManifestError, ToolManifestNotFoundError
from mother.tools.tool_manifest import (
    CLIIntegration,
    ConfigField,
    DockerIntegration,
    HTTPIntegration,
    IntegrationSpec,
    IntegrationType,
    PythonIntegration,
    RiskLevel,
    ToolManifest,
    ToolMetadata,
    find_tool_manifest,
    load_tool_manifest,
    validate_tool_manifest,
    validate_tool_name,
)


class TestValidateToolName:
    """Tests for validate_tool_name function."""

    def test_valid_names(self):
        """Test valid tool names."""
        assert validate_tool_name("abc") is True
        assert validate_tool_name("my-tool") is True
        assert validate_tool_name("tool123") is True
        assert validate_tool_name("my-awesome-tool-v2") is True
        assert validate_tool_name("contentcraft") is True
        assert validate_tool_name("lead-engine") is True

    def test_invalid_names_too_short(self):
        """Test names that are too short."""
        assert validate_tool_name("ab") is False
        assert validate_tool_name("a") is False
        assert validate_tool_name("") is False

    def test_invalid_names_too_long(self):
        """Test names that are too long."""
        assert validate_tool_name("a" * 31) is False

    def test_invalid_names_wrong_chars(self):
        """Test names with invalid characters."""
        assert validate_tool_name("MyTool") is False  # uppercase
        assert validate_tool_name("my_tool") is False  # underscore
        assert validate_tool_name("my.tool") is False  # dot
        assert validate_tool_name("my tool") is False  # space
        assert validate_tool_name("123tool") is False  # starts with number
        assert validate_tool_name("-tool") is False  # starts with hyphen


class TestFindToolManifest:
    """Tests for find_tool_manifest function."""

    def test_find_yaml_extension(self):
        """Test finding mother-tool.yaml."""
        with TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "mother-tool.yaml"
            manifest_path.write_text("test: true")

            result = find_tool_manifest(Path(tmpdir))
            assert result == manifest_path

    def test_find_yml_extension(self):
        """Test finding mother-tool.yml."""
        with TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "mother-tool.yml"
            manifest_path.write_text("test: true")

            result = find_tool_manifest(Path(tmpdir))
            assert result == manifest_path

    def test_prefers_yaml_over_yml(self):
        """Test that .yaml is preferred over .yml."""
        with TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "mother-tool.yaml"
            yml_path = Path(tmpdir) / "mother-tool.yml"
            yaml_path.write_text("test: yaml")
            yml_path.write_text("test: yml")

            result = find_tool_manifest(Path(tmpdir))
            assert result == yaml_path

    def test_not_found(self):
        """Test when no manifest exists."""
        with TemporaryDirectory() as tmpdir:
            result = find_tool_manifest(Path(tmpdir))
            assert result is None


class TestLoadToolManifest:
    """Tests for load_tool_manifest function."""

    def test_load_from_file(self):
        """Test loading manifest from file path."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        manifest = load_tool_manifest(fixtures_dir / "mother-tool-sample.yaml")

        assert manifest.name == "sample-tool"
        assert manifest.version == "1.2.3"
        assert manifest.tool.description == "A sample tool for testing the tool registry"
        assert manifest.tool.author == "Mother AI OS Team"
        assert manifest.tool.risk_level == RiskLevel.LOW
        assert manifest.integration.type == IntegrationType.CLI
        assert manifest.integration.cli.binary == "sample-tool"
        assert "filesystem:read" in manifest.permissions

    def test_load_from_directory(self):
        """Test loading manifest from directory."""
        with TemporaryDirectory() as tmpdir:
            manifest_content = {
                "schema_version": "1.0",
                "tool": {
                    "name": "test-tool",
                    "version": "1.0.0",
                    "description": "Test",
                },
                "integration": {
                    "type": "cli",
                    "cli": {"binary": "test"},
                },
            }
            manifest_path = Path(tmpdir) / "mother-tool.yaml"
            with open(manifest_path, "w") as f:
                yaml.dump(manifest_content, f)

            manifest = load_tool_manifest(Path(tmpdir))
            assert manifest.name == "test-tool"

    def test_load_not_found(self):
        """Test loading from non-existent path."""
        with pytest.raises(ToolManifestNotFoundError):
            load_tool_manifest(Path("/nonexistent/path"))

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()

            with pytest.raises(ToolManifestError):
                load_tool_manifest(Path(f.name))


class TestValidateToolManifest:
    """Tests for validate_tool_manifest function."""

    def test_minimal_valid_manifest(self):
        """Test minimal valid manifest."""
        data = {
            "schema_version": "1.0",
            "tool": {
                "name": "test-tool",
                "version": "1.0.0",
                "description": "A test tool",
            },
            "integration": {
                "type": "cli",
                "cli": {"binary": "test-tool"},
            },
        }

        manifest = validate_tool_manifest(data)
        assert manifest.name == "test-tool"
        assert manifest.version == "1.0.0"
        assert manifest.integration.type == IntegrationType.CLI

    def test_full_cli_manifest(self):
        """Test full CLI manifest."""
        data = {
            "schema_version": "1.0",
            "tool": {
                "name": "full-tool",
                "version": "2.0.0",
                "description": "Full featured tool",
                "author": "Test Author",
                "homepage": "https://example.com",
                "repository": "https://github.com/test/repo",
                "license": "MIT",
                "risk_level": "medium",
                "tags": ["test", "full"],
            },
            "integration": {
                "type": "cli",
                "cli": {
                    "binary": "full-tool",
                    "install_command": "pip install full-tool",
                    "health_check": "full-tool --health",
                    "output_format": "json",
                },
            },
            "permissions": ["filesystem:read", "network:external"],
            "config": [
                {
                    "name": "api_key",
                    "description": "API key",
                    "type": "string",
                    "required": True,
                    "secret": True,
                }
            ],
            "dependencies": ["python>=3.11"],
        }

        manifest = validate_tool_manifest(data)
        assert manifest.tool.author == "Test Author"
        assert manifest.tool.risk_level == RiskLevel.MEDIUM
        assert len(manifest.config) == 1
        assert manifest.config[0].secret is True

    def test_python_integration(self):
        """Test Python integration manifest."""
        data = {
            "schema_version": "1.0",
            "tool": {
                "name": "python-tool",
                "version": "1.0.0",
            },
            "integration": {
                "type": "python",
                "python": {
                    "module": "my_tool.main",
                    "class_name": "MyToolPlugin",
                    "entrypoint": "main",
                    "install_command": "pip install my-tool",
                },
            },
        }

        manifest = validate_tool_manifest(data)
        assert manifest.integration.type == IntegrationType.PYTHON
        assert manifest.integration.python.module == "my_tool.main"
        assert manifest.integration.python.class_name == "MyToolPlugin"

    def test_http_integration(self):
        """Test HTTP integration manifest."""
        data = {
            "schema_version": "1.0",
            "tool": {
                "name": "http-tool",
                "version": "1.0.0",
            },
            "integration": {
                "type": "http",
                "http": {
                    "base_url": "http://localhost:9000",
                    "port": 9000,
                    "health_endpoint": "/api/health",
                    "start_command": "python -m http_tool serve",
                },
            },
        }

        manifest = validate_tool_manifest(data)
        assert manifest.integration.type == IntegrationType.HTTP
        assert manifest.integration.http.port == 9000
        assert manifest.integration.http.health_endpoint == "/api/health"

    def test_docker_integration(self):
        """Test Docker integration manifest."""
        data = {
            "schema_version": "1.0",
            "tool": {
                "name": "docker-tool",
                "version": "1.0.0",
            },
            "integration": {
                "type": "docker",
                "docker": {
                    "image": "myrepo/docker-tool",
                    "tag": "v1.0",
                    "ports": {8080: 80},
                    "volumes": {"/data": "/app/data"},
                    "environment": {"DEBUG": "true"},
                },
            },
        }

        manifest = validate_tool_manifest(data)
        assert manifest.integration.type == IntegrationType.DOCKER
        assert manifest.integration.docker.image == "myrepo/docker-tool"
        assert manifest.integration.docker.tag == "v1.0"

    def test_missing_tool_section(self):
        """Test manifest without tool section."""
        data = {
            "schema_version": "1.0",
            "integration": {"type": "cli", "cli": {"binary": "test"}},
        }

        with pytest.raises(ToolManifestError) as exc_info:
            validate_tool_manifest(data)
        assert "Missing 'tool' section" in str(exc_info.value)

    def test_missing_integration_section(self):
        """Test manifest without integration section."""
        data = {
            "schema_version": "1.0",
            "tool": {"name": "test-tool", "version": "1.0.0"},
        }

        with pytest.raises(ToolManifestError) as exc_info:
            validate_tool_manifest(data)
        assert "Missing 'integration' section" in str(exc_info.value)

    def test_invalid_tool_name(self):
        """Test manifest with invalid tool name."""
        data = {
            "schema_version": "1.0",
            "tool": {"name": "Invalid_Name", "version": "1.0.0"},
            "integration": {"type": "cli", "cli": {"binary": "test"}},
        }

        with pytest.raises(ToolManifestError) as exc_info:
            validate_tool_manifest(data)
        assert "Invalid tool name" in str(exc_info.value)

    def test_missing_version(self):
        """Test manifest without version."""
        data = {
            "schema_version": "1.0",
            "tool": {"name": "test-tool"},
            "integration": {"type": "cli", "cli": {"binary": "test"}},
        }

        with pytest.raises(ToolManifestError) as exc_info:
            validate_tool_manifest(data)
        assert "Missing 'version' field" in str(exc_info.value)

    def test_invalid_integration_type(self):
        """Test manifest with invalid integration type."""
        data = {
            "schema_version": "1.0",
            "tool": {"name": "test-tool", "version": "1.0.0"},
            "integration": {"type": "invalid"},
        }

        with pytest.raises(ToolManifestError) as exc_info:
            validate_tool_manifest(data)
        assert "Invalid integration type" in str(exc_info.value)

    def test_python_integration_missing_module(self):
        """Test Python integration without module."""
        data = {
            "schema_version": "1.0",
            "tool": {"name": "test-tool", "version": "1.0.0"},
            "integration": {"type": "python", "python": {}},
        }

        with pytest.raises(ToolManifestError) as exc_info:
            validate_tool_manifest(data)
        assert "module" in str(exc_info.value)

    def test_cli_integration_missing_binary(self):
        """Test CLI integration without binary."""
        data = {
            "schema_version": "1.0",
            "tool": {"name": "test-tool", "version": "1.0.0"},
            "integration": {"type": "cli", "cli": {}},
        }

        with pytest.raises(ToolManifestError) as exc_info:
            validate_tool_manifest(data)
        assert "binary" in str(exc_info.value)

    def test_docker_integration_missing_image(self):
        """Test Docker integration without image."""
        data = {
            "schema_version": "1.0",
            "tool": {"name": "test-tool", "version": "1.0.0"},
            "integration": {"type": "docker", "docker": {}},
        }

        with pytest.raises(ToolManifestError) as exc_info:
            validate_tool_manifest(data)
        assert "image" in str(exc_info.value)


class TestToolManifest:
    """Tests for ToolManifest class methods."""

    def test_is_high_risk(self):
        """Test is_high_risk method."""
        fixtures_dir = Path(__file__).parent / "fixtures"

        # Low risk
        low_risk = load_tool_manifest(fixtures_dir / "mother-tool-sample.yaml")
        assert low_risk.is_high_risk() is False

        # High risk
        high_risk = load_tool_manifest(fixtures_dir / "mother-tool-highrisk.yaml")
        assert high_risk.is_high_risk() is True

    def test_get_high_risk_permissions(self):
        """Test get_high_risk_permissions method."""
        fixtures_dir = Path(__file__).parent / "fixtures"

        # Low risk tool
        low_risk = load_tool_manifest(fixtures_dir / "mother-tool-sample.yaml")
        high_risk_perms = low_risk.get_high_risk_permissions()
        # network:external is flagged
        assert "network:external" in high_risk_perms

        # High risk tool
        high_risk = load_tool_manifest(fixtures_dir / "mother-tool-highrisk.yaml")
        high_risk_perms = high_risk.get_high_risk_permissions()
        assert "shell" in high_risk_perms
        assert "subprocess" in high_risk_perms
        assert "filesystem:write" in high_risk_perms

    def test_to_dict(self):
        """Test to_dict serialization."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        manifest = load_tool_manifest(fixtures_dir / "mother-tool-sample.yaml")

        data = manifest.to_dict()

        assert data["schema_version"] == "1.0"
        assert data["tool"]["name"] == "sample-tool"
        assert data["tool"]["version"] == "1.2.3"
        assert data["integration"]["type"] == "cli"
        assert data["integration"]["cli"]["binary"] == "sample-tool"
        assert "filesystem:read" in data["permissions"]

    def test_properties(self):
        """Test manifest properties."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        manifest = load_tool_manifest(fixtures_dir / "mother-tool-sample.yaml")

        assert manifest.name == "sample-tool"
        assert manifest.version == "1.2.3"
        assert manifest.risk_level == RiskLevel.LOW


class TestIntegrationDataclasses:
    """Tests for integration dataclasses."""

    def test_python_integration_defaults(self):
        """Test PythonIntegration defaults."""
        integration = PythonIntegration(module="test.module")
        assert integration.module == "test.module"
        assert integration.class_name is None
        assert integration.entrypoint is None
        assert integration.install_command is None

    def test_cli_integration_defaults(self):
        """Test CLIIntegration defaults."""
        integration = CLIIntegration(binary="mytool")
        assert integration.binary == "mytool"
        assert integration.install_command is None
        assert integration.health_check is None
        assert integration.output_format == "text"

    def test_http_integration_defaults(self):
        """Test HTTPIntegration defaults."""
        integration = HTTPIntegration()
        assert integration.base_url is None
        assert integration.port == 8000
        assert integration.health_endpoint == "/health"
        assert integration.start_command is None

    def test_docker_integration_defaults(self):
        """Test DockerIntegration defaults."""
        integration = DockerIntegration(image="myimage")
        assert integration.image == "myimage"
        assert integration.tag == "latest"
        assert integration.ports == {}
        assert integration.volumes == {}
        assert integration.environment == {}
