"""Tests for the setup CLI module."""

from unittest.mock import patch

import pytest

from mother import credentials
from mother.cli import setup


class TestSetupWizard:
    """Tests for the setup wizard."""

    @pytest.fixture
    def temp_credentials_file(self, tmp_path):
        """Create a temporary credentials file."""
        cred_file = tmp_path / "credentials.env"
        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            yield cred_file

    def test_print_header(self, capsys):
        """Test header is printed correctly."""
        setup.print_header()
        captured = capsys.readouterr()
        assert "Mother AI OS Setup" in captured.out

    def test_prompt_with_default(self, monkeypatch):
        """Test prompt with default value."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = setup.prompt("Test question", default="default_value")
        assert result == "default_value"

    def test_prompt_with_input(self, monkeypatch):
        """Test prompt with user input."""
        monkeypatch.setattr("builtins.input", lambda _: "user_value")
        result = setup.prompt("Test question")
        assert result == "user_value"

    def test_prompt_required_empty(self, monkeypatch, capsys):
        """Test required prompt rejects empty input."""
        inputs = iter(["", "finally_a_value"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        result = setup.prompt("Test question", required=True)
        assert result == "finally_a_value"
        captured = capsys.readouterr()
        assert "required" in captured.out.lower()

    def test_prompt_yes_no_default_yes(self, monkeypatch):
        """Test yes/no prompt with default yes."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = setup.prompt_yes_no("Continue?", default=True)
        assert result is True

    def test_prompt_yes_no_default_no(self, monkeypatch):
        """Test yes/no prompt with default no."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = setup.prompt_yes_no("Continue?", default=False)
        assert result is False

    def test_prompt_yes_no_explicit_yes(self, monkeypatch):
        """Test yes/no prompt with explicit yes."""
        monkeypatch.setattr("builtins.input", lambda _: "yes")
        result = setup.prompt_yes_no("Continue?", default=False)
        assert result is True

    def test_prompt_yes_no_explicit_no(self, monkeypatch):
        """Test yes/no prompt with explicit no."""
        monkeypatch.setattr("builtins.input", lambda _: "no")
        result = setup.prompt_yes_no("Continue?", default=True)
        assert result is False


class TestSetupMain:
    """Tests for setup main entry point."""

    def test_help_flag(self, capsys):
        """Test --help flag shows help."""
        result = setup.main(["--help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Mother Setup Wizard" in captured.out

    def test_keyboard_interrupt(self, monkeypatch, capsys):
        """Test Ctrl+C is handled gracefully."""
        def raise_interrupt(*args, **kwargs):
            raise KeyboardInterrupt()

        with patch.object(setup, "run_setup", raise_interrupt):
            result = setup.main([])

        assert result == 130
        captured = capsys.readouterr()
        assert "cancelled" in captured.out.lower()


class TestShowSummary:
    """Tests for the summary display."""

    @pytest.fixture
    def temp_credentials_file(self, tmp_path):
        """Create a temporary credentials file with some content."""
        cred_file = tmp_path / "credentials.env"
        cred_file.write_text("ANTHROPIC_API_KEY=sk-ant-test123456789\n")
        with patch.object(credentials, "CREDENTIALS_FILE", cred_file):
            yield cred_file

    def test_show_summary(self, temp_credentials_file, capsys):
        """Test summary displays correctly."""
        setup.show_summary()
        captured = capsys.readouterr()
        assert "SETUP COMPLETE" in captured.out
        assert "ANTHROPIC_API_KEY" in captured.out
        assert "NEXT STEPS" in captured.out
