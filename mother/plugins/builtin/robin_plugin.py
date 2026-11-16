"""Built-in dark web OSINT plugin for Mother AI OS.

Wraps the vendored `robin` engine (see robin_engine/) to run AI-driven dark web
OSINT investigations: LLM query refinement -> multi-engine .onion search over Tor
-> LLM result filtering -> Tor scraping -> structured intelligence report.

HIGH-RISK: this plugin reaches dark web search engines and hidden services over
Tor and sends scraped content to an LLM provider. It is registered but disabled
by default (risk_level=HIGH) and its capabilities are blocked by safe_mode; it
runs only when a user explicitly enables it. Intended for lawful investigative
and threat-intelligence use only.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..base import PluginBase, PluginResult
from ..manifest import (
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
    RiskLevel,
)

# Default model — the vendored engine ships a tested ChatAnthropic path. Override
# per-call with the `model` parameter or globally via plugin config.
DEFAULT_MODEL = "claude-sonnet-4-5"

# Report presets supported by the engine (see robin_engine/llm.py PRESET_PROMPTS).
VALID_PRESETS = (
    "threat_intel",
    "ransomware_malware",
    "personal_identity",
    "corporate_espionage",
)


def _create_manifest() -> PluginManifest:
    """Create the dark web OSINT plugin manifest programmatically."""
    model_param = ParameterSpec(
        name="model",
        type=ParameterType.STRING,
        description=(
            "LLM model key to drive the investigation (e.g. 'claude-sonnet-4-5', "
            "'gpt-4.1', 'gemini-2.5-pro', or a local Ollama model). Requires the "
            "matching provider API key in the environment."
        ),
        required=False,
        default=DEFAULT_MODEL,
    )

    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="darkweb-osint",
            version="1.0.0",
            description="AI-powered dark web OSINT investigations over Tor (robin engine)",
            author="David Sanker <david@lawkraft.com>",
            license="MIT",
            homepage="https://github.com/apurvsinghgautam/robin",
            repository="https://github.com/apurvsinghgautam/robin",
            risk_level=RiskLevel.HIGH,
            disabled_by_default=True,
        ),
        capabilities=[
            CapabilitySpec(
                name="robin_investigate",
                description=(
                    "Run a full dark web OSINT investigation: refine the query with an "
                    "LLM, search dark web search engines over Tor, filter the best "
                    "results, scrape them, and produce a structured intelligence report."
                ),
                confirmation_required=True,
                timeout=600,
                parameters=[
                    ParameterSpec(
                        name="query",
                        type=ParameterType.STRING,
                        description="The investigation query / subject.",
                        required=True,
                    ),
                    ParameterSpec(
                        name="preset",
                        type=ParameterType.STRING,
                        description=(
                            "Report preset: 'threat_intel' (default), "
                            "'ransomware_malware', 'personal_identity', or "
                            "'corporate_espionage'."
                        ),
                        required=False,
                        default="threat_intel",
                    ),
                    model_param,
                    ParameterSpec(
                        name="custom_instructions",
                        type=ParameterType.STRING,
                        description="Extra focus instructions appended to the report prompt.",
                        required=False,
                        default="",
                    ),
                    ParameterSpec(
                        name="max_results",
                        type=ParameterType.INTEGER,
                        description="Cap on raw search results fed to the LLM filter (default 50).",
                        required=False,
                        default=50,
                    ),
                    ParameterSpec(
                        name="max_scrape",
                        type=ParameterType.INTEGER,
                        description="Cap on filtered results actually scraped over Tor (default 10).",
                        required=False,
                        default=10,
                    ),
                    ParameterSpec(
                        name="workers",
                        type=ParameterType.INTEGER,
                        description="Concurrent Tor workers for search/scrape (default 5).",
                        required=False,
                        default=5,
                    ),
                ],
            ),
            CapabilitySpec(
                name="robin_search",
                description=(
                    "Refine the query and search dark web search engines over Tor, "
                    "returning the filtered list of .onion results without scraping "
                    "or summarizing."
                ),
                confirmation_required=False,
                timeout=180,
                parameters=[
                    ParameterSpec(
                        name="query",
                        type=ParameterType.STRING,
                        description="The search query / subject.",
                        required=True,
                    ),
                    model_param,
                    ParameterSpec(
                        name="max_results",
                        type=ParameterType.INTEGER,
                        description="Cap on raw search results fed to the LLM filter (default 50).",
                        required=False,
                        default=50,
                    ),
                ],
            ),
            CapabilitySpec(
                name="robin_health",
                description=(
                    "Health check: verify the Tor proxy, ping the dark web search "
                    "engines over Tor, and test the selected LLM provider."
                ),
                confirmation_required=False,
                timeout=180,
                parameters=[model_param],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.robin_plugin",
                **{"class": "RobinPlugin"},
            ),
        ),
        permissions=[
            "network:external",
            "tor:read",
            "llm:invoke",
        ],
    )


class RobinPlugin(PluginBase):
    """Built-in plugin for AI-powered dark web OSINT investigations over Tor."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the dark web OSINT plugin."""
        super().__init__(_create_manifest(), config)
        self._default_model = config.get("model", DEFAULT_MODEL) if config else DEFAULT_MODEL

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a dark web OSINT capability."""
        handlers = {
            "robin_investigate": self._investigate,
            "robin_search": self._search,
            "robin_health": self._health,
        }
        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )
        try:
            return await handler(**params)
        except Exception as e:  # noqa: BLE001 - surface engine errors uniformly
            return PluginResult.error_result(f"Error: {e}", code="ROBIN_ERROR")

    async def _investigate(
        self,
        query: str,
        preset: str = "threat_intel",
        model: str | None = None,
        custom_instructions: str = "",
        max_results: int = 50,
        max_scrape: int = 10,
        workers: int = 5,
    ) -> PluginResult:
        """Run the full refine -> search -> filter -> scrape -> summarize pipeline."""
        model = model or self._default_model
        if preset not in VALID_PRESETS:
            return PluginResult.error_result(
                f"Invalid preset '{preset}'. Valid presets: {', '.join(VALID_PRESETS)}",
                code="INVALID_PRESET",
            )
        return await asyncio.to_thread(
            self._run_investigation,
            query,
            preset,
            model,
            custom_instructions,
            max_results,
            max_scrape,
            workers,
        )

    def _run_investigation(
        self,
        query: str,
        preset: str,
        model: str,
        custom_instructions: str,
        max_results: int,
        max_scrape: int,
        workers: int,
    ) -> PluginResult:
        """Blocking pipeline body (runs in a worker thread)."""
        from . import robin_engine as engine

        llm = engine.get_llm(model)
        refined = engine.refine_query(llm, query)

        results = engine.get_search_results(refined.replace(" ", "+"), max_workers=workers)
        if len(results) > max_results:
            results = results[:max_results]

        if not results:
            return PluginResult.success_result(
                data={
                    "query": query,
                    "refined_query": refined,
                    "model": model,
                    "preset": preset,
                    "num_search_results": 0,
                    "sources": [],
                    "report": "No dark web search results found for this query.",
                },
                raw_output="No dark web search results found for this query.",
            )

        filtered = engine.filter_results(llm, refined, results)
        if len(filtered) > max_scrape:
            filtered = filtered[:max_scrape]

        scraped = engine.scrape_multiple(filtered, max_workers=workers)
        report = engine.generate_summary(
            llm,
            query,
            scraped,
            preset=preset,
            custom_instructions=custom_instructions,
        )

        return PluginResult.success_result(
            data={
                "query": query,
                "refined_query": refined,
                "model": model,
                "preset": preset,
                "num_search_results": len(results),
                "num_filtered": len(filtered),
                "num_scraped": len(scraped),
                "sources": filtered,
                "report": report,
            },
            raw_output=report,
        )

    async def _search(
        self,
        query: str,
        model: str | None = None,
        max_results: int = 50,
    ) -> PluginResult:
        """Refine + search + filter only (no scrape/summary)."""
        model = model or self._default_model
        return await asyncio.to_thread(self._run_search, query, model, max_results)

    def _run_search(self, query: str, model: str, max_results: int) -> PluginResult:
        from . import robin_engine as engine

        llm = engine.get_llm(model)
        refined = engine.refine_query(llm, query)
        results = engine.get_search_results(refined.replace(" ", "+"), max_workers=5)
        if len(results) > max_results:
            results = results[:max_results]
        filtered = engine.filter_results(llm, refined, results) if results else []

        return PluginResult.success_result(
            data={
                "query": query,
                "refined_query": refined,
                "model": model,
                "num_search_results": len(results),
                "num_filtered": len(filtered),
                "results": filtered,
            }
        )

    async def _health(self, model: str | None = None) -> PluginResult:
        """Check Tor proxy, dark web search engines, and the LLM provider."""
        model = model or self._default_model
        return await asyncio.to_thread(self._run_health, model)

    def _run_health(self, model: str) -> PluginResult:
        from . import robin_engine as engine

        tor = engine.check_tor_proxy()
        engines = engine.check_search_engines()
        llm = engine.check_llm_health(model)
        up = sum(1 for e in engines if e.get("status") == "up")

        return PluginResult.success_result(
            data={
                "model": model,
                "tor_proxy": tor,
                "search_engines": engines,
                "search_engines_up": f"{up}/{len(engines)}",
                "llm": llm,
            }
        )


# Export the plugin class and manifest
__all__ = ["RobinPlugin", "_create_manifest"]
