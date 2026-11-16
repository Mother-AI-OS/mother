"""Tests for the built-in dark web OSINT (robin) plugin.

Covers manifest validation, high-risk gating, capability dispatch, and the
investigation pipeline. All network and LLM operations are mocked for offline,
deterministic testing.
"""

from unittest.mock import MagicMock, patch

import pytest

from mother.plugins.builtin.robin_plugin import (
    DEFAULT_MODEL,
    RobinPlugin,
    _create_manifest,
)
from mother.plugins.manifest import RiskLevel
from mother.policy.engine import PolicyEngine

ENGINE = "mother.plugins.builtin.robin_engine"

# The vendored engine needs the optional `darkweb` extra (LangChain, bs4,
# requests). Import it up front so the whole module skips with a clear reason
# when that extra is absent, rather than every patch() failing individually.
pytest.importorskip(
    ENGINE,
    reason='darkweb extra not installed - run: pip install "mother-ai-os[darkweb]"',
)


class TestCreateManifest:
    def test_creates_valid_manifest(self):
        manifest = _create_manifest()
        assert manifest.plugin.name == "darkweb-osint"
        assert manifest.plugin.version == "1.0.0"
        assert len(manifest.capabilities) == 3

    def test_expected_capabilities(self):
        cap_names = [c.name for c in _create_manifest().capabilities]
        assert "robin_investigate" in cap_names
        assert "robin_search" in cap_names
        assert "robin_health" in cap_names

    def test_gated_as_high_risk(self):
        manifest = _create_manifest()
        assert manifest.plugin.risk_level == RiskLevel.HIGH
        assert manifest.is_disabled_by_default() is True
        assert "network:external" in manifest.get_high_risk_permissions()

    def test_investigate_requires_confirmation(self):
        caps = {c.name: c for c in _create_manifest().capabilities}
        assert caps["robin_investigate"].confirmation_required is True


class TestPluginInit:
    def test_default_model(self):
        plugin = RobinPlugin()
        assert plugin._default_model == DEFAULT_MODEL

    def test_config_overrides_model(self):
        plugin = RobinPlugin({"model": "gpt-4.1"})
        assert plugin._default_model == "gpt-4.1"


class TestExecuteErrors:
    @pytest.mark.asyncio
    async def test_unknown_capability(self):
        plugin = RobinPlugin()
        result = await plugin.execute("robin_nope", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_invalid_preset(self):
        plugin = RobinPlugin()
        result = await plugin.execute("robin_investigate", {"query": "x", "preset": "bogus"})
        assert result.success is False
        assert result.error_code == "INVALID_PRESET"


class TestInvestigate:
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        plugin = RobinPlugin()
        onion = [{"title": "t", "link": "http://abc.onion"}]
        with (
            patch(f"{ENGINE}.get_llm", return_value=MagicMock()),
            patch(f"{ENGINE}.refine_query", return_value="refined q") as refine,
            patch(f"{ENGINE}.get_search_results", return_value=onion) as search,
            patch(f"{ENGINE}.filter_results", return_value=onion),
            patch(f"{ENGINE}.scrape_multiple", return_value={"http://abc.onion": "text"}),
            patch(f"{ENGINE}.generate_summary", return_value="REPORT"),
        ):
            result = await plugin.execute("robin_investigate", {"query": "acme leak", "preset": "threat_intel"})

        assert result.success is True
        assert result.data["report"] == "REPORT"
        assert result.data["refined_query"] == "refined q"
        assert result.data["num_search_results"] == 1
        refine.assert_called_once()
        # spaces are converted to + before searching (upstream behavior)
        assert "+" in search.call_args.args[0]

    @pytest.mark.asyncio
    async def test_no_results_short_circuits(self):
        plugin = RobinPlugin()
        with (
            patch(f"{ENGINE}.get_llm", return_value=MagicMock()),
            patch(f"{ENGINE}.refine_query", return_value="q"),
            patch(f"{ENGINE}.get_search_results", return_value=[]),
            patch(f"{ENGINE}.filter_results") as flt,
            patch(f"{ENGINE}.generate_summary") as summ,
        ):
            result = await plugin.execute("robin_investigate", {"query": "nothing"})

        assert result.success is True
        assert result.data["num_search_results"] == 0
        flt.assert_not_called()
        summ.assert_not_called()


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_only(self):
        plugin = RobinPlugin()
        onion = [{"title": "t", "link": "http://abc.onion"}]
        with (
            patch(f"{ENGINE}.get_llm", return_value=MagicMock()),
            patch(f"{ENGINE}.refine_query", return_value="q"),
            patch(f"{ENGINE}.get_search_results", return_value=onion),
            patch(f"{ENGINE}.filter_results", return_value=onion),
            patch(f"{ENGINE}.scrape_multiple") as scrape,
        ):
            result = await plugin.execute("robin_search", {"query": "acme"})

        assert result.success is True
        assert result.data["num_filtered"] == 1
        scrape.assert_not_called()


class TestHealth:
    @pytest.mark.asyncio
    async def test_health(self):
        plugin = RobinPlugin()
        with (
            patch(f"{ENGINE}.check_tor_proxy", return_value={"status": "up"}),
            patch(f"{ENGINE}.check_search_engines", return_value=[{"status": "up"}, {"status": "down"}]),
            patch(f"{ENGINE}.check_llm_health", return_value={"status": "up", "provider": "Anthropic"}),
        ):
            result = await plugin.execute("robin_health", {})

        assert result.success is True
        assert result.data["tor_proxy"]["status"] == "up"
        assert result.data["search_engines_up"] == "1/2"


class TestPolicyClassification:
    def test_robin_capabilities_are_high_risk(self):
        engine = PolicyEngine()
        assert engine._is_high_risk_capability("robin_investigate") is True
        assert engine._is_high_risk_capability("robin_search") is True
        assert engine._is_high_risk_capability("robin_health") is True
