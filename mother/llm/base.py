"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from .response import LLMResponse, ToolResult


class ProviderType(Enum):
    """Supported LLM provider types."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    ZHIPU = "zhipu"
    GEMINI = "gemini"


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Each provider implementation must handle:
    - Converting tool schemas to provider-specific format
    - Sending messages and receiving responses
    - Formatting tool results for the provider
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 16384,
        **kwargs: Any,
    ):
        """Initialize the provider.

        Args:
            api_key: API key for the provider
            model: Model identifier to use
            max_tokens: Maximum tokens in response
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self._config = kwargs
        self._client: Any = None

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type enum."""
        ...

    @abstractmethod
    def _initialize_client(self) -> None:
        """Initialize the provider-specific client."""
        ...

    @abstractmethod
    async def create_message(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send a message to the LLM and get a response.

        Args:
            messages: List of conversation messages in Anthropic format
            system_prompt: System prompt
            tools: List of tool definitions in Anthropic format

        Returns:
            Unified LLMResponse object
        """
        ...

    @abstractmethod
    def convert_tool_schema(self, anthropic_schema: dict[str, Any]) -> dict[str, Any]:
        """Convert Anthropic tool schema to provider-specific format.

        Args:
            anthropic_schema: Tool definition in Anthropic format

        Returns:
            Tool definition in provider-specific format
        """
        ...

    @abstractmethod
    def format_tool_result(self, tool_result: ToolResult) -> dict[str, Any]:
        """Format a tool result for the provider.

        Args:
            tool_result: ToolResult object

        Returns:
            Tool result in provider-specific message format
        """
        ...

    def convert_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """Convert a list of tools to provider-specific format.

        Args:
            tools: List of tools in Anthropic format

        Returns:
            List of tools in provider-specific format, or None
        """
        if tools is None:
            return None
        return [self.convert_tool_schema(tool) for tool in tools]
