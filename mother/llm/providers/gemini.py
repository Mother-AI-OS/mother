"""Google Gemini LLM provider."""

from typing import Any

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

from ..base import LLMProvider, ProviderType
from ..response import LLMResponse, ToolCall, ToolResult


class GeminiProvider(LLMProvider):
    """Google Gemini provider.

    Gemini has a different approach to function calling with
    FunctionDeclaration objects and a chat-based API.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GEMINI

    def _initialize_client(self) -> None:
        genai.configure(api_key=self.api_key)
        self._client = genai.GenerativeModel(self.model)

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

        # Configure generation
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=self.max_tokens,
        )

        # Prepare tools
        gemini_tools = None
        if tools:
            function_declarations = [
                self._create_function_declaration(t) for t in tools
            ]
            gemini_tools = [Tool(function_declarations=function_declarations)]

        # Get the last user message for the send_message call
        last_message = ""
        if gemini_history:
            last_entry = gemini_history[-1]
            if isinstance(last_entry.get("parts"), list) and last_entry["parts"]:
                last_message = last_entry["parts"][0]
            elif isinstance(last_entry.get("parts"), str):
                last_message = last_entry["parts"]

        # Build history without the last message
        history = gemini_history[:-1] if gemini_history else []

        # Start chat with history
        chat = self._client.start_chat(history=history)

        # Send message with system instruction
        response = chat.send_message(
            last_message,
            generation_config=generation_config,
            tools=gemini_tools,
        )

        # Parse response
        text = ""
        tool_calls: list[ToolCall] = []

        for part in response.parts:
            if hasattr(part, "text") and part.text:
                text += part.text
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                tool_calls.append(
                    ToolCall(
                        id=f"call_{fc.name}_{len(tool_calls)}",
                        name=fc.name,
                        arguments=dict(fc.args),
                    )
                )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason="end_turn" if not tool_calls else "tool_use",
            usage={},  # Gemini usage tracking differs
            raw_response=response,
        )

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert Anthropic messages to Gemini format."""
        gemini_history: list[dict[str, Any]] = []

        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]

            if isinstance(content, str):
                gemini_history.append(
                    {
                        "role": role,
                        "parts": [content],
                    }
                )
            elif isinstance(content, list):
                parts: list[Any] = []
                for item in content:
                    if item.get("type") == "text":
                        parts.append(item["text"])
                    elif item.get("type") == "tool_result":
                        # Function response in Gemini
                        parts.append(
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=item.get("tool_name", "unknown"),
                                    response={"result": item["content"]},
                                )
                            )
                        )
                    elif item.get("type") == "tool_use":
                        parts.append(
                            genai.protos.Part(
                                function_call=genai.protos.FunctionCall(
                                    name=item["name"],
                                    args=item["input"],
                                )
                            )
                        )
                if parts:
                    gemini_history.append({"role": role, "parts": parts})

        return gemini_history

    def _create_function_declaration(
        self, anthropic_schema: dict[str, Any]
    ) -> FunctionDeclaration:
        """Create Gemini FunctionDeclaration from Anthropic schema."""
        input_schema = anthropic_schema.get("input_schema", {})

        # Convert JSON Schema to Gemini parameter format
        parameters = self._convert_json_schema_to_gemini(input_schema)

        return FunctionDeclaration(
            name=anthropic_schema["name"],
            description=anthropic_schema.get("description", ""),
            parameters=parameters,
        )

    def _convert_json_schema_to_gemini(self, json_schema: dict[str, Any]) -> dict[str, Any]:
        """Convert JSON Schema to Gemini's parameter format."""
        result: dict[str, Any] = {"type": json_schema.get("type", "object")}

        if "properties" in json_schema:
            result["properties"] = {}
            for name, prop in json_schema["properties"].items():
                result["properties"][name] = {
                    "type": prop.get("type", "string"),
                    "description": prop.get("description", ""),
                }
                if "enum" in prop:
                    result["properties"][name]["enum"] = prop["enum"]

        if "required" in json_schema:
            result["required"] = json_schema["required"]

        return result

    def convert_tool_schema(self, anthropic_schema: dict[str, Any]) -> dict[str, Any]:
        """Convert to Gemini format (for reference)."""
        return {
            "name": anthropic_schema["name"],
            "description": anthropic_schema.get("description", ""),
            "parameters": self._convert_json_schema_to_gemini(
                anthropic_schema.get("input_schema", {})
            ),
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
