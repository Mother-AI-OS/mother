"""Tests for the policy engine module."""

import pytest
import tempfile
from pathlib import Path

from mother.policy import (
    PolicyEngine,
    PolicyDecision,
    PolicyConfig,
    PolicyRule,
    PolicyAction,
    RiskTier,
    DataClassification,
    FilesystemCondition,
    CommandCondition,
    NetworkCondition,
    DataCondition,
    PolicyViolationError,
    get_default_policy,
    get_permissive_policy,
    load_policy,
    load_policy_from_file,
    save_policy_to_file,
    merge_policies,
    evaluate_filesystem_condition,
    evaluate_command_condition,
    evaluate_network_condition,
    evaluate_data_condition,
)


class TestPolicyDecision:
    """Tests for PolicyDecision model."""

    def test_allow(self):
        """Test creating allow decision."""
        decision = PolicyDecision.allow(reason="Test allowed")
        assert decision.allowed is True
        assert decision.action == PolicyAction.ALLOW
        assert decision.reason == "Test allowed"
        assert decision.risk_tier == RiskTier.LOW

    def test_deny(self):
        """Test creating deny decision."""
        decision = PolicyDecision.deny(
            reason="Test denied",
            matched_rules=["rule1"],
            risk_tier=RiskTier.HIGH,
        )
        assert decision.allowed is False
        assert decision.action == PolicyAction.DENY
        assert decision.reason == "Test denied"
        assert decision.matched_rules == ["rule1"]
        assert decision.risk_tier == RiskTier.HIGH

    def test_require_confirmation(self):
        """Test creating confirmation required decision."""
        decision = PolicyDecision.require_confirmation(reason="Needs confirmation")
        assert decision.allowed is True
        assert decision.action == PolicyAction.CONFIRM
        # The decision has requires_audit=True but action is CONFIRM
        assert decision.requires_audit is True

    def test_audit_action(self):
        """Test creating an audit action decision directly."""
        decision = PolicyDecision(
            allowed=True,
            action=PolicyAction.AUDIT,
            reason="Audit logging",
            requires_audit=True,
        )
        assert decision.allowed is True
        assert decision.action == PolicyAction.AUDIT
        assert decision.requires_audit is True


class TestPolicyRule:
    """Tests for PolicyRule model."""

    def test_matches_capability_exact(self):
        """Test exact capability matching."""
        rule = PolicyRule(
            name="test-rule",
            capability_pattern="shell_run_command",
            action=PolicyAction.DENY,
        )
        assert rule.matches_capability("shell_run_command") is True
        assert rule.matches_capability("shell_run_script") is False

    def test_matches_capability_regex(self):
        """Test regex capability matching."""
        rule = PolicyRule(
            name="shell-block",
            capability_pattern="shell_.*",
            action=PolicyAction.DENY,
        )
        assert rule.matches_capability("shell_run_command") is True
        assert rule.matches_capability("shell_run_script") is True
        assert rule.matches_capability("web_fetch") is False

    def test_matches_capability_complex_regex(self):
        """Test complex regex matching."""
        rule = PolicyRule(
            name="filesystem-read",
            capability_pattern="filesystem_(read|list|stat).*",
            action=PolicyAction.ALLOW,
        )
        assert rule.matches_capability("filesystem_read") is True
        assert rule.matches_capability("filesystem_list") is True
        assert rule.matches_capability("filesystem_write") is False


class TestPolicyConfig:
    """Tests for PolicyConfig model."""

    def test_get_rules_for_capability(self):
        """Test getting rules for a capability."""
        config = PolicyConfig(
            name="test",
            rules=[
                PolicyRule(
                    name="allow-read",
                    capability_pattern="filesystem_read",
                    action=PolicyAction.ALLOW,
                    priority=10,
                ),
                PolicyRule(
                    name="block-shell",
                    capability_pattern="shell_.*",
                    action=PolicyAction.DENY,
                    priority=50,
                ),
                PolicyRule(
                    name="allow-all",
                    capability_pattern=".*",
                    action=PolicyAction.ALLOW,
                    priority=0,
                ),
            ],
        )

        # Get rules for shell command
        rules = config.get_rules_for_capability("shell_run_command")
        assert len(rules) == 2
        # Higher priority first
        assert rules[0].name == "block-shell"
        assert rules[1].name == "allow-all"

    def test_rules_sorted_by_priority(self):
        """Test rules are returned sorted by priority."""
        config = PolicyConfig(
            name="test",
            rules=[
                PolicyRule(name="low", capability_pattern=".*", action=PolicyAction.ALLOW, priority=10),
                PolicyRule(name="high", capability_pattern=".*", action=PolicyAction.DENY, priority=100),
                PolicyRule(name="mid", capability_pattern=".*", action=PolicyAction.CONFIRM, priority=50),
            ],
        )

        rules = config.get_rules_for_capability("any_capability")
        assert rules[0].name == "high"
        assert rules[1].name == "mid"
        assert rules[2].name == "low"


class TestFilesystemCondition:
    """Tests for filesystem condition evaluation."""

    def test_allowed_path(self):
        """Test allowed path matches."""
        condition = FilesystemCondition(
            allowed_paths=["./workspace/**", "./data/**"],
        )

        result = evaluate_filesystem_condition(condition, "./workspace/file.txt", "read")
        assert result.allowed is True

    def test_denied_path(self):
        """Test denied path blocks."""
        condition = FilesystemCondition(
            denied_paths=["/etc/shadow", "**/.ssh/**"],
        )

        result = evaluate_filesystem_condition(condition, "/etc/shadow", "read")
        assert result.allowed is False

    def test_denied_takes_precedence(self):
        """Test denied paths take precedence over allowed."""
        condition = FilesystemCondition(
            allowed_paths=["**/*"],
            denied_paths=["**/secrets/**"],
        )

        result = evaluate_filesystem_condition(condition, "./workspace/secrets/api.key", "read")
        assert result.allowed is False

    def test_read_only_path(self):
        """Test read-only path allows read but blocks write."""
        condition = FilesystemCondition(
            read_only_paths=["/etc/**"],
        )

        read_result = evaluate_filesystem_condition(condition, "/etc/hosts", "read")
        assert read_result.allowed is True

        write_result = evaluate_filesystem_condition(condition, "/etc/hosts", "write")
        assert write_result.allowed is False


class TestCommandCondition:
    """Tests for command condition evaluation."""

    def test_allowed_command(self):
        """Test allowed command matches."""
        condition = CommandCondition(
            allowed_commands=["ls", "cat", "echo"],
        )

        result = evaluate_command_condition(condition, "ls -la", None)
        assert result.allowed is True

    def test_denied_command_regex(self):
        """Test denied command regex blocks."""
        condition = CommandCondition(
            denied_commands=["^rm\\s+-rf\\s+/"],
        )

        result = evaluate_command_condition(condition, "rm -rf /", None)
        assert result.allowed is False

    def test_denied_pattern_literal(self):
        """Test denied literal pattern blocks."""
        condition = CommandCondition(
            denied_patterns=[":(){ :|:& };:"],
        )

        result = evaluate_command_condition(condition, ":(){ :|:& };:", None)
        assert result.allowed is False

    def test_allowed_cwd(self):
        """Test allowed working directory."""
        condition = CommandCondition(
            allowed_cwd=["./workspace", "./data"],
        )

        result = evaluate_command_condition(condition, "ls", "./workspace")
        assert result.allowed is True

        result = evaluate_command_condition(condition, "ls", "/tmp")
        assert result.allowed is False


class TestNetworkCondition:
    """Tests for network condition evaluation."""

    def test_allowed_domain(self):
        """Test allowed domain matches."""
        condition = NetworkCondition(
            allowed_domains=["*.example.com", "api.service.io"],
        )

        result = evaluate_network_condition(condition, url="https://app.example.com/api")
        assert result.allowed is True

    def test_denied_domain(self):
        """Test denied domain blocks."""
        condition = NetworkCondition(
            denied_domains=["*.onion", "localhost"],
        )

        result = evaluate_network_condition(condition, url="http://localhost:8080/")
        assert result.allowed is False

    def test_blocked_private_ranges(self):
        """Test private IP range blocking."""
        condition = NetworkCondition(
            block_private_ranges=True,
        )

        result = evaluate_network_condition(condition, url="http://192.168.1.1/admin")
        assert result.allowed is False

        result = evaluate_network_condition(condition, url="http://10.0.0.1/")
        assert result.allowed is False

    def test_allowed_ports(self):
        """Test allowed ports."""
        condition = NetworkCondition(
            allowed_ports=[80, 443],
        )

        result = evaluate_network_condition(condition, url="https://example.com:443/")
        assert result.allowed is True

        result = evaluate_network_condition(condition, url="http://example.com:22/")
        assert result.allowed is False


class TestDataCondition:
    """Tests for data condition evaluation."""

    def test_sensitive_pattern_detection(self):
        """Test sensitive data pattern detection."""
        condition = DataCondition(
            block_exfiltration=True,
            sensitive_patterns=[
                "sk-[a-zA-Z0-9]{20,}",
                "(?i)api[_-]?key",
            ],
        )

        # Contains API key pattern
        result = evaluate_data_condition(
            condition,
            "My api_key is abc123",
            destination="external",
        )
        assert result.allowed is False

        # Contains Stripe-like key
        result = evaluate_data_condition(
            condition,
            "sk-abcdefghijklmnopqrstuvwxyz",
            destination="external",
        )
        assert result.allowed is False

    def test_allowed_export_domain(self):
        """Test allowed export domains."""
        condition = DataCondition(
            block_exfiltration=True,
            sensitive_patterns=["(?i)secret"],
            allowed_export_domains=["internal.company.com"],
        )

        # Sending to allowed domain should pass
        result = evaluate_data_condition(
            condition,
            "The secret code",
            destination="internal.company.com",
        )
        assert result.allowed is True

        # Sending to external domain should block
        result = evaluate_data_condition(
            condition,
            "The secret code",
            destination="external.com",
        )
        assert result.allowed is False


class TestPolicyEngine:
    """Tests for PolicyEngine class."""

    @pytest.fixture
    def safe_policy(self):
        """Create a safe mode policy."""
        return PolicyConfig(
            name="test-safe",
            safe_mode=True,
            default_action=PolicyAction.DENY,
            rules=[
                PolicyRule(
                    name="allow-read",
                    capability_pattern="filesystem_read",
                    action=PolicyAction.ALLOW,
                    priority=100,
                ),
            ],
        )

    @pytest.fixture
    def permissive_policy(self):
        """Create a permissive policy."""
        return PolicyConfig(
            name="test-permissive",
            safe_mode=False,
            default_action=PolicyAction.ALLOW,
        )

    def test_evaluate_allowed(self, permissive_policy):
        """Test evaluation returns allow."""
        engine = PolicyEngine(permissive_policy)
        decision = engine.evaluate("web_fetch", {"url": "https://example.com"})
        assert decision.allowed is True

    def test_evaluate_denied_safe_mode(self, safe_policy):
        """Test safe mode blocks high-risk capabilities."""
        engine = PolicyEngine(safe_policy)
        decision = engine.evaluate("shell_run_command", {"command": "ls"})
        assert decision.allowed is False
        assert "safe mode" in decision.reason.lower()

    def test_evaluate_allowed_by_rule(self, safe_policy):
        """Test explicit allow rule works."""
        engine = PolicyEngine(safe_policy)
        decision = engine.evaluate("filesystem_read", {"path": "/tmp/file.txt"})
        assert decision.allowed is True
        assert "allow-read" in decision.matched_rules

    def test_is_high_risk_capability(self):
        """Test high-risk capability detection."""
        engine = PolicyEngine()

        assert engine._is_high_risk_capability("shell_run_command") is True
        assert engine._is_high_risk_capability("tor_browse") is True
        assert engine._is_high_risk_capability("filesystem_delete") is True
        assert engine._is_high_risk_capability("web_fetch") is False
        assert engine._is_high_risk_capability("pdf_read") is False

    def test_is_capability_enabled(self, safe_policy):
        """Test capability enabled check."""
        engine = PolicyEngine(safe_policy)

        # filesystem_read is allowed by rule
        assert engine.is_capability_enabled("filesystem_read") is True

        # shell is blocked in safe mode
        assert engine.is_capability_enabled("shell_run_command") is False

    def test_get_allowed_capabilities(self, safe_policy):
        """Test filtering capabilities by policy."""
        engine = PolicyEngine(safe_policy)

        all_caps = [
            "filesystem_read",
            "filesystem_write",
            "shell_run_command",
            "web_fetch",
        ]

        allowed = engine.get_allowed_capabilities(all_caps)

        assert "filesystem_read" in allowed
        assert "web_fetch" in allowed
        assert "shell_run_command" not in allowed

    def test_evaluate_with_conditions(self):
        """Test evaluation with parameter conditions."""
        config = PolicyConfig(
            name="test-conditions",
            safe_mode=False,
            default_action=PolicyAction.ALLOW,
            rules=[
                PolicyRule(
                    name="block-root-rm",
                    capability_pattern="shell_run_command",
                    action=PolicyAction.DENY,
                    priority=100,
                    conditions={
                        "param.command": {"regex": "^rm\\s+-rf\\s+/"},
                    },
                ),
            ],
        )
        engine = PolicyEngine(config)

        # Safe command should be allowed
        decision = engine.evaluate("shell_run_command", {"command": "ls -la"})
        assert decision.allowed is True

        # Dangerous command should be blocked
        decision = engine.evaluate("shell_run_command", {"command": "rm -rf /"})
        assert decision.allowed is False

    def test_reload_policy(self, safe_policy, permissive_policy):
        """Test reloading policy configuration."""
        engine = PolicyEngine(safe_policy)

        # Initially blocks shell
        decision = engine.evaluate("shell_run_command", {"command": "ls"})
        assert decision.allowed is False

        # Reload with permissive policy
        engine.reload_policy(permissive_policy)

        # Now allows shell
        decision = engine.evaluate("shell_run_command", {"command": "ls"})
        assert decision.allowed is True


class TestPolicyLoader:
    """Tests for policy loading functions."""

    def test_get_default_policy(self):
        """Test getting default policy."""
        policy = get_default_policy()
        assert policy.name == "default-safe"
        assert policy.safe_mode is True
        assert policy.default_action == PolicyAction.DENY

    def test_get_permissive_policy(self):
        """Test getting permissive policy."""
        policy = get_permissive_policy()
        assert policy.safe_mode is False
        assert policy.default_action == PolicyAction.ALLOW

    def test_save_and_load_policy(self, tmp_path):
        """Test saving and loading policy from file."""
        policy = PolicyConfig(
            name="test-save",
            description="Test saving policy",
            safe_mode=True,
            rules=[
                PolicyRule(
                    name="test-rule",
                    capability_pattern="test_.*",
                    action=PolicyAction.ALLOW,
                ),
            ],
        )

        policy_path = tmp_path / "test_policy.yaml"
        save_policy_to_file(policy, policy_path)

        loaded = load_policy_from_file(policy_path)
        assert loaded.name == "test-save"
        assert loaded.safe_mode is True
        assert len(loaded.rules) == 1
        assert loaded.rules[0].name == "test-rule"

    def test_merge_policies(self):
        """Test merging two policies."""
        base = PolicyConfig(
            name="base",
            safe_mode=True,
            rules=[
                PolicyRule(name="base-rule", capability_pattern=".*", action=PolicyAction.DENY),
            ],
        )

        override = PolicyConfig(
            name="override",
            safe_mode=False,
            rules=[
                PolicyRule(name="override-rule", capability_pattern="test", action=PolicyAction.ALLOW),
            ],
        )

        merged = merge_policies(base, override)

        assert merged.name == "override"
        assert merged.safe_mode is False  # Override takes precedence
        assert len(merged.rules) == 2  # Both rules included


class TestPolicyViolationError:
    """Tests for PolicyViolationError exception."""

    def test_exception_creation(self):
        """Test creating policy violation error."""
        decision = PolicyDecision.deny(
            reason="Shell blocked",
            matched_rules=["block-shell"],
            risk_tier=RiskTier.HIGH,
        )

        error = PolicyViolationError(decision)
        assert "Shell blocked" in str(error)
        assert error.decision.allowed is False

    def test_exception_attributes(self):
        """Test exception has decision attribute."""
        decision = PolicyDecision.deny(
            reason="Test denial",
            matched_rules=["test-rule"],
        )

        error = PolicyViolationError(decision)
        assert error.decision == decision
        assert error.decision.matched_rules == ["test-rule"]


class TestPolicyEngineIntegration:
    """Integration tests for policy engine."""

    def test_filesystem_policy_integration(self):
        """Test filesystem policy with condition evaluation.

        Note: Filesystem conditions act as RESTRICTIONS only.
        The rule grants access, conditions can block it.
        """
        config = PolicyConfig(
            name="fs-test",
            safe_mode=False,
            default_action=PolicyAction.DENY,
            filesystem=FilesystemCondition(
                allowed_paths=["./workspace/**"],
                denied_paths=["**/*.key", "**/*.pem"],
            ),
            rules=[
                PolicyRule(
                    name="allow-fs-read",
                    capability_pattern="filesystem_read",
                    action=PolicyAction.ALLOW,
                    priority=100,
                ),
            ],
        )

        engine = PolicyEngine(config)

        # Read from workspace - allowed by rule
        decision = engine.evaluate("filesystem_read", {"path": "./workspace/data.txt"})
        assert decision.allowed is True

        # Read key file - allowed by rule but blocked by filesystem denied_paths
        decision = engine.evaluate("filesystem_read", {"path": "./workspace/secret.key"})
        assert decision.allowed is False

    def test_network_policy_integration(self):
        """Test network policy with condition evaluation."""
        config = PolicyConfig(
            name="net-test",
            safe_mode=False,
            default_action=PolicyAction.ALLOW,
            network=NetworkCondition(
                denied_domains=["*.onion", "localhost"],
                block_private_ranges=True,
            ),
        )

        engine = PolicyEngine(config)

        # Public URL - allowed
        decision = engine.evaluate("web_fetch", {"url": "https://api.example.com/data"})
        assert decision.allowed is True

        # Onion URL - blocked
        decision = engine.evaluate("web_fetch", {"url": "http://example.onion/hidden"})
        assert decision.allowed is False

    def test_command_policy_integration(self):
        """Test command policy with condition evaluation."""
        config = PolicyConfig(
            name="cmd-test",
            safe_mode=False,
            default_action=PolicyAction.ALLOW,
            commands=CommandCondition(
                denied_commands=[
                    "^rm\\s+-rf\\s+/",
                    "^sudo\\s+",
                ],
                denied_patterns=[
                    ":(){ :|:& };:",
                ],
            ),
        )

        engine = PolicyEngine(config)

        # Safe command - allowed
        decision = engine.evaluate("shell_run_command", {"command": "ls -la /tmp"})
        assert decision.allowed is True

        # Dangerous rm - blocked
        decision = engine.evaluate("shell_run_command", {"command": "rm -rf /"})
        assert decision.allowed is False

        # sudo - blocked
        decision = engine.evaluate("shell_run_command", {"command": "sudo apt update"})
        assert decision.allowed is False


class TestSafeModeEnvironmentOverride:
    """Tests for MOTHER_SAFE_MODE environment variable override."""

    def test_safe_mode_enabled_by_default(self, monkeypatch):
        """Test safe mode is enabled by default when no env var is set."""
        monkeypatch.delenv("MOTHER_SAFE_MODE", raising=False)
        policy = get_default_policy()
        assert policy.safe_mode is True

    def test_safe_mode_env_override_enable(self, monkeypatch):
        """Test MOTHER_SAFE_MODE=1 enables safe mode."""
        monkeypatch.setenv("MOTHER_SAFE_MODE", "1")

        # Create a permissive policy (safe_mode=False)
        config = PolicyConfig(name="test", safe_mode=False)

        # Apply env overrides should enable safe mode
        from mother.policy.loader import apply_env_overrides
        result = apply_env_overrides(config)

        assert result.safe_mode is True

    def test_safe_mode_env_override_disable(self, monkeypatch):
        """Test MOTHER_SAFE_MODE=0 disables safe mode."""
        monkeypatch.setenv("MOTHER_SAFE_MODE", "0")

        # Create a safe policy (safe_mode=True)
        config = PolicyConfig(name="test", safe_mode=True)

        # Apply env overrides should disable safe mode
        from mother.policy.loader import apply_env_overrides
        result = apply_env_overrides(config)

        assert result.safe_mode is False

    def test_safe_mode_env_override_false_string(self, monkeypatch):
        """Test MOTHER_SAFE_MODE=false disables safe mode."""
        monkeypatch.setenv("MOTHER_SAFE_MODE", "false")

        config = PolicyConfig(name="test", safe_mode=True)
        from mother.policy.loader import apply_env_overrides
        result = apply_env_overrides(config)

        assert result.safe_mode is False

    def test_safe_mode_env_override_no_string(self, monkeypatch):
        """Test MOTHER_SAFE_MODE=no disables safe mode."""
        monkeypatch.setenv("MOTHER_SAFE_MODE", "no")

        config = PolicyConfig(name="test", safe_mode=True)
        from mother.policy.loader import apply_env_overrides
        result = apply_env_overrides(config)

        assert result.safe_mode is False

    def test_safe_mode_env_override_true_string(self, monkeypatch):
        """Test MOTHER_SAFE_MODE=true enables safe mode."""
        monkeypatch.setenv("MOTHER_SAFE_MODE", "true")

        config = PolicyConfig(name="test", safe_mode=False)
        from mother.policy.loader import apply_env_overrides
        result = apply_env_overrides(config)

        assert result.safe_mode is True

    def test_safe_mode_env_no_change_when_same(self, monkeypatch):
        """Test env override doesn't modify when value is the same."""
        monkeypatch.setenv("MOTHER_SAFE_MODE", "1")

        config = PolicyConfig(name="test", safe_mode=True)
        from mother.policy.loader import apply_env_overrides
        result = apply_env_overrides(config)

        assert result.safe_mode is True
        assert result.name == "test"

    def test_load_policy_applies_env_override(self, monkeypatch, tmp_path):
        """Test load_policy() applies environment overrides."""
        # Create a policy file with safe_mode=False
        policy_file = tmp_path / "test_policy.yaml"
        policy_file.write_text("""
name: dev-policy
safe_mode: false
default_action: allow
""")
        monkeypatch.setenv("MOTHER_POLICY_PATH", str(policy_file))
        monkeypatch.setenv("MOTHER_SAFE_MODE", "1")  # Override to enable

        from mother.policy.loader import load_policy
        policy = load_policy()

        # Even though file says safe_mode=false, env overrides to true
        assert policy.safe_mode is True
        assert policy.name == "dev-policy"


class TestSafeModeRestrictions:
    """Tests for safe mode capability restrictions."""

    def test_safe_mode_blocks_shell(self):
        """Test safe mode blocks shell execution."""
        policy = get_default_policy()
        engine = PolicyEngine(policy)

        decision = engine.evaluate("shell_run_command", {"command": "ls"})
        assert decision.allowed is False
        assert "safe mode" in decision.reason.lower()

    def test_safe_mode_blocks_tor(self):
        """Test safe mode blocks Tor capabilities."""
        policy = get_default_policy()
        engine = PolicyEngine(policy)

        decision = engine.evaluate("tor_browse", {"url": "http://example.onion"})
        assert decision.allowed is False

    def test_safe_mode_blocks_delete(self):
        """Test safe mode blocks delete operations."""
        policy = get_default_policy()
        engine = PolicyEngine(policy)

        decision = engine.evaluate("filesystem_delete", {"path": "/tmp/file"})
        assert decision.allowed is False

    def test_safe_mode_allows_with_explicit_rule(self):
        """Test safe mode allows capabilities with explicit allow rule."""
        policy = PolicyConfig(
            name="test-safe-with-rule",
            safe_mode=True,
            rules=[
                PolicyRule(
                    name="allow-ls",
                    capability_pattern="shell_run_command",
                    action=PolicyAction.ALLOW,
                    priority=100,
                    conditions={"param.command": {"regex": "^ls"}},
                ),
            ],
        )
        engine = PolicyEngine(policy)

        # ls command should be allowed
        decision = engine.evaluate("shell_run_command", {"command": "ls -la"})
        assert decision.allowed is True

        # rm command should still be blocked (no matching allow rule)
        decision = engine.evaluate("shell_run_command", {"command": "rm -rf /"})
        assert decision.allowed is False

    def test_safe_mode_default_deny(self):
        """Test default policy has default_action=deny."""
        policy = get_default_policy()
        assert policy.default_action == PolicyAction.DENY

    def test_safe_mode_blocks_network_egress(self):
        """Test default safe policy blocks network egress."""
        policy = get_default_policy()
        engine = PolicyEngine(policy)

        # Web fetch should be blocked
        decision = engine.evaluate("web_fetch", {"url": "https://example.com"})
        # In safe mode, web_fetch is not high-risk, but network conditions block it
        # The network condition blocks all domains
        assert decision.allowed is False
