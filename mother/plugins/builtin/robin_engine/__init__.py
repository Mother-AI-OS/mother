"""Vendored engine from `robin` (AI-powered dark web OSINT tool).

Upstream: https://github.com/apurvsinghgautam/robin (MIT). Vendored here so the
Mother OS `darkweb_osint` plugin can drive the pipeline programmatically without
the Streamlit UI. Only intra-package imports were rewritten to be relative; the
engine logic is unchanged. It talks to the local Tor SOCKS proxy on
127.0.0.1:9050 and to whichever LLM provider is configured (defaults to Claude).
"""

from __future__ import annotations

from .health import check_llm_health, check_search_engines, check_tor_proxy
from .llm import (
    PRESET_PROMPTS,
    filter_results,
    generate_summary,
    get_llm,
    refine_query,
)
from .llm_utils import get_model_choices, resolve_model_config
from .scrape import scrape_multiple
from .search import DEFAULT_SEARCH_ENGINES, SEARCH_ENGINES, get_search_results

__all__ = [
    "get_search_results",
    "SEARCH_ENGINES",
    "DEFAULT_SEARCH_ENGINES",
    "scrape_multiple",
    "get_llm",
    "refine_query",
    "filter_results",
    "generate_summary",
    "PRESET_PROMPTS",
    "get_model_choices",
    "resolve_model_config",
    "check_tor_proxy",
    "check_search_engines",
    "check_llm_health",
]
