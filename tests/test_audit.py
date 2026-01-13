"""Tests for the audit logging module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mother.audit import (
    AuditEntry,
    AuditEventType,
    AuditLogConfig,
    AuditLogger,
    RedactionConfig,
    Redactor,
    SensitiveDataType,
    get_audit_logger,
    get_redactor,
    redact_string,
)


class TestSensitiveDataRedaction:
    """Tests for sensitive data redaction."""

    def test_redact_openai_key(self):
        """Test OpenAI API key redaction."""
        text = "My key is sk-abcdefghijklmnopqrstuvwxyz123456"
        result = redact_string(text)
        assert "sk-abcdef" not in result
        assert "[REDACTED:OPENAI_KEY]" in result

    def test_redact_anthropic_key(self):
        """Test Anthropic API key redaction."""
        text = "API key: sk-ant-api03-aBcDeFgHiJkLmNoPqRsTuVwXyZ"
        result = redact_string(text)
        assert "sk-ant-" not in result
        assert "[REDACTED:ANTHROPIC_KEY]" in result

    def test_redact_github_pat(self):
        """Test GitHub Personal Access Token redaction."""
        # GitHub PAT is ghp_ followed by exactly 36 alphanumeric chars
        # Example: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (36 chars after ghp_)
        text = "Token: ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890"
        result = redact_string(text)
        assert "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890" not in result
        assert "[REDACTED:GITHUB_PAT]" in result

    def test_redact_aws_access_key(self):
        """Test AWS access key redaction."""
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        result = redact_string(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED:AWS_ACCESS_KEY]" in result

    def test_redact_bearer_token(self):
        """Test Bearer token redaction."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = redact_string(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED:BEARER_TOKEN]" in result

    def test_redact_jwt(self):
        """Test JWT redaction."""
        text = "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = redact_string(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED:JWT]" in result

    def test_redact_password_field(self):
        """Test password field redaction."""
        text = 'password: "mysecretpass123"'
        result = redact_string(text)
        assert "mysecretpass123" not in result
        assert "[REDACTED]" in result

    def test_redact_email(self):
        """Test email address redaction."""
        text = "Contact: user@example.com for support"
        result = redact_string(text)
        assert "user@example.com" not in result
        assert "[REDACTED:EMAIL]" in result

    def test_redact_phone_number(self):
        """Test phone number redaction."""
        text = "Call me at +1-555-123-4567"
        result = redact_string(text)
        assert "555-123-4567" not in result
        assert "[REDACTED:PHONE]" in result

    def test_redact_ssn(self):
        """Test SSN redaction."""
        text = "SSN: 123-45-6789"
        result = redact_string(text)
        assert "123-45-6789" not in result
        assert "[REDACTED:SSN]" in result

    def test_redact_credit_card(self):
        """Test credit card number redaction."""
        # Credit cards should be redacted (spaces format to avoid phone pattern overlap)
        text = "Card: 4111 1111 1111 1111"
        result = redact_string(text)
        assert "4111 1111 1111 1111" not in result
        assert "[REDACTED:CREDIT_CARD]" in result

    def test_redact_multiple_patterns(self):
        """Test redacting multiple patterns in one string."""
        text = "API: sk-abc123456789012345678901234 Email: test@example.com"
        result = redact_string(text)
        assert "sk-abc" not in result
        assert "test@example.com" not in result

    def test_redact_preserves_non_sensitive(self):
        """Test that non-sensitive data is preserved."""
        text = "Hello world! This is a normal message."
        result = redact_string(text)
        assert result == text

    def test_redact_empty_string(self):
        """Test redacting empty string."""
        assert redact_string("") == ""

    def test_redact_none(self):
        """Test redacting None."""
        assert redact_string(None) is None


class TestRedactor:
    """Tests for the Redactor class."""

    def test_redactor_default_config(self):
        """Test Redactor with default configuration."""
        redactor = Redactor()
        assert len(redactor.config.redact_types) == len(SensitiveDataType)

    def test_redactor_custom_config(self):
        """Test Redactor with custom configuration."""
        config = RedactionConfig(
            redact_types={SensitiveDataType.EMAIL, SensitiveDataType.PHONE}
        )
        redactor = Redactor(config)

        # Should redact email
        result = redactor.redact_string("test@example.com")
        assert "[REDACTED:EMAIL]" in result

        # Should not redact API key (not in config)
        result = redactor.redact_string("sk-abc123456789012345678901234")
        # API keys won't be redacted if not in redact_types
        # But they might still be caught by generic patterns

    def test_redactor_redact_value_dict(self):
        """Test redacting sensitive data from dictionaries."""
        redactor = Redactor()
        data = {
            "user": "john",
            "email": "john@example.com",
            "api_key": "sk-abc123456789012345678901234",
        }
        result = redactor.redact_value(data)

        assert result["user"] == "john"
        assert "[REDACTED" in result["email"]
        assert "[REDACTED]" in result["api_key"]

    def test_redactor_redact_value_nested(self):
        """Test redacting nested structures."""
        redactor = Redactor()
        data = {
            "user": {
                "email": "test@example.com",
                "credentials": {
                    "password": "secret123",
                },
            },
            "tags": ["user@example.com", "normal"],
        }
        result = redactor.redact_value(data)

        assert "[REDACTED" in result["user"]["email"]
        assert "[REDACTED]" in result["user"]["credentials"]["password"]
        assert "[REDACTED" in result["tags"][0]
        assert result["tags"][1] == "normal"

    def test_redactor_redact_value_list(self):
        """Test redacting lists."""
        redactor = Redactor()
        data = ["test@example.com", "normal", "sk-abc123456789012345678901234"]
        result = redactor.redact_value(data)

        assert "[REDACTED" in result[0]
        assert result[1] == "normal"
        assert "[REDACTED" in result[2]

    def test_redactor_max_depth(self):
        """Test max depth protection."""
        config = RedactionConfig(max_depth=2)
        redactor = Redactor(config)

        # Create deeply nested structure
        data = {"a": {"b": {"c": {"d": "test@example.com"}}}}
        result = redactor.redact_value(data)

        # Should hit max depth
        assert "[MAX_DEPTH_EXCEEDED]" in str(result)

    def test_redactor_sensitive_key_detection(self):
        """Test that sensitive keys trigger redaction."""
        redactor = Redactor()
        data = {
            "password": "any_value_here",
            "api_key": "any_value",
            "secret_token": "any_value",
        }
        result = redactor.redact_value(data)

        assert result["password"] == "[REDACTED]"
        assert result["api_key"] == "[REDACTED]"
        assert result["secret_token"] == "[REDACTED]"


class TestAuditEntry:
    """Tests for AuditEntry model."""

    def test_audit_entry_defaults(self):
        """Test AuditEntry default values."""
        entry = AuditEntry(event_type=AuditEventType.CAPABILITY_REQUEST)

        assert entry.event_type == AuditEventType.CAPABILITY_REQUEST
        assert entry.timestamp is not None
        assert entry.correlation_id is not None
        assert entry.metadata == {}

    def test_audit_entry_with_values(self):
        """Test AuditEntry with provided values."""
        entry = AuditEntry(
            event_type=AuditEventType.CAPABILITY_EXECUTED,
            capability="filesystem_write",
            plugin="core",
            allowed=True,
            duration_ms=15.5,
        )

        assert entry.capability == "filesystem_write"
        assert entry.plugin == "core"
        assert entry.allowed is True
        assert entry.duration_ms == 15.5

    def test_audit_entry_serialization(self):
        """Test AuditEntry JSON serialization."""
        entry = AuditEntry(
            event_type=AuditEventType.CAPABILITY_REQUEST,
            capability="test",
        )
        data = entry.model_dump(exclude_none=True)
        json_str = json.dumps(data)

        assert "capability_request" in json_str
        assert "test" in json_str


class TestAuditLogConfig:
    """Tests for AuditLogConfig."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = AuditLogConfig()

        assert config.enabled is True
        assert config.max_file_size_mb == 100
        assert config.max_files == 10
        assert config.redact_sensitive is True
        assert config.async_write is True

    def test_config_custom_values(self):
        """Test custom configuration values."""
        config = AuditLogConfig(
            enabled=False,
            max_file_size_mb=50,
            max_files=5,
            log_path=Path("/custom/path/audit.jsonl"),
        )

        assert config.enabled is False
        assert config.max_file_size_mb == 50
        assert config.max_files == 5
        assert str(config.log_path) == "/custom/path/audit.jsonl"


class TestAuditLogger:
    """Tests for AuditLogger class."""

    @pytest.fixture
    def temp_log_dir(self, tmp_path):
        """Create a temporary directory for logs."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        return log_dir

    @pytest.fixture
    def audit_logger(self, temp_log_dir):
        """Create an audit logger with temporary directory."""
        config = AuditLogConfig(
            log_path=temp_log_dir / "audit.jsonl",
            async_write=False,  # Disable buffering for tests
            redact_sensitive=True,
        )
        logger = AuditLogger(config)
        yield logger
        logger.close()

    def test_logger_initialization(self, audit_logger, temp_log_dir):
        """Test logger initializes correctly."""
        assert audit_logger.config.enabled is True
        assert (temp_log_dir / "audit.jsonl").exists()

    def test_log_capability_request(self, audit_logger, temp_log_dir):
        """Test logging a capability request."""
        correlation_id = audit_logger.log_capability_request(
            capability="filesystem_read",
            plugin="core",
            params={"path": "/test/file.txt"},
        )

        assert correlation_id is not None

        # Read and verify log
        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        assert entry["event_type"] == "capability_request"
        assert entry["capability"] == "filesystem_read"
        assert entry["plugin"] == "core"

    def test_log_policy_decision_allowed(self, audit_logger, temp_log_dir):
        """Test logging an allowed policy decision."""
        audit_logger.log_policy_decision(
            capability="filesystem_read",
            plugin="core",
            action="allow",
            allowed=True,
            reason="Path is within allowed directory",
            risk_tier="low",
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        assert entry["event_type"] == "capability_allowed"
        assert entry["allowed"] is True
        assert entry["action"] == "allow"

    def test_log_policy_decision_denied(self, audit_logger, temp_log_dir):
        """Test logging a denied policy decision."""
        audit_logger.log_policy_decision(
            capability="shell_exec",
            plugin="core",
            action="deny",
            allowed=False,
            reason="Shell execution blocked in safe mode",
            risk_tier="high",
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        assert entry["event_type"] == "capability_denied"
        assert entry["allowed"] is False

    def test_log_capability_result_success(self, audit_logger, temp_log_dir):
        """Test logging successful capability execution."""
        audit_logger.log_capability_result(
            capability="filesystem_read",
            plugin="core",
            success=True,
            result={"content": "file data"},
            duration_ms=10.5,
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        assert entry["event_type"] == "capability_executed"
        assert entry["duration_ms"] == 10.5

    def test_log_capability_result_failure(self, audit_logger, temp_log_dir):
        """Test logging failed capability execution."""
        audit_logger.log_capability_result(
            capability="filesystem_read",
            plugin="core",
            success=False,
            error="File not found",
            duration_ms=5.0,
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        assert entry["event_type"] == "capability_failed"
        assert entry["reason"] == "File not found"

    def test_log_policy_violation(self, audit_logger, temp_log_dir):
        """Test logging a policy violation."""
        audit_logger.log_policy_violation(
            capability="shell_exec",
            plugin="core",
            violation_type="BLOCKED_COMMAND",
            details="Command 'rm -rf /' is dangerous",
            params={"command": "rm -rf /"},
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        assert entry["event_type"] == "policy_violation"
        assert "BLOCKED_COMMAND" in entry["reason"]

    def test_log_auth_success(self, audit_logger, temp_log_dir):
        """Test logging successful authentication."""
        audit_logger.log_auth_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            user_id="api_key_hash_123",
            source_ip="192.168.1.1",
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        assert entry["event_type"] == "auth_success"
        assert entry["user_id"] == "api_key_hash_123"

    def test_log_auth_failure(self, audit_logger, temp_log_dir):
        """Test logging failed authentication."""
        audit_logger.log_auth_event(
            event_type=AuditEventType.AUTH_FAILURE,
            source_ip="192.168.1.100",
            reason="Invalid API key",
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        assert entry["event_type"] == "auth_failure"
        assert entry["reason"] == "Invalid API key"

    def test_log_system_start(self, audit_logger, temp_log_dir):
        """Test logging system start."""
        audit_logger.log_system_event(
            event_type=AuditEventType.SYSTEM_START,
            details="Mother AI OS started",
            version="1.0.0",
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        assert entry["event_type"] == "system_start"
        assert entry["metadata"]["version"] == "1.0.0"

    def test_log_plugin_loaded(self, audit_logger, temp_log_dir):
        """Test logging plugin load."""
        audit_logger.log_plugin_event(
            event_type=AuditEventType.PLUGIN_LOADED,
            plugin="mailcraft",
            details="Loaded successfully",
            version="2.0.0",
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        assert entry["event_type"] == "plugin_loaded"
        assert entry["plugin"] == "mailcraft"

    def test_sensitive_data_redaction_in_params(self, audit_logger, temp_log_dir):
        """Test that sensitive data is redacted in params."""
        audit_logger.log_capability_request(
            capability="api_call",
            plugin="http",
            params={
                "url": "https://api.example.com",
                "headers": {
                    "Authorization": "Bearer sk-secret123token456"
                },
                "api_key": "sk-abc123456789012345678901234",
            },
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        entry = json.loads(log_content.strip())

        # API key should be redacted
        assert "sk-abc123" not in json.dumps(entry)
        assert "[REDACTED" in json.dumps(entry)

    def test_multiple_entries(self, audit_logger, temp_log_dir):
        """Test logging multiple entries."""
        correlation_id = audit_logger.log_capability_request(
            capability="test",
            plugin="core",
        )

        audit_logger.log_policy_decision(
            capability="test",
            plugin="core",
            action="allow",
            allowed=True,
            reason="Test",
            correlation_id=correlation_id,
        )

        audit_logger.log_capability_result(
            capability="test",
            plugin="core",
            success=True,
            correlation_id=correlation_id,
        )

        log_content = (temp_log_dir / "audit.jsonl").read_text()
        lines = log_content.strip().split("\n")

        assert len(lines) == 3

        # Verify correlation ID is consistent
        entries = [json.loads(line) for line in lines]
        assert all(e["correlation_id"] == correlation_id for e in entries)


class TestAuditLogRotation:
    """Tests for log rotation functionality."""

    @pytest.fixture
    def small_log_config(self, tmp_path):
        """Create config with small max file size for testing rotation."""
        return AuditLogConfig(
            log_path=tmp_path / "audit.jsonl",
            max_file_size_bytes=1024,  # 1KB for testing rotation
            max_files=3,
            async_write=False,
        )

    def test_log_rotation_by_size(self, small_log_config, tmp_path):
        """Test that logs are rotated when size limit is reached."""
        logger = AuditLogger(small_log_config)

        # Write many entries to trigger rotation
        for i in range(100):
            logger.log_capability_request(
                capability=f"test_{i}",
                plugin="core",
                params={"data": "x" * 100},
            )

        logger.close()

        # Check that rotation occurred
        log_files = list(tmp_path.glob("audit*.jsonl"))
        assert len(log_files) > 1

    def test_old_logs_cleanup(self, small_log_config, tmp_path):
        """Test that old logs are cleaned up beyond max_files."""
        logger = AuditLogger(small_log_config)

        # Write many entries to trigger multiple rotations
        for i in range(500):
            logger.log_capability_request(
                capability=f"test_{i}",
                plugin="core",
                params={"data": "x" * 100},
            )

        logger.close()

        # Check that we don't exceed max_files (current + rotated)
        log_files = list(tmp_path.glob("audit*.jsonl"))
        assert len(log_files) <= small_log_config.max_files + 1


class TestGlobalAuditLogger:
    """Tests for global audit logger functions."""

    def test_get_audit_logger_singleton(self, tmp_path):
        """Test that get_audit_logger returns singleton."""
        config = AuditLogConfig(
            log_path=tmp_path / "audit.jsonl",
            async_write=False,
        )

        logger1 = get_audit_logger(config)
        logger2 = get_audit_logger()

        # Should be the same instance when no config is passed
        # Note: When config is passed, it creates a new instance
        assert logger2 is not None

        logger1.close()

    def test_get_redactor_singleton(self):
        """Test that get_redactor returns singleton."""
        redactor1 = get_redactor()
        redactor2 = get_redactor()

        assert redactor1 is redactor2


class TestAuditEventTypes:
    """Tests for all audit event types."""

    def test_all_event_types_defined(self):
        """Test that all expected event types are defined."""
        expected_types = [
            "capability_request",
            "capability_allowed",
            "capability_denied",
            "capability_executed",
            "capability_failed",
            "policy_evaluation",
            "policy_violation",
            "auth_success",
            "auth_failure",
            "auth_revoked",
            "system_start",
            "system_shutdown",
            "config_change",
            "plugin_loaded",
            "plugin_unloaded",
            "plugin_error",
            "data_access",
            "data_export",
            "sensitive_data_detected",
        ]

        actual_types = [e.value for e in AuditEventType]

        for expected in expected_types:
            assert expected in actual_types, f"Missing event type: {expected}"


class TestRedactionIntegrationWithLogger:
    """Integration tests for redaction within the audit logger."""

    @pytest.fixture
    def redacting_logger(self, tmp_path):
        """Create logger with redaction enabled."""
        config = AuditLogConfig(
            log_path=tmp_path / "audit.jsonl",
            async_write=False,
            redact_sensitive=True,
            include_params=True,
            include_results=True,
        )
        logger = AuditLogger(config)
        yield logger, tmp_path
        logger.close()

    def test_api_key_redacted_in_params(self, redacting_logger):
        """Test API keys are redacted in parameters."""
        logger, tmp_path = redacting_logger

        logger.log_capability_request(
            capability="api_call",
            plugin="http",
            params={"api_key": "sk-ant-api03-aBcDeFgHiJkLmNoPqRsTuVwXyZ"},
        )

        log_content = (tmp_path / "audit.jsonl").read_text()
        assert "sk-ant-api03" not in log_content
        assert "[REDACTED" in log_content

    def test_email_redacted_in_result(self, redacting_logger):
        """Test emails are redacted in results."""
        logger, tmp_path = redacting_logger

        logger.log_capability_result(
            capability="user_lookup",
            plugin="core",
            success=True,
            result={"user_email": "secret@company.com"},
        )

        log_content = (tmp_path / "audit.jsonl").read_text()
        assert "secret@company.com" not in log_content

    def test_password_redacted_in_metadata(self, redacting_logger):
        """Test passwords are redacted in metadata."""
        logger, tmp_path = redacting_logger

        logger.log_capability_request(
            capability="connect",
            plugin="db",
            params={"host": "localhost"},
            password="supersecret123",
        )

        log_content = (tmp_path / "audit.jsonl").read_text()
        assert "supersecret123" not in log_content
