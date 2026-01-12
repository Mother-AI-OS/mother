"""Google Gemini LLM provider using the new google.genai SDK."""

from typing import Any

from google import genai
from google.genai import types

from ..base import LLMProvider, ProviderType
from ..response import LLMResponse, ToolCall, ToolResult


class GeminiProvider(LLMProvider):
    """Google Gemini provider using the unified google.genai SDK.

    Uses the new google-genai package which replaces the deprecated
    google-generativeai package.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GEMINI

    def _initialize_client(self) -> None:
        self._client = genai.Client(api_key=self.api_key)

    async def create_message(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        if self._client is None:
            self._initialize_client()

        # Convert messages to Gemini format
        gemini_history = self._convert_messages(messages)

        # Prepare tools
        gemini_tools = None
        if tools:
            function_declarations = [
                self._create_function_declaration(t) for t in tools
            ]
            gemini_tools = [types.Tool(function_declarations=function_declarations)]

        # Prepare generation config
        config = types.GenerateContentConfig(
            max_output_tokens=self.max_tokens,
            system_instruction=system_prompt,
        )
        if gemini_tools:
            config = types.GenerateContentConfig(
                max_output_tokens=self.max_tokens,
                system_instruction=system_prompt,
                tools=gemini_tools,
                # Disable automatic function calling - we handle it manually
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            )

        # Get the last user message for the send_message call
        last_message = ""
        if gemini_history:
            last_entry = gemini_history[-1]
            if isinstance(last_entry.parts, list) and last_entry.parts:
                first_part = last_entry.parts[0]
                if hasattr(first_part, "text"):
                    last_message = first_part.text
                elif isinstance(first_part, str):
                    last_message = first_part
            gemini_history = gemini_history[:-1]

        # Use async chat API
        chat = self._client.aio.chats.create(
            model=self.model,
            history=gemini_history if gemini_history else None,
            config=config,
        )

        response = await chat.send_message(last_message)

        # Parse response
        text = ""
        tool_calls: list[ToolCall] = []

        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    text += part.text
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append(
                        ToolCall(
                            id=f"call_{fc.name}_{len(tool_calls)}",
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {},
                        )
                    )

        # Extract usage if available
        usage = {}
        if response.usage_metadata:
            usage = {
                "input_tokens": response.usage_metadata.prompt_token_count or 0,
                "output_tokens": response.usage_metadata.candidates_token_count or 0,
            }

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason="end_turn" if not tool_calls else "tool_use",
            usage=usage,
            raw_response=response,
        )

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> list[types.Content]:
        """Convert Anthropic messages to Gemini Content format."""
        gemini_history: list[types.Content] = []

        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]

            if isinstance(content, str):
                gemini_history.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=content)],
                    )
                )
            elif isinstance(content, list):
                parts: list[types.Part] = []
                for item in content:
                    if item.get("type") == "text":
                        parts.append(types.Part.from_text(text=item["text"]))
                    elif item.get("type") == "tool_result":
                        # Function response in Gemini
                        parts.append(
                            types.Part.from_function_response(
                                name=item.get("tool_name", "unknown"),
                                response={"result": item["content"]},
                            )
                        )
                    elif item.get("type") == "tool_use":
                        parts.append(
                            types.Part.from_function_call(
                                name=item["name"],
                                args=item["input"],
                            )
                        )
                if parts:
                    gemini_history.append(types.Content(role=role, parts=parts))

        return gemini_history

    def _create_function_declaration(
        self, anthropic_schema: dict[str, Any]
    ) -> types.FunctionDeclaration:
        """Create Gemini FunctionDeclaration from Anthropic schema."""
        input_schema = anthropic_schema.get("input_schema", {})

        return types.FunctionDeclaration(
            name=anthropic_schema["name"],
            description=anthropic_schema.get("description", ""),
            parameters=input_schema,
        )

    def convert_tool_schema(self, anthropic_schema: dict[str, Any]) -> dict[str, Any]:
        """Convert to Gemini format (for reference)."""
        return {
            "name": anthropic_schema["name"],
            "description": anthropic_schema.get("description", ""),
            "parameters": anthropic_schema.get("input_schema", {}),
        }

    def format_tool_result(self, tool_result: ToolResult) -> dict[str, Any]:
        """Format for Gemini function response."""
        # Extract function name from tool_call_id (format: call_name_index)
        parts = tool_result.tool_call_id.split("_")
        name = parts[1] if len(parts) > 1 else "unknown"

        return {
            "function_response": {
                "name": name,
                "response": {"result": tool_result.content},
            }
        }
