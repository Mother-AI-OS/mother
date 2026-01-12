"""Anthropic Claude LLM provider."""

from typing import Any

import anthropic

from ..base import LLMProvider, ProviderType
from ..response import LLMResponse, ToolCall, ToolResult


class AnthropicProvider(LLMProvider):
    """Claude provider using Anthropic's API.

    This is the primary/native provider - schemas pass through unchanged
    since the internal format matches Anthropic's tool_use format.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.ANTHROPIC

    def _initialize_client(self) -> None:
        self._client = anthropic.Anthropic(api_key=self.api_key)

    async def create_message(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        if self._client is None:
            self._initialize_client()

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": messages,
        }

        if tools:
            kwargs["tools"] = tools  # Already in Anthropic format

        response = self._client.messages.create(**kwargs)

        # Parse response into unified format
        text = ""
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "end_turn",
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            raw_response=response,
        )

    def convert_tool_schema(self, anthropic_schema: dict[str, Any]) -> dict[str, Any]:
        """No conversion needed - already Anthropic format."""
        return anthropic_schema

    def format_tool_result(self, tool_result: ToolResult) -> dict[str, Any]:
        """Format for Anthropic tool_result block."""
        return {
            "type": "tool_result",
            "tool_use_id": tool_result.tool_call_id,
            "content": tool_result.content,
            "is_error": tool_result.is_error,
        }
