"""Tests for the tool policy module."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
import yaml

from mother.tools.exceptions import ToolPolicyViolationError
from mother.tools.policy import (
    ToolPolicyAction,
    ToolPolicyConfig,
    ToolPolicyDecision,
    ToolPolicyEngine,
    load_tool_policy,
)
from mother.tools.tool_manifest import RiskLevel


class TestToolPolicyConfig:
    """Tests for ToolPolicyConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ToolPolicyConfig()

        assert config.enabled is True
        assert config.default_action == ToolPolicyAction.CONFIRM
        assert config.risk_rules["low"] == ToolPolicyAction.ALLOW
        assert config.risk_rules["medium"] == ToolPolicyAction.CONFIRM
        assert config.risk_rules["high"] == ToolPolicyAction.CONFIRM
        assert config.risk_rules["critical"] == ToolPolicyAction.DENY

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "enabled": False,
            "default_action": "deny",
            "risk_rules": {
                "low": "allow",
                "medium": "allow",
                "high": "confirm",
                "critical": "deny",
            },
            "blocked_tools": ["dangerous-tool"],
            "allowed_tools": ["trusted-tool"],
        }

        config = ToolPolicyConfig.from_dict(data)

        assert config.enabled is False
        assert config.default_action == ToolPolicyAction.DENY
        assert config.risk_rules["low"] == ToolPolicyAction.ALLOW
        assert config.risk_rules["medium"] == ToolPolicyAction.ALLOW
        assert "dangerous-tool" in config.blocked_tools
        assert "trusted-tool" in config.allowed_tools

    def test_to_dict(self):
        """Test serializing config to dictionary."""
        config = ToolPolicyConfig(
            enabled=True,
            blocked_tools=["bad-tool"],
        )

        data = config.to_dict()

        assert data["enabled"] is True
        assert "bad-tool" in data["blocked_tools"]
        assert data["default_action"] == "confirm"


class TestToolPolicyDecision:
    """Tests for ToolPolicyDecision."""

    def test_allow(self):
        """Test creating allow decision."""
        decision = ToolPolicyDecision.allow("Allowed by policy")

        assert decision.allowed is True
        assert decision.action == ToolPolicyAction.ALLOW
        assert decision.requires_confirmation is False

    def test_deny(self):
        """Test creating deny decision."""
        decision = ToolPolicyDecision.deny("Blocked by policy", tool_name="test")

        assert decision.allowed is False
        assert decision.action == ToolPolicyAction.DENY
        assert decision.tool_name == "test"

    def test_require_confirmation(self):
        """Test creating confirmation decision."""
        decision = ToolPolicyDecision.require_confirmation(
            "Needs confirmation",
            risk_level="high",
        )

        assert decision.allowed is True
        assert decision.action == ToolPolicyAction.CONFIRM
        assert decision.requires_confirmation is True
        assert decision.risk_level == "high"


class TestToolPolicyEngine:
    """Tests for ToolPolicyEngine."""

    def test_evaluate_install_low_risk(self):
        """Test evaluating low-risk tool installation."""
        engine = ToolPolicyEngine()
        decision = engine.evaluate_install("my-tool", "low")

        assert decision.allowed is True
        assert decision.action == ToolPolicyAction.ALLOW
        assert not decision.requires_confirmation

    def test_evaluate_install_medium_risk(self):
        """Test evaluating medium-risk tool installation."""
        engine = ToolPolicyEngine()
        decision = engine.evaluate_install("my-tool", "medium")

        assert decision.allowed is True
        assert decision.action == ToolPolicyAction.CONFIRM
        assert decision.requires_confirmation is True

    def test_evaluate_install_high_risk(self):
        """Test evaluating high-risk tool installation."""
        engine = ToolPolicyEngine()
        decision = engine.evaluate_install("my-tool", "high")

        assert decision.allowed is True
        assert decision.action == ToolPolicyAction.CONFIRM
        assert decision.requires_confirmation is True

    def test_evaluate_install_critical_risk(self):
        """Test evaluating critical-risk tool installation."""
        engine = ToolPolicyEngine()
        decision = engine.evaluate_install("my-tool", "critical")

        assert decision.allowed is False
        assert decision.action == ToolPolicyAction.DENY

    def test_evaluate_install_blocked_tool(self):
        """Test evaluating blocked tool installation."""
        config = ToolPolicyConfig(blocked_tools=["blocked-tool"])
        engine = ToolPolicyEngine(config)
        decision = engine.evaluate_install("blocked-tool", "low")

        assert decision.allowed is False
        assert "blocked" in decision.reason.lower()

    def test_evaluate_install_allowed_tool(self):
        """Test evaluating explicitly allowed tool installation."""
        config = ToolPolicyConfig(allowed_tools=["special-tool"])
        engine = ToolPolicyEngine(config)
        # Even with high risk, explicitly allowed tools are permitted
        decision = engine.evaluate_install("special-tool", "high")

        assert decision.allowed is True
        assert decision.action == ToolPolicyAction.ALLOW
        assert "explicitly allowed" in decision.reason.lower()

    def test_evaluate_install_disabled_policy(self):
        """Test evaluating with disabled policy."""
        config = ToolPolicyConfig(enabled=False)
        engine = ToolPolicyEngine(config)
        decision = engine.evaluate_install("any-tool", "critical")

        assert decision.allowed is True
        assert "disabled" in decision.reason.lower()

    def test_evaluate_install_risk_level_enum(self):
        """Test evaluating with RiskLevel enum."""
        engine = ToolPolicyEngine()
        decision = engine.evaluate_install("my-tool", RiskLevel.LOW)

        assert decision.allowed is True
        assert decision.action == ToolPolicyAction.ALLOW

    def test_check_install_allowed(self):
        """Test check_install for allowed tool."""
        engine = ToolPolicyEngine()
        # Should not raise
        engine.check_install("my-tool", "low")

    def test_check_install_denied(self):
        """Test check_install for denied tool."""
        engine = ToolPolicyEngine()

        with pytest.raises(ToolPolicyViolationError):
            engine.check_install("my-tool", "critical")

    def test_check_install_confirmation_not_given(self):
        """Test check_install when confirmation is required but not given."""
        engine = ToolPolicyEngine()

        with pytest.raises(ToolPolicyViolationError) as exc_info:
            engine.check_install("my-tool", "high", confirmed=False)
        assert "--yes" in str(exc_info.value)

    def test_check_install_confirmation_given(self):
        """Test check_install when confirmation is given."""
        engine = ToolPolicyEngine()
        # Should not raise
        engine.check_install("my-tool", "high", confirmed=True)

    def test_custom_risk_rules(self):
        """Test with custom risk rules."""
        config = ToolPolicyConfig(
            risk_rules={
                "low": ToolPolicyAction.CONFIRM,
                "medium": ToolPolicyAction.DENY,
                "high": ToolPolicyAction.DENY,
                "critical": ToolPolicyAction.DENY,
            }
        )
        engine = ToolPolicyEngine(config)

        low_decision = engine.evaluate_install("my-tool", "low")
        assert low_decision.requires_confirmation is True

        medium_decision = engine.evaluate_install("my-tool", "medium")
        assert medium_decision.allowed is False


class TestLoadToolPolicy:
    """Tests for load_tool_policy function."""

    def test_load_from_file(self):
        """Test loading policy from file."""
        policy_data = {
            "enabled": True,
            "default_action": "deny",
            "blocked_tools": ["test-blocked"],
        }

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(policy_data, f)
            f.flush()

            config = load_tool_policy(f.name)

            assert config.enabled is True
            assert config.default_action == ToolPolicyAction.DENY
            assert "test-blocked" in config.blocked_tools

    def test_load_nonexistent_returns_default(self):
        """Test that loading nonexistent file returns default config."""
        config = load_tool_policy("/nonexistent/path/policy.yaml")

        assert config.enabled is True
        assert config.default_action == ToolPolicyAction.CONFIRM

    def test_load_empty_file(self):
        """Test loading empty file."""
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()

            config = load_tool_policy(f.name)

            # Should return default config
            assert config.enabled is True
