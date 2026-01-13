"""Tests for Tor and Tor-shell plugin policy coverage.

This module provides comprehensive test coverage for:
1. Safe mode HARD-GATE blocking of Tor/Tor-shell capabilities by default
2. Explicit policy ALLOW enabling Tor/Tor-shell execution paths
3. Offline testing with no real Tor daemon or network calls
4. Regression protection for policy gating behavior

All tests are designed to run offline in CI without a Tor daemon.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mother.plugins.base import PluginResult, ResultStatus
from mother.plugins.builtin.tor import TorPlugin, _create_manifest as create_tor_manifest
from mother.plugins.builtin.tor_shell import (
    TorShellPlugin,
    _create_manifest as create_tor_shell_manifest,
)
from mother.policy import (
    NetworkCondition,
    PolicyAction,
    PolicyConfig,
    PolicyDecision,
    PolicyEngine,
    PolicyRule,
    RiskTier,
    get_default_policy,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def safe_mode_policy() -> PolicyConfig:
    """Create a safe mode policy with no explicit allow rules for Tor."""
    return PolicyConfig(
        name="test-safe-mode",
        version="1.0",
        safe_mode=True,
        default_action=PolicyAction.DENY,
        rules=[],
    )


@pytest.fixture
def safe_mode_policy_with_tor_allow() -> PolicyConfig:
    """Create a safe mode policy WITH explicit allow for tor_fetch.

    Note: This also configures network conditions to allow .onion domains,
    since both the safe-mode check AND network conditions must pass.
    """
    return PolicyConfig(
        name="test-safe-with-tor-allow",
        version="1.0",
        safe_mode=True,
        default_action=PolicyAction.DENY,
        # Configure network to allow .onion domains for Tor
        network=NetworkCondition(
            allowed_domains=["*.onion"],
            denied_domains=[],  # Clear default denial
        ),
        rules=[
            PolicyRule(
                name="allow-tor-fetch",
                capability_pattern="tor_fetch",
                action=PolicyAction.ALLOW,
                priority=100,
                description="Explicitly allow tor_fetch capability",
            ),
        ],
    )


@pytest.fixture
def safe_mode_policy_with_tor_shell_allow() -> PolicyConfig:
    """Create a safe mode policy WITH explicit allow for tor-shell capabilities."""
    return PolicyConfig(
        name="test-safe-with-tor-shell-allow",
        version="1.0",
        safe_mode=True,
        default_action=PolicyAction.DENY,
        rules=[
            PolicyRule(
                name="allow-tor-shell-dw",
                capability_pattern="tor-shell_darknet_dw",
                action=PolicyAction.ALLOW,
                priority=100,
                description="Explicitly allow tor-shell_darknet_dw capability",
            ),
        ],
    )


@pytest.fixture
def tor_plugin() -> TorPlugin:
    """Create a TorPlugin instance for testing."""
    return TorPlugin()


@pytest.fixture
def tor_shell_plugin() -> TorShellPlugin:
    """Create a TorShellPlugin instance for testing."""
    return TorShellPlugin()


# =============================================================================
# Test A: Safe-mode blocks Tor at policy layer (no execution)
# =============================================================================


class TestSafeModeBlocksTor:
    """Tests that verify safe mode HARD-GATE blocks Tor capabilities by default."""

    def test_policy_engine_identifies_tor_as_high_risk(self) -> None:
        """Test that the policy engine correctly identifies tor_* capabilities as high-risk."""
        engine = PolicyEngine()

        # All tor_* capabilities should be identified as high-risk
        assert engine._is_high_risk_capability("tor_fetch") is True
        assert engine._is_high_risk_capability("tor_browse") is True
        assert engine._is_high_risk_capability("tor_check_status") is True
        assert engine._is_high_risk_capability("tor_start") is True
        assert engine._is_high_risk_capability("tor_stop") is True
        assert engine._is_high_risk_capability("tor_new_identity") is True
        assert engine._is_high_risk_capability("tor_verified_sites") is True
        assert engine._is_high_risk_capability("darknet_bbc") is False  # Not prefixed with tor_

    def test_safe_mode_denies_tor_fetch_no_allow_rule(
        self, safe_mode_policy: PolicyConfig
    ) -> None:
        """Test that safe mode DENIES tor_fetch when no explicit allow rule exists."""
        engine = PolicyEngine(safe_mode_policy)

        decision = engine.evaluate("tor_fetch", {"url": "http://example.onion"})

        assert decision.allowed is False
        assert decision.action == PolicyAction.DENY
        assert "safe mode" in decision.reason.lower()
        assert decision.risk_tier == RiskTier.HIGH
        assert "safe_mode" in decision.matched_rules

    def test_safe_mode_denies_tor_browse_no_allow_rule(
        self, safe_mode_policy: PolicyConfig
    ) -> None:
        """Test that safe mode DENIES tor_browse when no explicit allow rule exists."""
        engine = PolicyEngine(safe_mode_policy)

        decision = engine.evaluate("tor_browse", {"url": "http://example.onion"})

        assert decision.allowed is False
        assert "safe mode" in decision.reason.lower()

    def test_safe_mode_denies_tor_start(self, safe_mode_policy: PolicyConfig) -> None:
        """Test that safe mode DENIES tor_start (service control)."""
        engine = PolicyEngine(safe_mode_policy)

        decision = engine.evaluate("tor_start", {})

        assert decision.allowed is False
        assert "safe mode" in decision.reason.lower()

    def test_safe_mode_denies_tor_new_identity(
        self, safe_mode_policy: PolicyConfig
    ) -> None:
        """Test that safe mode DENIES tor_new_identity."""
        engine = PolicyEngine(safe_mode_policy)

        decision = engine.evaluate("tor_new_identity", {})

        assert decision.allowed is False
        assert "safe mode" in decision.reason.lower()

    def test_default_policy_blocks_tor(self) -> None:
        """Test that the DEFAULT policy blocks all tor capabilities."""
        policy = get_default_policy()
        engine = PolicyEngine(policy)

        # All tor capabilities should be blocked by default safe policy
        for capability in [
            "tor_fetch",
            "tor_browse",
            "tor_start",
            "tor_stop",
            "tor_check_status",
            "tor_new_identity",
            "tor_verified_sites",
        ]:
            decision = engine.evaluate(capability, {})
            assert decision.allowed is False, f"{capability} should be blocked"

    def test_is_capability_enabled_returns_false_for_tor(
        self, safe_mode_policy: PolicyConfig
    ) -> None:
        """Test is_capability_enabled returns False for tor capabilities in safe mode."""
        engine = PolicyEngine(safe_mode_policy)

        assert engine.is_capability_enabled("tor_fetch") is False
        assert engine.is_capability_enabled("tor_browse") is False
        assert engine.is_capability_enabled("tor_start") is False

    def test_get_allowed_capabilities_filters_tor(
        self, safe_mode_policy: PolicyConfig
    ) -> None:
        """Test that get_allowed_capabilities filters out tor capabilities."""
        engine = PolicyEngine(safe_mode_policy)

        all_caps = [
            "filesystem_read",
            "web_fetch",
            "tor_fetch",
            "tor_browse",
            "email_send",
        ]

        allowed = engine.get_allowed_capabilities(all_caps)

        assert "tor_fetch" not in allowed
        assert "tor_browse" not in allowed
        # Non-high-risk capabilities should pass
        assert "filesystem_read" in allowed


# =============================================================================
# Test B: Safe-mode blocks Tor-shell at policy layer
# =============================================================================


class TestSafeModeBlocksTorShell:
    """Tests that verify safe mode HARD-GATE blocks Tor-shell capabilities by default."""

    def test_policy_engine_identifies_tor_shell_as_high_risk(self) -> None:
        """Test that the policy engine identifies tor-shell_* capabilities as high-risk."""
        engine = PolicyEngine()

        # All tor-shell_* capabilities should be identified as high-risk
        assert engine._is_high_risk_capability("tor-shell_darknet_dw") is True
        assert engine._is_high_risk_capability("tor-shell_darknet_voa") is True
        assert engine._is_high_risk_capability("tor-shell_darknet_rferl") is True
        assert engine._is_high_risk_capability("tor-shell_darknet_bellingcat") is True
        assert engine._is_high_risk_capability("tor-shell_darknet_propublica") is True
        assert engine._is_high_risk_capability("tor-shell_darknet_nyt") is True
        assert engine._is_high_risk_capability("tor-shell_darknet_bookmarks") is True
        assert engine._is_high_risk_capability("tor-shell_darknet_news") is True

    def test_safe_mode_denies_tor_shell_dw(
        self, safe_mode_policy: PolicyConfig
    ) -> None:
        """Test that safe mode DENIES tor-shell_darknet_dw."""
        engine = PolicyEngine(safe_mode_policy)

        decision = engine.evaluate("tor-shell_darknet_dw", {})

        assert decision.allowed is False
        assert "safe mode" in decision.reason.lower()
        assert decision.risk_tier == RiskTier.HIGH

    def test_safe_mode_denies_all_tor_shell_capabilities(
        self, safe_mode_policy: PolicyConfig
    ) -> None:
        """Test that safe mode DENIES all tor-shell capabilities."""
        engine = PolicyEngine(safe_mode_policy)

        tor_shell_caps = [
            "tor-shell_darknet_dw",
            "tor-shell_darknet_voa",
            "tor-shell_darknet_rferl",
            "tor-shell_darknet_bellingcat",
            "tor-shell_darknet_propublica",
            "tor-shell_darknet_nyt",
            "tor-shell_darknet_bookmarks",
            "tor-shell_darknet_news",
        ]

        for capability in tor_shell_caps:
            decision = engine.evaluate(capability, {})
            assert decision.allowed is False, f"{capability} should be blocked"
            assert "safe mode" in decision.reason.lower()

    def test_default_policy_blocks_tor_shell(self) -> None:
        """Test that the DEFAULT policy blocks all tor-shell capabilities."""
        policy = get_default_policy()
        engine = PolicyEngine(policy)

        decision = engine.evaluate("tor-shell_darknet_dw", {})
        assert decision.allowed is False

    def test_is_capability_enabled_returns_false_for_tor_shell(
        self, safe_mode_policy: PolicyConfig
    ) -> None:
        """Test is_capability_enabled returns False for tor-shell capabilities."""
        engine = PolicyEngine(safe_mode_policy)

        assert engine.is_capability_enabled("tor-shell_darknet_dw") is False
        assert engine.is_capability_enabled("tor-shell_darknet_nyt") is False


# =============================================================================
# Test C: Explicit policy allow enables Tor capability path (offline)
# =============================================================================


class TestExplicitAllowEnablesTor:
    """Tests that verify explicit ALLOW rules enable Tor execution paths."""

    def test_explicit_allow_rule_allows_tor_fetch(
        self, safe_mode_policy_with_tor_allow: PolicyConfig
    ) -> None:
        """Test that explicit ALLOW rule permits tor_fetch even in safe mode."""
        engine = PolicyEngine(safe_mode_policy_with_tor_allow)

        decision = engine.evaluate("tor_fetch", {"url": "http://example.onion"})

        assert decision.allowed is True
        assert decision.action == PolicyAction.ALLOW
        assert "allow-tor-fetch" in decision.matched_rules

    def test_explicit_allow_does_not_affect_other_tor_caps(
        self, safe_mode_policy_with_tor_allow: PolicyConfig
    ) -> None:
        """Test that allowing tor_fetch doesn't allow tor_browse."""
        engine = PolicyEngine(safe_mode_policy_with_tor_allow)

        # tor_fetch is allowed
        fetch_decision = engine.evaluate("tor_fetch", {"url": "http://example.onion"})
        assert fetch_decision.allowed is True

        # tor_browse is still blocked (no allow rule for it)
        browse_decision = engine.evaluate("tor_browse", {"url": "http://example.onion"})
        assert browse_decision.allowed is False

    @pytest.mark.asyncio
    async def test_tor_fetch_execution_with_mocked_network(
        self, tor_plugin: TorPlugin
    ) -> None:
        """Test tor_fetch execution with monkeypatched network call.

        This test verifies the execution path works when policy allows,
        without making real network calls.
        """
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Stubbed Tor content</html>"
        mock_response.content = b"<html>Stubbed Tor content</html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "http://example.onion"
        mock_response.encoding = "utf-8"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tor_plugin.execute("tor_fetch", {"url": "http://example.onion"})

        assert result.success is True
        assert result.data is not None
        assert result.data["status_code"] == 200
        assert "Stubbed Tor content" in result.data["content"]
        # Verify no real network call was made - the mock was used
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_tor_verified_sites_no_network_required(
        self, tor_plugin: TorPlugin
    ) -> None:
        """Test tor_verified_sites returns data without network calls."""
        # This capability returns static data and doesn't need network access
        result = await tor_plugin.execute("tor_verified_sites", {})

        assert result.success is True
        assert result.data is not None
        assert "news" in result.data
        assert "search" in result.data
        # Verify it contains expected sites
        news_sites = result.data["news"]
        site_names = [s["name"] for s in news_sites]
        assert "BBC News" in site_names
        assert "The New York Times" in site_names


# =============================================================================
# Test D: Explicit policy allow enables Tor-shell capability path (offline)
# =============================================================================


class TestExplicitAllowEnablesTorShell:
    """Tests that verify explicit ALLOW rules enable Tor-shell execution paths."""

    def test_explicit_allow_rule_allows_tor_shell_dw(
        self, safe_mode_policy_with_tor_shell_allow: PolicyConfig
    ) -> None:
        """Test that explicit ALLOW rule permits tor-shell_darknet_dw."""
        engine = PolicyEngine(safe_mode_policy_with_tor_shell_allow)

        decision = engine.evaluate("tor-shell_darknet_dw", {})

        assert decision.allowed is True
        assert decision.action == PolicyAction.ALLOW
        assert "allow-tor-shell-dw" in decision.matched_rules

    def test_explicit_allow_does_not_affect_other_tor_shell_caps(
        self, safe_mode_policy_with_tor_shell_allow: PolicyConfig
    ) -> None:
        """Test that allowing darknet_dw doesn't allow darknet_voa."""
        engine = PolicyEngine(safe_mode_policy_with_tor_shell_allow)

        # darknet_dw is allowed
        dw_decision = engine.evaluate("tor-shell_darknet_dw", {})
        assert dw_decision.allowed is True

        # darknet_voa is still blocked (no allow rule for it)
        voa_decision = engine.evaluate("tor-shell_darknet_voa", {})
        assert voa_decision.allowed is False

    @pytest.mark.asyncio
    async def test_tor_shell_dw_execution_with_mocked_subprocess(
        self, tor_shell_plugin: TorShellPlugin
    ) -> None:
        """Test tor-shell darknet_dw execution with monkeypatched subprocess.

        This test verifies the execution path works when policy allows,
        without spawning real processes.
        """
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"Stubbed Deutsche Welle content from Tor", b"")
        )
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = await tor_shell_plugin.execute("darknet_dw", {})

        assert result.success is True
        assert result.data is not None
        assert result.data["site"] == "Deutsche Welle"
        assert result.data["site_key"] == "dw"
        assert "Stubbed Deutsche Welle content" in result.data["content"]
        # Verify subprocess was called but not a real process
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args
        assert call_args[0][0] == "torsocks"  # First arg is torsocks
        assert call_args[0][1] == "w3m"  # Second arg is w3m browser

    @pytest.mark.asyncio
    async def test_tor_shell_bookmarks_no_subprocess_required(
        self, tor_shell_plugin: TorShellPlugin
    ) -> None:
        """Test darknet_bookmarks returns data without subprocess calls."""
        # This capability returns static data and doesn't need subprocess access
        result = await tor_shell_plugin.execute("darknet_bookmarks", {})

        assert result.success is True
        assert result.data is not None
        assert "search_engines" in result.data
        assert "news_sites" in result.data
        # Verify raw output format
        assert result.raw_output is not None
        assert "Darknet Bookmarks" in result.raw_output

    @pytest.mark.asyncio
    async def test_tor_shell_news_no_subprocess_required(
        self, tor_shell_plugin: TorShellPlugin
    ) -> None:
        """Test darknet_news returns data without subprocess calls."""
        result = await tor_shell_plugin.execute("darknet_news", {})

        assert result.success is True
        assert result.data is not None
        assert "sites" in result.data
        assert len(result.data["sites"]) > 0
        # All sites should be verified
        for site in result.data["sites"]:
            assert site["verified"] is True


# =============================================================================
# Test E: Registry exposes Tor/Tor-shell as high-risk/disabled-by-default
# =============================================================================


class TestTorPluginsHighRiskClassification:
    """Tests that verify Tor plugins are properly classified as high-risk."""

    def test_tor_manifest_has_network_permissions(self) -> None:
        """Test Tor plugin manifest declares network permissions."""
        manifest = create_tor_manifest()

        assert "tor:read" in manifest.permissions
        assert "tor:write" in manifest.permissions
        assert "network:proxy" in manifest.permissions

    def test_tor_shell_manifest_has_shell_permissions(self) -> None:
        """Test Tor-shell plugin manifest declares shell execution permissions."""
        manifest = create_tor_shell_manifest()

        assert "shell:execute" in manifest.permissions
        assert "tor:read" in manifest.permissions

    def test_tor_capabilities_exist_in_manifest(self) -> None:
        """Test Tor plugin manifest exposes expected capabilities."""
        manifest = create_tor_manifest()
        cap_names = [c.name for c in manifest.capabilities]

        expected_caps = [
            "tor_check_status",
            "tor_fetch",
            "tor_browse",
            "tor_start",
            "tor_stop",
            "tor_new_identity",
            "tor_verified_sites",
            "darknet_bbc",
            "darknet_cia",
            "darknet_ddg",
        ]

        for cap in expected_caps:
            assert cap in cap_names, f"Capability {cap} should exist"

    def test_tor_shell_capabilities_exist_in_manifest(self) -> None:
        """Test Tor-shell plugin manifest exposes expected capabilities."""
        manifest = create_tor_shell_manifest()
        cap_names = [c.name for c in manifest.capabilities]

        expected_caps = [
            "darknet_dw",
            "darknet_voa",
            "darknet_rferl",
            "darknet_bellingcat",
            "darknet_propublica",
            "darknet_nyt",
            "darknet_bookmarks",
            "darknet_news",
        ]

        for cap in expected_caps:
            assert cap in cap_names, f"Capability {cap} should exist"

    def test_tor_capabilities_confirmation_required(self) -> None:
        """Test high-impact Tor capabilities require confirmation."""
        manifest = create_tor_manifest()
        cap_by_name = {c.name: c for c in manifest.capabilities}

        # Service control capabilities should require confirmation
        assert cap_by_name["tor_start"].confirmation_required is True
        assert cap_by_name["tor_stop"].confirmation_required is True

    def test_policy_engine_patterns_match_tor_plugins(self) -> None:
        """Test that policy engine regex patterns correctly match Tor plugin names."""
        engine = PolicyEngine()

        # Test the actual capability names that would come from registry
        # tor plugin: capabilities are named tor_* (no prefix needed)
        assert engine._is_high_risk_capability("tor_fetch") is True

        # tor-shell plugin: when registered, capabilities are prefixed
        # e.g., "tor-shell" + "_" + "darknet_dw" = "tor-shell_darknet_dw"
        assert engine._is_high_risk_capability("tor-shell_darknet_dw") is True

    def test_tor_plugin_name_and_version(self) -> None:
        """Test Tor plugin metadata."""
        manifest = create_tor_manifest()

        assert manifest.plugin.name == "tor"
        assert manifest.plugin.version == "1.0.0"

    def test_tor_shell_plugin_name_and_version(self) -> None:
        """Test Tor-shell plugin metadata."""
        manifest = create_tor_shell_manifest()

        assert manifest.plugin.name == "tor-shell"
        assert manifest.plugin.version == "1.0.0"


# =============================================================================
# Integration Tests: Policy + Plugin Execution
# =============================================================================


class TestPolicyPluginIntegration:
    """Integration tests combining policy evaluation with plugin execution."""

    @pytest.mark.asyncio
    async def test_full_flow_blocked_by_safe_mode(
        self,
        safe_mode_policy: PolicyConfig,
        tor_plugin: TorPlugin,
    ) -> None:
        """Test that a capability blocked by policy is not executed.

        This simulates the full flow where policy is checked BEFORE execution.
        """
        engine = PolicyEngine(safe_mode_policy)

        # Step 1: Check policy (this happens before execution in real flow)
        decision = engine.evaluate("tor_fetch", {"url": "http://example.onion"})

        # Step 2: In real system, execution would be skipped if decision.allowed is False
        assert decision.allowed is False

        # We can verify plugin execution WOULD work by mocking,
        # but the policy should have blocked it
        mock_client = AsyncMock()
        mock_response = MagicMock(status_code=200, text="content", content=b"content")
        mock_response.headers = {}
        mock_response.url = "http://example.onion"
        mock_response.encoding = "utf-8"
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Plugin execution should NOT happen in real flow due to policy denial
        # This test demonstrates the separation of concerns
        assert decision.reason == (
            "Capability 'tor_fetch' is blocked in safe mode. "
            "Add an explicit policy rule to enable it."
        )

    @pytest.mark.asyncio
    async def test_full_flow_allowed_with_explicit_rule(
        self,
        safe_mode_policy_with_tor_allow: PolicyConfig,
        tor_plugin: TorPlugin,
    ) -> None:
        """Test full flow: policy allows, then plugin executes successfully."""
        engine = PolicyEngine(safe_mode_policy_with_tor_allow)

        # Step 1: Check policy
        decision = engine.evaluate("tor_fetch", {"url": "http://example.onion"})
        assert decision.allowed is True

        # Step 2: Execute plugin (with mocked network)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Tor content"
        mock_response.content = b"Tor content"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "http://example.onion"
        mock_response.encoding = "utf-8"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tor_plugin.execute("tor_fetch", {"url": "http://example.onion"})

        assert result.success is True
        assert result.data["status_code"] == 200


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestTorPluginErrorHandling:
    """Tests for error handling in Tor plugins (offline)."""

    @pytest.mark.asyncio
    async def test_tor_fetch_timeout_handling(self, tor_plugin: TorPlugin) -> None:
        """Test tor_fetch handles timeout errors gracefully."""
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tor_plugin.execute(
                "tor_fetch", {"url": "http://example.onion", "timeout": 30}
            )

        assert result.success is False
        assert result.status == ResultStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_tor_fetch_connection_error(self, tor_plugin: TorPlugin) -> None:
        """Test tor_fetch handles connection errors gracefully."""
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tor_plugin.execute(
                "tor_fetch", {"url": "http://example.onion"}
            )

        assert result.success is False
        assert result.error_code == "CONNECT_ERROR"

    @pytest.mark.asyncio
    async def test_tor_shell_subprocess_error(
        self, tor_shell_plugin: TorShellPlugin
    ) -> None:
        """Test tor-shell handles subprocess errors gracefully."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error: connection failed")
        )
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await tor_shell_plugin.execute("darknet_dw", {})

        assert result.success is False
        assert result.error_code == "BROWSER_FAILED"

    @pytest.mark.asyncio
    async def test_tor_shell_browser_not_found(
        self, tor_shell_plugin: TorShellPlugin
    ) -> None:
        """Test tor-shell handles missing browser gracefully."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("w3m not found"),
        ):
            result = await tor_shell_plugin.execute("darknet_dw", {})

        assert result.success is False
        assert result.error_code == "BROWSER_NOT_FOUND"
        assert "w3m" in result.error_message


# =============================================================================
# Wildcard Policy Rules
# =============================================================================


class TestWildcardPolicyRules:
    """Tests for wildcard policy rules affecting Tor capabilities."""

    def test_wildcard_allow_all_tor(self) -> None:
        """Test wildcard rule allowing all tor_* capabilities."""
        policy = PolicyConfig(
            name="allow-all-tor",
            version="1.0",
            safe_mode=True,
            rules=[
                PolicyRule(
                    name="allow-all-tor",
                    capability_pattern="tor_.*",
                    action=PolicyAction.ALLOW,
                    priority=100,
                ),
            ],
        )
        engine = PolicyEngine(policy)

        # All tor capabilities should be allowed
        assert engine.evaluate("tor_fetch", {}).allowed is True
        assert engine.evaluate("tor_browse", {}).allowed is True
        assert engine.evaluate("tor_start", {}).allowed is True

    def test_wildcard_allow_all_tor_shell(self) -> None:
        """Test wildcard rule allowing all tor-shell_* capabilities."""
        policy = PolicyConfig(
            name="allow-all-tor-shell",
            version="1.0",
            safe_mode=True,
            rules=[
                PolicyRule(
                    name="allow-all-tor-shell",
                    capability_pattern="tor-shell_.*",
                    action=PolicyAction.ALLOW,
                    priority=100,
                ),
            ],
        )
        engine = PolicyEngine(policy)

        # All tor-shell capabilities should be allowed
        assert engine.evaluate("tor-shell_darknet_dw", {}).allowed is True
        assert engine.evaluate("tor-shell_darknet_nyt", {}).allowed is True

    def test_deny_rule_takes_precedence(self) -> None:
        """Test that explicit DENY takes precedence over ALLOW."""
        policy = PolicyConfig(
            name="mixed-rules",
            version="1.0",
            safe_mode=False,  # Not in safe mode for this test
            rules=[
                PolicyRule(
                    name="allow-tor",
                    capability_pattern="tor_.*",
                    action=PolicyAction.ALLOW,
                    priority=50,
                ),
                PolicyRule(
                    name="deny-tor-start",
                    capability_pattern="tor_start",
                    action=PolicyAction.DENY,
                    priority=100,  # Higher priority
                ),
            ],
        )
        engine = PolicyEngine(policy)

        # tor_fetch allowed by wildcard rule
        assert engine.evaluate("tor_fetch", {}).allowed is True

        # tor_start blocked by specific deny rule (higher priority)
        assert engine.evaluate("tor_start", {}).allowed is False
