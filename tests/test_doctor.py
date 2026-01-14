"""Tests for the doctor command."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from mother.cli.doctor import (
    CheckResult,
    CheckStatus,
    DoctorReport,
    check_audit_logging,
    check_authentication,
    check_config_directory,
    check_llm_provider,
    check_multikey_mode,
    check_network_binding,
    check_policy_file,
    check_rate_limiting,
    check_safe_mode,
    check_sandbox_mode,
    check_workspace_directory,
    cmd_doctor,
    run_all_checks,
)

# Patch target for get_settings
SETTINGS_PATCH = "mother.config.settings.get_settings"


class TestCheckResult:
    """Tests for CheckResult."""

    def test_to_dict(self):
        """Test CheckResult to_dict method."""
        result = CheckResult(
            name="Test Check",
            status=CheckStatus.PASS,
            message="All good",
            details="Extra info",
        )
        d = result.to_dict()
        assert d["name"] == "Test Check"
        assert d["status"] == "pass"
        assert d["message"] == "All good"
        assert d["details"] == "Extra info"


class TestDoctorReport:
    """Tests for DoctorReport."""

    def test_empty_report(self):
        """Test empty report."""
        report = DoctorReport()
        assert report.passed == 0
        assert report.warnings == 0
        assert report.failures == 0
        assert report.is_production_ready is True

    def test_counts(self):
        """Test count properties."""
        report = DoctorReport(
            checks=[
                CheckResult("A", CheckStatus.PASS, "ok"),
                CheckResult("B", CheckStatus.PASS, "ok"),
                CheckResult("C", CheckStatus.WARN, "warning"),
                CheckResult("D", CheckStatus.FAIL, "error"),
            ]
        )
        assert report.passed == 2
        assert report.warnings == 1
        assert report.failures == 1
        assert report.is_production_ready is False

    def test_to_dict(self):
        """Test DoctorReport to_dict method."""
        report = DoctorReport(
            checks=[
                CheckResult("Test", CheckStatus.PASS, "ok"),
            ]
        )
        d = report.to_dict()
        assert "checks" in d
        assert "summary" in d
        assert d["summary"]["passed"] == 1
        assert d["summary"]["production_ready"] is True


class TestAuthenticationCheck:
    """Tests for authentication check."""

    def test_auth_disabled(self):
        """Test when authentication is disabled."""
        mock_settings = MagicMock()
        mock_settings.require_auth = False

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_authentication()
            assert result.status == CheckStatus.FAIL
            assert "DISABLED" in result.message

    def test_auth_with_api_key(self):
        """Test when API key is configured."""
        mock_settings = MagicMock()
        mock_settings.require_auth = True
        mock_settings.api_key = "test-key"

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_authentication()
            assert result.status == CheckStatus.PASS
            assert "Legacy API key" in result.message

    def test_auth_no_key(self):
        """Test when no API key is set."""
        mock_settings = MagicMock()
        mock_settings.require_auth = True
        mock_settings.api_key = None

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_authentication()
            assert result.status == CheckStatus.WARN


class TestLLMProviderCheck:
    """Tests for LLM provider check."""

    def test_no_api_key(self):
        """Test when no API key is set."""
        mock_settings = MagicMock()
        mock_settings.ai_provider = "anthropic"
        mock_settings.anthropic_api_key = None
        mock_settings.openai_api_key = None
        mock_settings.zhipu_api_key = None
        mock_settings.gemini_api_key = None

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_llm_provider()
            assert result.status == CheckStatus.FAIL
            assert "No API key" in result.message

    def test_valid_api_key(self):
        """Test with valid API key."""
        mock_settings = MagicMock()
        mock_settings.ai_provider = "anthropic"
        mock_settings.anthropic_api_key = "sk-ant-valid-api-key-1234567890"
        mock_settings.openai_api_key = None
        mock_settings.zhipu_api_key = None
        mock_settings.gemini_api_key = None
        mock_settings.llm_model = "claude-3"

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_llm_provider()
            assert result.status == CheckStatus.PASS

    def test_short_api_key(self):
        """Test with suspiciously short API key."""
        mock_settings = MagicMock()
        mock_settings.ai_provider = "openai"
        mock_settings.anthropic_api_key = None
        mock_settings.openai_api_key = "short"
        mock_settings.zhipu_api_key = None
        mock_settings.gemini_api_key = None

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_llm_provider()
            assert result.status == CheckStatus.WARN
            assert "short" in result.message.lower()


class TestSafeModeCheck:
    """Tests for safe mode check."""

    def test_safe_mode_enabled(self):
        """Test when safe mode is enabled."""
        mock_settings = MagicMock()
        mock_settings.safe_mode = True

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_safe_mode()
            assert result.status == CheckStatus.PASS

    def test_safe_mode_disabled(self):
        """Test when safe mode is disabled."""
        mock_settings = MagicMock()
        mock_settings.safe_mode = False

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_safe_mode()
            assert result.status == CheckStatus.WARN
            assert "DISABLED" in result.message


class TestSandboxModeCheck:
    """Tests for sandbox mode check."""

    def test_sandbox_enabled(self):
        """Test when sandbox mode is enabled."""
        mock_settings = MagicMock()
        mock_settings.sandbox_mode = True
        mock_settings.workspace_dir = Path("/workspace")

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_sandbox_mode()
            assert result.status == CheckStatus.PASS

    def test_sandbox_disabled(self):
        """Test when sandbox mode is disabled."""
        mock_settings = MagicMock()
        mock_settings.sandbox_mode = False

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_sandbox_mode()
            assert result.status == CheckStatus.WARN


class TestAuditLoggingCheck:
    """Tests for audit logging check."""

    def test_audit_disabled(self):
        """Test when audit logging is disabled."""
        mock_settings = MagicMock()
        mock_settings.audit_log_enabled = False

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_audit_logging()
            assert result.status == CheckStatus.WARN
            assert "DISABLED" in result.message

    def test_audit_enabled_writable(self):
        """Test when audit logging is enabled and writable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"

            mock_settings = MagicMock()
            mock_settings.audit_log_enabled = True
            mock_settings.audit_log_path = log_path

            with patch(SETTINGS_PATCH, return_value=mock_settings):
                result = check_audit_logging()
                assert result.status == CheckStatus.PASS


class TestNetworkBindingCheck:
    """Tests for network binding check."""

    def test_bound_to_all_interfaces(self):
        """Test when bound to all interfaces."""
        mock_settings = MagicMock()
        mock_settings.api_host = "0.0.0.0"
        mock_settings.api_port = 8080

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_network_binding()
            assert result.status == CheckStatus.WARN
            assert "all interfaces" in result.message

    def test_bound_to_localhost(self):
        """Test when bound to localhost."""
        mock_settings = MagicMock()
        mock_settings.api_host = "127.0.0.1"
        mock_settings.api_port = 8080

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_network_binding()
            assert result.status == CheckStatus.PASS


class TestRateLimitingCheck:
    """Tests for rate limiting check."""

    def test_rate_limiting_enabled(self):
        """Test when rate limiting is enabled."""
        result = check_rate_limiting()
        assert result.status == CheckStatus.PASS
        assert "60 RPM" in result.details


class TestRunAllChecks:
    """Tests for run_all_checks."""

    def test_returns_report(self):
        """Test that run_all_checks returns a DoctorReport."""
        report = run_all_checks()
        assert isinstance(report, DoctorReport)
        assert len(report.checks) >= 10  # Should have at least 10 checks


class TestCmdDoctor:
    """Tests for cmd_doctor command."""

    def test_json_output(self, capsys):
        """Test JSON output mode."""
        cmd_doctor(json_output=True)
        captured = capsys.readouterr()

        # Should be valid JSON
        data = json.loads(captured.out)
        assert "checks" in data
        assert "summary" in data

    def test_verbose_output(self, capsys):
        """Test verbose output mode."""
        cmd_doctor(verbose=True)
        captured = capsys.readouterr()

        # Should show details
        assert "Mother Doctor" in captured.out
        assert "Summary:" in captured.out

    def test_exit_code_success(self):
        """Test exit code when no failures."""
        # Create all passing checks
        with patch("mother.cli.doctor.run_all_checks") as mock_run:
            mock_run.return_value = DoctorReport(
                checks=[
                    CheckResult("Test", CheckStatus.PASS, "ok"),
                ]
            )
            exit_code = cmd_doctor(json_output=True)
            assert exit_code == 0

    def test_exit_code_failure(self):
        """Test exit code when failures exist."""
        with patch("mother.cli.doctor.run_all_checks") as mock_run:
            mock_run.return_value = DoctorReport(
                checks=[
                    CheckResult("Test", CheckStatus.FAIL, "error"),
                ]
            )
            exit_code = cmd_doctor(json_output=True)
            assert exit_code == 1


class TestMultikeyModeCheck:
    """Tests for multi-key mode check."""

    def test_store_not_initialized(self):
        """Test when key store doesn't exist."""
        mock_settings = MagicMock()
        mock_settings.config_dir = Path("/nonexistent/path")

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_multikey_mode()
            assert result.status == CheckStatus.WARN
            assert "not initialized" in result.message


class TestWorkspaceDirectoryCheck:
    """Tests for workspace directory check."""

    def test_workspace_accessible(self):
        """Test when workspace is accessible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_settings = MagicMock()
            mock_settings.workspace_dir = Path(tmpdir)

            with patch(SETTINGS_PATCH, return_value=mock_settings):
                result = check_workspace_directory()
                assert result.status == CheckStatus.PASS


class TestConfigDirectoryCheck:
    """Tests for config directory check."""

    def test_config_accessible(self):
        """Test when config directory is accessible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_settings = MagicMock()
            mock_settings.config_dir = Path(tmpdir)

            with patch(SETTINGS_PATCH, return_value=mock_settings):
                result = check_config_directory()
                assert result.status == CheckStatus.PASS


class TestPolicyFileCheck:
    """Tests for policy file check."""

    def test_no_policy_file(self):
        """Test when no policy file is configured."""
        mock_settings = MagicMock()
        mock_settings.policy_path = None

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_policy_file()
            assert result.status == CheckStatus.WARN
            assert "No custom policy" in result.message

    def test_policy_file_not_found(self):
        """Test when policy file doesn't exist."""
        mock_settings = MagicMock()
        mock_settings.policy_path = "/nonexistent/policy.yaml"

        with patch(SETTINGS_PATCH, return_value=mock_settings):
            result = check_policy_file()
            assert result.status == CheckStatus.FAIL
            assert "not found" in result.message
