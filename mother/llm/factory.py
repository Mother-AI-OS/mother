"""Factory for creating LLM providers."""

from typing import TYPE_CHECKING, Any

from .base import LLMProvider, ProviderType
from .providers.anthropic import AnthropicProvider
from .providers.openai import OpenAIProvider
from .providers.zhipu import ZhipuProvider
from .providers.gemini import GeminiProvider

if TYPE_CHECKING:
    from ..config.settings import Settings


# Default models for each provider
DEFAULT_MODELS: dict[ProviderType, str] = {
    ProviderType.ANTHROPIC: "claude-sonnet-4-20250514",
    ProviderType.OPENAI: "gpt-4-turbo-preview",
    ProviderType.ZHIPU: "glm-4-plus",
    ProviderType.GEMINI: "gemini-1.5-pro",
}


PROVIDER_CLASSES: dict[ProviderType, type[LLMProvider]] = {
    ProviderType.ANTHROPIC: AnthropicProvider,
    ProviderType.OPENAI: OpenAIProvider,
    ProviderType.ZHIPU: ZhipuProvider,
    ProviderType.GEMINI: GeminiProvider,
}


def create_provider(
    provider_type: ProviderType | str,
    api_key: str,
    model: str | None = None,
    **kwargs: Any,
) -> LLMProvider:
    """Create an LLM provider instance.

    Args:
        provider_type: The type of provider to create
        api_key: API key for the provider
        model: Model to use (defaults to provider's default)
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured LLMProvider instance

    Raises:
        ValueError: If provider type is unknown
    """
    if isinstance(provider_type, str):
        provider_type = ProviderType(provider_type.lower())

    provider_class = PROVIDER_CLASSES.get(provider_type)
    if not provider_class:
        raise ValueError(f"Unknown provider type: {provider_type}")

    model = model or DEFAULT_MODELS[provider_type]

    return provider_class(
        api_key=api_key,
        model=model,
        **kwargs,
    )


def get_provider_for_settings(settings: "Settings") -> LLMProvider:
    """Create provider based on application settings.

    Args:
        settings: Application Settings instance

    Returns:
        Configured LLMProvider

    Raises:
        ValueError: If required API key is missing
    """
    provider_type = ProviderType(settings.ai_provider.lower())

    # Get appropriate API key
    api_key_map: dict[ProviderType, str | None] = {
        ProviderType.ANTHROPIC: settings.anthropic_api_key,
        ProviderType.OPENAI: settings.openai_api_key,
        ProviderType.ZHIPU: settings.zhipu_api_key,
        ProviderType.GEMINI: settings.gemini_api_key,
    }

    api_key = api_key_map.get(provider_type)
    if not api_key:
        env_var_map = {
            ProviderType.ANTHROPIC: "ANTHROPIC_API_KEY",
            ProviderType.OPENAI: "OPENAI_API_KEY",
            ProviderType.ZHIPU: "ZHIPU_API_KEY",
            ProviderType.GEMINI: "GEMINI_API_KEY",
        }
        raise ValueError(
            f"Missing API key for provider '{provider_type.value}'. "
            f"Set {env_var_map[provider_type]} environment variable."
        )

    # Get model from settings or use default
    model = settings.llm_model or DEFAULT_MODELS[provider_type]

    return create_provider(
        provider_type=provider_type,
        api_key=api_key,
        model=model,
        max_tokens=settings.max_tokens,
    )
