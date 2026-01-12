"""Multi-LLM provider abstraction layer.

This module provides a unified interface for multiple LLM providers:
- Anthropic (Claude)
- OpenAI (GPT-4)
- Zhipu AI (GLM-4)
- Google (Gemini)

Usage:
    from mother.llm import create_provider, get_provider_for_settings
    from mother.config.settings import get_settings

    # Create from settings
    provider = get_provider_for_settings(get_settings())

    # Or create directly
    provider = create_provider("openai", api_key="sk-...", model="gpt-4-turbo")

    # Send messages
    response = provider.create_message(
        messages=[{"role": "user", "content": "Hello"}],
        system="You are a helpful assistant.",
    )
"""

from .base import LLMProvider, ProviderType
from .factory import (
    DEFAULT_MODELS,
    create_provider,
    get_available_providers,
    get_provider_for_settings,
)
from .response import LLMResponse, ToolCall, ToolResult, Usage

__all__ = [
    "LLMProvider",
    "ProviderType",
    "LLMResponse",
    "ToolCall",
    "ToolResult",
    "Usage",
    "create_provider",
    "get_provider_for_settings",
    "get_available_providers",
    "DEFAULT_MODELS",
]
