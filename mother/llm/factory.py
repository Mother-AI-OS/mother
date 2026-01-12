"""Factory for creating LLM providers."""

from typing import TYPE_CHECKING

from .base import LLMProvider

if TYPE_CHECKING:
    from mother.config.settings import Settings

# Default models for each provider
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4-turbo",
    "zhipu": "glm-4",
    "gemini": "gemini-1.5-pro",
}

# Provider class mapping (lazy loaded)
_PROVIDER_CLASSES: dict[str, type[LLMProvider]] | None = None


def _load_provider_classes() -> dict[str, type[LLMProvider]]:
    """Lazily load provider classes to avoid import errors for missing dependencies."""
    global _PROVIDER_CLASSES
    if _PROVIDER_CLASSES is not None:
        return _PROVIDER_CLASSES

    _PROVIDER_CLASSES = {}

    # Always try to load all providers, they handle missing deps gracefully
    try:
        from .providers.anthropic import AnthropicProvider

        _PROVIDER_CLASSES["anthropic"] = AnthropicProvider
    except ImportError:
        pass

    try:
        from .providers.openai import OpenAIProvider

        _PROVIDER_CLASSES["openai"] = OpenAIProvider
    except ImportError:
        pass

    try:
        from .providers.zhipu import ZhipuProvider

        _PROVIDER_CLASSES["zhipu"] = ZhipuProvider
    except ImportError:
        pass

    try:
        from .providers.gemini import GeminiProvider

        _PROVIDER_CLASSES["gemini"] = GeminiProvider
    except ImportError:
        pass

    return _PROVIDER_CLASSES


def get_available_providers() -> list[str]:
    """Get list of available provider names."""
    return list(_load_provider_classes().keys())


def create_provider(
    provider_name: str,
    api_key: str,
    model: str | None = None,
    **kwargs,
) -> LLMProvider:
    """Create an LLM provider instance.

    Args:
        provider_name: Provider name ('anthropic', 'openai', 'zhipu', 'gemini')
        api_key: API key for the provider
        model: Model to use (uses default if not specified)
        **kwargs: Additional provider-specific configuration

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider is not available
    """
    providers = _load_provider_classes()

    if provider_name not in providers:
        available = ", ".join(providers.keys()) if providers else "none"
        raise ValueError(
            f"Provider '{provider_name}' is not available. "
            f"Available providers: {available}. "
            f"Make sure the required package is installed."
        )

    provider_class = providers[provider_name]
    model = model or DEFAULT_MODELS.get(provider_name, "")

    return provider_class(api_key=api_key, model=model, **kwargs)


def get_provider_for_settings(settings: "Settings") -> LLMProvider:
    """Create an LLM provider based on application settings.

    Args:
        settings: Application settings

    Returns:
        Configured LLMProvider instance

    Raises:
        ValueError: If provider is not configured or API key is missing
    """
    provider_name = settings.ai_provider.lower()

    # Get API key for the selected provider
    api_key_map = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "zhipu": settings.zhipu_api_key,
        "gemini": settings.gemini_api_key,
    }

    api_key = api_key_map.get(provider_name)

    if not api_key:
        # Check legacy key for anthropic
        if provider_name == "anthropic" and settings.anthropic_api_key:
            api_key = settings.anthropic_api_key
        else:
            key_name = f"{provider_name.upper()}_API_KEY"
            raise ValueError(
                f"API key not configured for provider '{provider_name}'. "
                f"Set the {key_name} environment variable."
            )

    # Determine model to use
    model = settings.llm_model
    if not model and provider_name == "anthropic":
        # Use legacy claude_model setting for backward compatibility
        model = settings.claude_model

    return create_provider(
        provider_name=provider_name,
        api_key=api_key,
        model=model,
    )
