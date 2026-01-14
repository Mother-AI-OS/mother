"""Tests for the init command."""

import json
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from mother.cli.init_cmd import (
    InitConfig,
    cmd_export,
    cmd_import,
    cmd_init,
    export_config,
    generate_files,
    import_config,
)


class TestInitConfig:
    """Tests for InitConfig."""

    def test_defaults(self):
        """Test default configuration."""
        config = InitConfig()
        assert config.output_dir == Path(".")
        assert config.include_docker is True
        assert config.include_policy is True
        assert config.include_env is True


class TestGenerateFiles:
    """Tests for generate_files."""

    def test_generates_all_files(self):
        """Test generating all files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = InitConfig(output_dir=Path(tmpdir))
            generated = generate_files(config)

            assert len(generated) == 4

            # Check all files exist
            assert (Path(tmpdir) / "docker-compose.yml").exists()
            assert (Path(tmpdir) / "Dockerfile").exists()
            assert (Path(tmpdir) / ".env.example").exists()
            assert (Path(tmpdir) / "config" / "policy.yaml").exists()

    def test_skip_docker(self):
        """Test skipping Docker files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = InitConfig(
                output_dir=Path(tmpdir),
                include_docker=False,
            )
            generate_files(config)

            assert not (Path(tmpdir) / "docker-compose.yml").exists()
            assert not (Path(tmpdir) / "Dockerfile").exists()
            assert (Path(tmpdir) / ".env.example").exists()

    def test_skip_policy(self):
        """Test skipping policy template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = InitConfig(
                output_dir=Path(tmpdir),
                include_policy=False,
            )
            generate_files(config)

            assert not (Path(tmpdir) / "config" / "policy.yaml").exists()

    def test_skip_env(self):
        """Test skipping .env.example."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = InitConfig(
                output_dir=Path(tmpdir),
                include_env=False,
            )
            generate_files(config)

            assert not (Path(tmpdir) / ".env.example").exists()

    def test_creates_output_dir(self):
        """Test creating output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "subdir" / "nested"
            config = InitConfig(output_dir=output_dir)
            generated = generate_files(config)

            assert output_dir.exists()
            assert len(generated) > 0


class TestDockerCompose:
    """Tests for docker-compose.yml content."""

    def test_contains_required_fields(self):
        """Test docker-compose.yml has required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = InitConfig(output_dir=Path(tmpdir))
            generate_files(config)

            compose_path = Path(tmpdir) / "docker-compose.yml"
            content = compose_path.read_text()

            assert "services:" in content
            assert "mother:" in content
            assert "volumes:" in content
            assert "networks:" in content
            assert "healthcheck:" in content


class TestEnvExample:
    """Tests for .env.example content."""

    def test_contains_required_vars(self):
        """Test .env.example has required variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = InitConfig(output_dir=Path(tmpdir))
            generate_files(config)

            env_path = Path(tmpdir) / ".env.example"
            content = env_path.read_text()

            assert "AI_PROVIDER=" in content
            assert "ANTHROPIC_API_KEY=" in content
            assert "MOTHER_REQUIRE_AUTH=" in content
            assert "MOTHER_SAFE_MODE=" in content
            assert "MOTHER_SANDBOX_MODE=" in content


class TestPolicyTemplate:
    """Tests for policy.yaml content."""

    def test_contains_required_sections(self):
        """Test policy.yaml has required sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = InitConfig(output_dir=Path(tmpdir))
            generate_files(config)

            policy_path = Path(tmpdir) / "config" / "policy.yaml"
            content = policy_path.read_text()

            assert "version:" in content
            assert "settings:" in content
            assert "rules:" in content
            assert "roles:" in content


class TestExportConfig:
    """Tests for export_config."""

    def test_creates_archive(self):
        """Test creating export archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.tar.gz"

            mock_settings = MagicMock()
            mock_settings.config_dir = Path(tmpdir) / "config"
            mock_settings.policy_path = None
            mock_settings.safe_mode = True
            mock_settings.sandbox_mode = True
            mock_settings.require_auth = True
            mock_settings.audit_log_enabled = True

            # Create config dir
            mock_settings.config_dir.mkdir(parents=True)

            with patch("mother.config.settings.get_settings", return_value=mock_settings):
                metadata = export_config(output_path)

            assert output_path.exists()
            assert "version" in metadata
            assert "exported_at" in metadata

    def test_export_includes_manifest(self):
        """Test export includes manifest.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.tar.gz"
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()

            mock_settings = MagicMock()
            mock_settings.config_dir = config_dir
            mock_settings.policy_path = None
            mock_settings.safe_mode = True
            mock_settings.sandbox_mode = True
            mock_settings.require_auth = True
            mock_settings.audit_log_enabled = True

            with patch("mother.config.settings.get_settings", return_value=mock_settings):
                export_config(output_path)

            # Extract and check
            extract_dir = Path(tmpdir) / "extracted"
            extract_dir.mkdir()
            with tarfile.open(output_path, "r:gz") as tar:
                tar.extractall(extract_dir, filter="data")

            manifest_path = extract_dir / "mother-export" / "manifest.json"
            assert manifest_path.exists()


class TestImportConfig:
    """Tests for import_config."""

    def test_imports_files(self):
        """Test importing configuration files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create export archive
            export_path = Path(tmpdir) / "export.tar.gz"
            config_dir = Path(tmpdir) / "source-config"
            config_dir.mkdir()

            # Create a test file
            test_file = config_dir / "plugins.json"
            test_file.write_text('{"plugins": []}')

            mock_settings = MagicMock()
            mock_settings.config_dir = config_dir
            mock_settings.policy_path = None
            mock_settings.safe_mode = True
            mock_settings.sandbox_mode = True
            mock_settings.require_auth = True
            mock_settings.audit_log_enabled = True

            with patch("mother.config.settings.get_settings", return_value=mock_settings):
                export_config(export_path)

            # Import to new location
            dest_config = Path(tmpdir) / "dest-config"
            dest_config.mkdir()

            mock_dest_settings = MagicMock()
            mock_dest_settings.config_dir = dest_config

            with patch("mother.config.settings.get_settings", return_value=mock_dest_settings):
                result = import_config(export_path)

            assert "plugins.json" in result["imported"]
            assert (dest_config / "plugins.json").exists()

    def test_import_skips_existing(self):
        """Test import skips existing files without force."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create export archive
            export_path = Path(tmpdir) / "export.tar.gz"
            config_dir = Path(tmpdir) / "source-config"
            config_dir.mkdir()

            test_file = config_dir / "plugins.json"
            test_file.write_text('{"plugins": []}')

            mock_settings = MagicMock()
            mock_settings.config_dir = config_dir
            mock_settings.policy_path = None
            mock_settings.safe_mode = True
            mock_settings.sandbox_mode = True
            mock_settings.require_auth = True
            mock_settings.audit_log_enabled = True

            with patch("mother.config.settings.get_settings", return_value=mock_settings):
                export_config(export_path)

            # Create existing file at destination
            dest_config = Path(tmpdir) / "dest-config"
            dest_config.mkdir()
            (dest_config / "plugins.json").write_text('{"existing": true}')

            mock_dest_settings = MagicMock()
            mock_dest_settings.config_dir = dest_config

            with patch("mother.config.settings.get_settings", return_value=mock_dest_settings):
                result = import_config(export_path, force=False)

            assert "plugins.json" not in result["imported"]
            assert any("plugins.json" in s for s in result["skipped"])

    def test_import_force_overwrites(self):
        """Test import with force overwrites existing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create export archive
            export_path = Path(tmpdir) / "export.tar.gz"
            config_dir = Path(tmpdir) / "source-config"
            config_dir.mkdir()

            test_file = config_dir / "plugins.json"
            test_file.write_text('{"plugins": ["new"]}')

            mock_settings = MagicMock()
            mock_settings.config_dir = config_dir
            mock_settings.policy_path = None
            mock_settings.safe_mode = True
            mock_settings.sandbox_mode = True
            mock_settings.require_auth = True
            mock_settings.audit_log_enabled = True

            with patch("mother.config.settings.get_settings", return_value=mock_settings):
                export_config(export_path)

            # Create existing file at destination
            dest_config = Path(tmpdir) / "dest-config"
            dest_config.mkdir()
            (dest_config / "plugins.json").write_text('{"existing": true}')

            mock_dest_settings = MagicMock()
            mock_dest_settings.config_dir = dest_config

            with patch("mother.config.settings.get_settings", return_value=mock_dest_settings):
                result = import_config(export_path, force=True)

            assert "plugins.json" in result["imported"]
            content = (dest_config / "plugins.json").read_text()
            assert "new" in content


class TestCmdInit:
    """Tests for cmd_init command."""

    def test_json_output(self, capsys):
        """Test JSON output mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = cmd_init(output_dir=tmpdir, json_output=True)
            captured = capsys.readouterr()

            assert exit_code == 0
            data = json.loads(captured.out)
            assert "output_dir" in data
            assert "files" in data

    def test_normal_output(self, capsys):
        """Test normal output mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = cmd_init(output_dir=tmpdir)
            captured = capsys.readouterr()

            assert exit_code == 0
            assert "Initialized Mother" in captured.out
            assert "Generated files:" in captured.out
            assert "Next steps:" in captured.out


class TestCmdExport:
    """Tests for cmd_export command."""

    def test_json_output(self, capsys):
        """Test JSON output mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "export.tar.gz"
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()

            mock_settings = MagicMock()
            mock_settings.config_dir = config_dir
            mock_settings.policy_path = None
            mock_settings.safe_mode = True
            mock_settings.sandbox_mode = True
            mock_settings.require_auth = True
            mock_settings.audit_log_enabled = True

            with patch("mother.config.settings.get_settings", return_value=mock_settings):
                exit_code = cmd_export(output=str(output_path), json_output=True)

            captured = capsys.readouterr()
            assert exit_code == 0
            data = json.loads(captured.out)
            assert "version" in data


class TestCmdImport:
    """Tests for cmd_import command."""

    def test_archive_not_found(self, capsys):
        """Test error when archive not found."""
        exit_code = cmd_import("/nonexistent/archive.tar.gz", json_output=True)
        captured = capsys.readouterr()

        assert exit_code == 1
        data = json.loads(captured.out)
        assert "error" in data
