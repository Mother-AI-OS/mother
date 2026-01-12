"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from .response import LLMResponse, ToolResult


class ProviderType(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    ZHIPU = "zhipu"
    GEMINI = "gemini"


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All providers must implement:
    - create_message(): Send messages and get a response
    - convert_tool_schema(): Convert Anthropic-format schema to provider format
    - format_tool_result(): Format tool results for the provider
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 4096,
        timeout: int = 300,
    ):
        """Initialize the provider.

        Args:
            api_key: API key for the provider
            model: Model identifier to use
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._client: Any = None

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
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
        """Send messages to the LLM and get a response.

        Args:
            messages: Conversation history in Anthropic format
            system_prompt: System instructions
            tools: Tool definitions in Anthropic format (will be converted)

        Returns:
            Unified LLMResponse
        """
        ...

    @abstractmethod
    def convert_tool_schema(
        self,
        anthropic_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Convert Anthropic tool schema to provider format.

        Args:
            anthropic_schema: Tool definition in Anthropic format:
                {name, description, input_schema: {type, properties, required}}

        Returns:
            Tool definition in provider's format
        """
        ...

    @abstractmethod
    def format_tool_result(
        self,
        tool_result: ToolResult,
    ) -> dict[str, Any]:
        """Format a tool result for the provider's message format.

        Args:
            tool_result: Unified tool result

        Returns:
            Provider-specific tool result message
        """
        ...

    def convert_tools(
        self,
        anthropic_tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert multiple tool schemas.

        Args:
            anthropic_tools: List of Anthropic-format tool schemas

        Returns:
            List of provider-format tool schemas
        """
        return [self.convert_tool_schema(t) for t in anthropic_tools]
