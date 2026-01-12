"""OpenAI GPT LLM provider."""

import json
from typing import Any

from openai import OpenAI

from ..base import LLMProvider, ProviderType
from ..response import LLMResponse, ToolCall, ToolResult


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider.

    Converts Anthropic-format messages and schemas to OpenAI's
    chat completions format.
    """

    # OpenAI has a max of 128 tools
    MAX_TOOLS = 128

    @staticmethod
    def _sanitize_tool_name(name: str) -> str:
        """Sanitize tool name for OpenAI (no dots allowed).

        OpenAI function names must match ^[a-zA-Z0-9_-]+$
        We replace dots with double underscores.
        """
        return name.replace(".", "__")

    @staticmethod
    def _restore_tool_name(name: str) -> str:
        """Restore original tool name from sanitized OpenAI name."""
        return name.replace("__", ".")

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENAI

    def _initialize_client(self) -> None:
        self._client = OpenAI(api_key=self.api_key)

    async def create_message(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        if self._client is None:
            self._initialize_client()

        # Convert messages from Anthropic to OpenAI format
        openai_messages = self._convert_messages(messages, system_prompt)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": openai_messages,
        }

        if tools:
            converted = self.convert_tools(tools)
            # OpenAI has a max of 128 tools
            if len(converted) > self.MAX_TOOLS:
                converted = converted[: self.MAX_TOOLS]
            kwargs["tools"] = converted
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)

        # Parse response
        message = response.choices[0].message
        text = message.content or ""
        tool_calls: list[ToolCall] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                # Restore original tool name (convert __ back to .)
                original_name = self._restore_tool_name(tc.function.name)
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=original_name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=response.choices[0].finish_reason or "stop",
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            raw_response=response,
        )

    def _convert_messages(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
    ) -> list[dict[str, Any]]:
        """Convert Anthropic messages to OpenAI format."""
        openai_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                if isinstance(content, str):
                    openai_messages.append({"role": "user", "content": content})
                elif isinstance(content, list):
                    # Handle tool results
                    for item in content:
                        if item.get("type") == "tool_result":
                            openai_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": item["tool_use_id"],
                                    "content": item["content"],
                                }
                            )
                        else:
                            openai_messages.append({"role": "user", "content": str(item)})
            elif role == "assistant":
                if isinstance(content, str):
                    openai_messages.append({"role": "assistant", "content": content})
                elif isinstance(content, list):
                    # Handle assistant message with tool calls
                    text_parts: list[str] = []
                    tool_calls: list[dict[str, Any]] = []
                    for item in content:
                        if item.get("type") == "text":
                            text_parts.append(item["text"])
                        elif item.get("type") == "tool_use":
                            # Sanitize name for OpenAI
                            sanitized_name = self._sanitize_tool_name(item["name"])
                            tool_calls.append(
                                {
                                    "id": item["id"],
                                    "type": "function",
                                    "function": {
                                        "name": sanitized_name,
                                        "arguments": json.dumps(item["input"]),
                                    },
                                }
                            )

                    assistant_msg: dict[str, Any] = {"role": "assistant"}
                    if text_parts:
                        assistant_msg["content"] = "".join(text_parts)
                    else:
                        assistant_msg["content"] = None
                    if tool_calls:
                        assistant_msg["tool_calls"] = tool_calls
                    openai_messages.append(assistant_msg)

        return openai_messages

    def convert_tool_schema(self, anthropic_schema: dict[str, Any]) -> dict[str, Any]:
        """Convert Anthropic schema to OpenAI function format."""
        params = anthropic_schema.get("input_schema", {"type": "object", "properties": {}})
        # OpenAI requires 'items' on array types - fix any missing
        params = self._fix_array_schemas(params)
        # Sanitize name for OpenAI (no dots allowed)
        sanitized_name = self._sanitize_tool_name(anthropic_schema["name"])
        return {
            "type": "function",
            "function": {
                "name": sanitized_name,
                "description": anthropic_schema.get("description", ""),
                "parameters": params,
            },
        }

    def _fix_array_schemas(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Recursively fix array schemas that are missing 'items'."""
        if not isinstance(schema, dict):
            return schema

        result = schema.copy()

        # If this is an array type without items, add default items
        if result.get("type") == "array" and "items" not in result:
            result["items"] = {"type": "string"}

        # Recursively fix properties
        if "properties" in result:
            result["properties"] = {k: self._fix_array_schemas(v) for k, v in result["properties"].items()}

        # Recursively fix items
        if "items" in result and isinstance(result["items"], dict):
            result["items"] = self._fix_array_schemas(result["items"])

        return result

    def format_tool_result(self, tool_result: ToolResult) -> dict[str, Any]:
        """Format for OpenAI tool message."""
        return {
            "role": "tool",
            "tool_call_id": tool_result.tool_call_id,
            "content": tool_result.content,
        }
