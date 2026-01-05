"""Tests for the credentials module."""

import os
from unittest.mock import patch

import pytest

from mother import credentials


class TestCredentialsModule:
    """Tests for credentials module functions."""

    @pytest.fixture
    def temp_credentials_file(self, tmp_path):
        """Create a temporary credentials file."""
        cred_file = tmp_path / "credentials.env"
        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            yield cred_file

    @pytest.fixture
    def populated_credentials_file(self, temp_credentials_file):
        """Create a populated credentials file."""
        content = """
# Test credentials
ANTHROPIC_API_KEY=test_anthropic_key
OPENAI_API_KEY=test_openai_key
MOTHER_HOST=localhost
MAILCRAFT_PASSWORD=secret123
CUSTOM_VAR=custom_value
"""
        temp_credentials_file.write_text(content)
        return temp_credentials_file


class TestEnsureFileExists:
    """Tests for ensure_file_exists function."""

    def test_creates_directory(self, tmp_path):
        """Test creates parent directory if missing."""
        cred_file = tmp_path / "subdir" / "credentials.env"
        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.ensure_file_exists()
            assert cred_file.parent.exists()

    def test_creates_file(self, tmp_path):
        """Test creates file if missing."""
        cred_file = tmp_path / "credentials.env"
        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.ensure_file_exists()
            assert cred_file.exists()

    def test_sets_permissions(self, tmp_path):
        """Test sets secure permissions on file."""
        cred_file = tmp_path / "credentials.env"
        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.ensure_file_exists()
            # Check file is readable only by owner
            mode = cred_file.stat().st_mode & 0o777
            assert mode == 0o600


class TestReadCredentials:
    """Tests for read_credentials function."""

    def test_reads_credentials(self, tmp_path):
        """Test reading credentials from file."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY1=value1\nKEY2=value2\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            result = credentials.read_credentials()

        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_ignores_comments(self, tmp_path):
        """Test comments are ignored."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("# Comment\nKEY=value\n# Another comment\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            result = credentials.read_credentials()

        assert result == {"KEY": "value"}

    def test_ignores_empty_lines(self, tmp_path):
        """Test empty lines are ignored."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY1=value1\n\n\nKEY2=value2\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            result = credentials.read_credentials()

        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_handles_values_with_equals(self, tmp_path):
        """Test values containing equals sign."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY=value=with=equals\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            result = credentials.read_credentials()

        assert result == {"KEY": "value=with=equals"}

    def test_strips_whitespace(self, tmp_path):
        """Test whitespace is stripped."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("  KEY  =  value  \n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            result = credentials.read_credentials()

        assert result == {"KEY": "value"}

    def test_empty_file(self, tmp_path):
        """Test reading empty file."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            result = credentials.read_credentials()

        assert result == {}


class TestWriteCredentials:
    """Tests for write_credentials function."""

    def test_writes_credentials(self, tmp_path):
        """Test writing credentials to file."""
        cred_file = tmp_path / "credentials.env"

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.write_credentials({"KEY": "value"})

        content = cred_file.read_text()
        assert "KEY=value" in content

    def test_writes_with_categories(self, tmp_path):
        """Test credentials are categorized."""
        cred_file = tmp_path / "credentials.env"

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.write_credentials(
                {
                    "ANTHROPIC_API_KEY": "test1",
                    "MOTHER_HOST": "localhost",
                    "CUSTOM_VAR": "value",
                }
            )

        content = cred_file.read_text()
        assert "AI API Keys" in content
        assert "Mother Agent" in content
        assert "Other" in content

    def test_sets_secure_permissions(self, tmp_path):
        """Test file has secure permissions after write."""
        cred_file = tmp_path / "credentials.env"

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.write_credentials({"KEY": "value"})

        mode = cred_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_writes_sorted(self, tmp_path):
        """Test credentials within categories are sorted."""
        cred_file = tmp_path / "credentials.env"

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.write_credentials(
                {
                    "ANTHROPIC_KEY_B": "b",
                    "ANTHROPIC_KEY_A": "a",
                }
            )

        content = cred_file.read_text()
        pos_a = content.find("ANTHROPIC_KEY_A")
        pos_b = content.find("ANTHROPIC_KEY_B")
        assert pos_a < pos_b


class TestMaskValue:
    """Tests for mask_value function."""

    def test_masks_long_value(self):
        """Test masking long value."""
        result = credentials.mask_value("abcd1234efgh5678")
        assert result == "abcd********5678"
        assert result.startswith("abcd")
        assert result.endswith("5678")
        assert "*" in result

    def test_masks_short_value(self):
        """Test masking short value."""
        result = credentials.mask_value("short")
        assert result == "*****"

    def test_masks_8_char_value(self):
        """Test masking exactly 8 character value."""
        result = credentials.mask_value("12345678")
        assert result == "********"

    def test_empty_value(self):
        """Test masking empty value."""
        result = credentials.mask_value("")
        assert result == "(empty)"


class TestGetCredential:
    """Tests for get_credential function."""

    def test_gets_existing_credential(self, tmp_path):
        """Test getting existing credential."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("API_KEY=secret123\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            result = credentials.get_credential("API_KEY")

        assert result == "secret123"

    def test_returns_none_for_missing(self, tmp_path):
        """Test returns None for missing credential."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("OTHER_KEY=value\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            result = credentials.get_credential("MISSING_KEY")

        assert result is None


class TestSetCredential:
    """Tests for set_credential function."""

    def test_adds_new_credential(self, tmp_path, capsys):
        """Test adding new credential."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.set_credential("NEW_KEY", "new_value")

        content = cred_file.read_text()
        assert "NEW_KEY=new_value" in content

        captured = capsys.readouterr()
        assert "Added:" in captured.out

    def test_updates_existing_credential(self, tmp_path, capsys):
        """Test updating existing credential."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY=old_value\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.set_credential("KEY", "new_value")

        content = cred_file.read_text()
        assert "KEY=new_value" in content
        assert "old_value" not in content

        captured = capsys.readouterr()
        assert "Updated:" in captured.out


class TestDeleteCredential:
    """Tests for delete_credential function."""

    def test_deletes_existing_credential(self, tmp_path, capsys):
        """Test deleting existing credential."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY=value\nOTHER=keep\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            result = credentials.delete_credential("KEY")

        assert result is True
        content = cred_file.read_text()
        assert "KEY=" not in content
        assert "OTHER=keep" in content

        captured = capsys.readouterr()
        assert "Deleted:" in captured.out

    def test_returns_false_for_missing(self, tmp_path, capsys):
        """Test returns False for missing credential."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("OTHER=value\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            result = credentials.delete_credential("MISSING")

        assert result is False

        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestSearchCredentials:
    """Tests for search_credentials function."""

    def test_finds_matching_credentials(self, tmp_path, capsys):
        """Test finding matching credentials."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("API_KEY_1=value1\nAPI_KEY_2=value2\nOTHER=value3\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.search_credentials("API_KEY")

        captured = capsys.readouterr()
        assert "API_KEY_1" in captured.out
        assert "API_KEY_2" in captured.out
        assert "OTHER" not in captured.out

    def test_case_insensitive_search(self, tmp_path, capsys):
        """Test case insensitive search."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("ANTHROPIC_KEY=value\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.search_credentials("anthropic")

        captured = capsys.readouterr()
        assert "ANTHROPIC_KEY" in captured.out

    def test_no_matches(self, tmp_path, capsys):
        """Test no matching credentials."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY=value\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.search_credentials("nonexistent")

        captured = capsys.readouterr()
        assert "No credentials matching" in captured.out


class TestListCredentials:
    """Tests for list_credentials function."""

    def test_lists_credentials_masked(self, tmp_path, capsys):
        """Test listing credentials with masked values."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("API_KEY=secret1234567890\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.list_credentials(show_values=False)

        captured = capsys.readouterr()
        assert "API_KEY" in captured.out
        assert "secret1234567890" not in captured.out
        assert "****" in captured.out

    def test_lists_credentials_unmasked(self, tmp_path, capsys):
        """Test listing credentials with full values."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("API_KEY=secret1234567890\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.list_credentials(show_values=True)

        captured = capsys.readouterr()
        assert "API_KEY" in captured.out
        assert "secret1234567890" in captured.out

    def test_empty_credentials(self, tmp_path, capsys):
        """Test listing empty credentials."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            credentials.list_credentials()

        captured = capsys.readouterr()
        assert "No credentials configured" in captured.out


class TestInteractiveEdit:
    """Tests for interactive_edit function."""

    def test_calls_editor(self, tmp_path):
        """Test calls editor with credentials file."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("os.system") as mock_system:
                credentials.interactive_edit()

        mock_system.assert_called_once()
        call_arg = mock_system.call_args[0][0]
        assert str(cred_file) in call_arg

    def test_uses_editor_env_var(self, tmp_path):
        """Test uses EDITOR environment variable."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch.dict(os.environ, {"EDITOR": "vim"}):
                with patch("os.system") as mock_system:
                    credentials.interactive_edit()

        call_arg = mock_system.call_args[0][0]
        assert "vim" in call_arg


class TestMain:
    """Tests for main CLI function."""

    def test_no_args_prints_usage(self, capsys):
        """Test no arguments prints usage."""
        with patch("sys.argv", ["credentials"]):
            credentials.main()

        captured = capsys.readouterr()
        assert "Usage:" in captured.out

    def test_help_prints_usage(self, capsys):
        """Test --help prints usage."""
        with patch("sys.argv", ["credentials", "--help"]):
            credentials.main()

        captured = capsys.readouterr()
        assert "Usage:" in captured.out

    def test_path_command(self, tmp_path, capsys):
        """Test path command."""
        cred_file = tmp_path / "credentials.env"

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "path"]):
                credentials.main()

        captured = capsys.readouterr()
        assert str(cred_file) in captured.out

    def test_list_command(self, tmp_path, capsys):
        """Test list command."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY=value\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "list"]):
                credentials.main()

        captured = capsys.readouterr()
        assert "KEY" in captured.out

    def test_get_command(self, tmp_path, capsys):
        """Test get command."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("API_KEY=secret\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "get", "API_KEY"]):
                credentials.main()

        captured = capsys.readouterr()
        assert "secret" in captured.out

    def test_get_command_missing_key(self, tmp_path, capsys):
        """Test get command with missing key."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "get", "MISSING"]):
                with pytest.raises(SystemExit) as exc_info:
                    credentials.main()

        assert exc_info.value.code == 1

    def test_set_command(self, tmp_path, capsys):
        """Test set command."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "set", "NEW_KEY", "value"]):
                credentials.main()

        content = cred_file.read_text()
        assert "NEW_KEY=value" in content

    def test_delete_command(self, tmp_path, capsys):
        """Test delete command."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY=value\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "delete", "KEY"]):
                credentials.main()

        content = cred_file.read_text()
        assert "KEY=" not in content

    def test_search_command(self, tmp_path, capsys):
        """Test search command."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("API_KEY=value\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "search", "API"]):
                credentials.main()

        captured = capsys.readouterr()
        assert "API_KEY" in captured.out

    def test_unknown_command(self, tmp_path, capsys):
        """Test unknown command."""
        cred_file = tmp_path / "credentials.env"

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "unknown"]):
                with pytest.raises(SystemExit) as exc_info:
                    credentials.main()

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Unknown command" in captured.out

    def test_get_without_key_arg(self, capsys):
        """Test get command without key argument (covers lines 210-211)."""
        with patch("sys.argv", ["credentials", "get"]):
            credentials.main()

        captured = capsys.readouterr()
        assert "Usage: mother credentials get <KEY>" in captured.out

    def test_set_without_args(self, capsys):
        """Test set command without arguments (covers lines 221-222)."""
        with patch("sys.argv", ["credentials", "set"]):
            credentials.main()

        captured = capsys.readouterr()
        assert "Usage: mother credentials set <KEY> <VALUE>" in captured.out

    def test_set_without_value_arg(self, capsys):
        """Test set command with only key argument."""
        with patch("sys.argv", ["credentials", "set", "KEY"]):
            credentials.main()

        captured = capsys.readouterr()
        assert "Usage: mother credentials set <KEY> <VALUE>" in captured.out

    def test_delete_without_key_arg(self, capsys):
        """Test delete command without key argument (covers lines 227-228)."""
        with patch("sys.argv", ["credentials", "delete"]):
            credentials.main()

        captured = capsys.readouterr()
        assert "Usage: mother credentials delete <KEY>" in captured.out

    def test_delete_nonexistent_key_exits(self, tmp_path):
        """Test delete command with nonexistent key exits (covers line 230)."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "delete", "MISSING_KEY"]):
                with pytest.raises(SystemExit) as exc_info:
                    credentials.main()

        assert exc_info.value.code == 1

    def test_search_without_pattern_arg(self, capsys):
        """Test search command without pattern argument (covers lines 234-235)."""
        with patch("sys.argv", ["credentials", "search"]):
            credentials.main()

        captured = capsys.readouterr()
        assert "Usage: mother credentials search <PATTERN>" in captured.out

    def test_edit_command(self, tmp_path):
        """Test edit command (covers line 239)."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("os.system") as mock_system:
                with patch("sys.argv", ["credentials", "edit"]):
                    credentials.main()

        mock_system.assert_called_once()
        call_arg = mock_system.call_args[0][0]
        assert str(cred_file) in call_arg

    def test_h_flag(self, capsys):
        """Test -h flag prints usage."""
        with patch("sys.argv", ["credentials", "-h"]):
            credentials.main()

        captured = capsys.readouterr()
        assert "Usage:" in captured.out

    def test_list_with_show_flag(self, tmp_path, capsys):
        """Test list command with --show flag."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY=secretvalue12345\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "list", "--show"]):
                credentials.main()

        captured = capsys.readouterr()
        assert "secretvalue12345" in captured.out

    def test_list_with_s_flag(self, tmp_path, capsys):
        """Test list command with -s flag."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY=secretvalue12345\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "list", "-s"]):
                credentials.main()

        captured = capsys.readouterr()
        assert "secretvalue12345" in captured.out

    def test_rm_alias(self, tmp_path, capsys):
        """Test rm alias for delete command."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("KEY=value\n")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch("sys.argv", ["credentials", "rm", "KEY"]):
                credentials.main()

        captured = capsys.readouterr()
        assert "Deleted:" in captured.out

    def test_set_multi_word_value(self, tmp_path, capsys):
        """Test set command with multi-word value."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("")

        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            with patch(
                "sys.argv", ["credentials", "set", "KEY", "multi", "word", "value"]
            ):
                credentials.main()

        content = cred_file.read_text()
        assert "KEY=multi word value" in content
