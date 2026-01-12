"""Tests for the multi-LLM provider abstraction layer."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from mother.llm import (
    LLMProvider,
    ProviderType,
    LLMResponse,
    ToolCall,
    ToolResult,
    Usage,
    DEFAULT_MODELS,
    create_provider,
    get_available_providers,
)
from mother.llm.base import LLMProvider as BaseLLMProvider
from mother.llm.factory import get_provider_for_settings


class TestProviderType:
    """Tests for ProviderType enum."""

    def test_anthropic(self):
        assert ProviderType.ANTHROPIC.value == "anthropic"

    def test_openai(self):
        assert ProviderType.OPENAI.value == "openai"

    def test_zhipu(self):
        assert ProviderType.ZHIPU.value == "zhipu"

    def test_gemini(self):
        assert ProviderType.GEMINI.value == "gemini"


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_creation(self):
        tc = ToolCall(id="call_123", name="test_tool", arguments={"arg1": "value1"})
        assert tc.id == "call_123"
        assert tc.name == "test_tool"
        assert tc.arguments == {"arg1": "value1"}


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_creation(self):
        tr = ToolResult(tool_call_id="call_123", content="Success!")
        assert tr.tool_call_id == "call_123"
        assert tr.content == "Success!"
        assert tr.is_error is False

    def test_with_error(self):
        tr = ToolResult(tool_call_id="call_123", content="Error occurred", is_error=True)
        assert tr.is_error is True


class TestUsage:
    """Tests for Usage dataclass."""

    def test_creation(self):
        usage = Usage(input_tokens=100, output_tokens=50)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50

    def test_total_tokens(self):
        usage = Usage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150

    def test_default_values(self):
        usage = Usage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_creation(self):
        response = LLMResponse(text="Hello!", stop_reason="end_turn")
        assert response.text == "Hello!"
        assert response.stop_reason == "end_turn"
        assert response.tool_calls == []

    def test_has_tool_calls_empty(self):
        response = LLMResponse()
        assert response.has_tool_calls is False

    def test_has_tool_calls_with_calls(self):
        tc = ToolCall(id="1", name="test", arguments={})
        response = LLMResponse(tool_calls=[tc])
        assert response.has_tool_calls is True

    def test_is_complete_true(self):
        response = LLMResponse(text="Done", stop_reason="end_turn")
        assert response.is_complete is True

    def test_is_complete_with_tool_calls(self):
        tc = ToolCall(id="1", name="test", arguments={})
        response = LLMResponse(tool_calls=[tc], stop_reason="tool_use")
        assert response.is_complete is False


class TestDefaultModels:
    """Tests for DEFAULT_MODELS."""

    def test_anthropic_model(self):
        assert "claude" in DEFAULT_MODELS["anthropic"]

    def test_openai_model(self):
        assert "gpt" in DEFAULT_MODELS["openai"]

    def test_zhipu_model(self):
        assert "glm" in DEFAULT_MODELS["zhipu"]

    def test_gemini_model(self):
        assert "gemini" in DEFAULT_MODELS["gemini"]


class TestGetAvailableProviders:
    """Tests for get_available_providers function."""

    def test_returns_list(self):
        providers = get_available_providers()
        assert isinstance(providers, list)

    def test_contains_providers(self):
        providers = get_available_providers()
        # At least some providers should be available
        assert len(providers) > 0


class TestCreateProvider:
    """Tests for create_provider function."""

    def test_invalid_provider(self):
        with pytest.raises(ValueError) as exc_info:
            create_provider("nonexistent", api_key="test")
        assert "not available" in str(exc_info.value)

    @patch("mother.llm.factory._load_provider_classes")
    def test_creates_provider(self, mock_load):
        mock_provider_class = Mock()
        mock_load.return_value = {"test": mock_provider_class}
        
        create_provider("test", api_key="sk-test", model="test-model")
        
        mock_provider_class.assert_called_once_with(
            api_key="sk-test",
            model="test-model",
        )


class TestGetProviderForSettings:
    """Tests for get_provider_for_settings function."""

    def test_missing_api_key(self):
        settings = Mock()
        settings.ai_provider = "anthropic"
        settings.anthropic_api_key = None
        settings.openai_api_key = None
        settings.zhipu_api_key = None
        settings.gemini_api_key = None
        
        with pytest.raises(ValueError) as exc_info:
            get_provider_for_settings(settings)
        assert "API key not configured" in str(exc_info.value)

    @patch("mother.llm.factory.create_provider")
    def test_creates_provider_from_settings(self, mock_create):
        settings = Mock()
        settings.ai_provider = "openai"
        settings.openai_api_key = "sk-test"
        settings.anthropic_api_key = None
        settings.zhipu_api_key = None
        settings.gemini_api_key = None
        settings.llm_model = "gpt-4"
        
        get_provider_for_settings(settings)
        
        mock_create.assert_called_once_with(
            provider_name="openai",
            api_key="sk-test",
            model="gpt-4",
        )

    @patch("mother.llm.factory.create_provider")
    def test_uses_claude_model_fallback(self, mock_create):
        settings = Mock()
        settings.ai_provider = "anthropic"
        settings.anthropic_api_key = "sk-ant-test"
        settings.openai_api_key = None
        settings.zhipu_api_key = None
        settings.gemini_api_key = None
        settings.llm_model = None
        settings.claude_model = "claude-3-opus"
        
        get_provider_for_settings(settings)
        
        mock_create.assert_called_once_with(
            provider_name="anthropic",
            api_key="sk-ant-test",
            model="claude-3-opus",
        )


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def test_provider_type(self):
        from mother.llm.providers.anthropic import AnthropicProvider
        
        provider = AnthropicProvider(api_key="test", model="claude-3")
        assert provider.provider_type == ProviderType.ANTHROPIC

    def test_convert_tool_schema_passthrough(self):
        from mother.llm.providers.anthropic import AnthropicProvider
        
        provider = AnthropicProvider(api_key="test", model="claude-3")
        schema = {"name": "test", "description": "Test tool"}
        result = provider.convert_tool_schema(schema)
        assert result == schema

    def test_format_tool_result(self):
        from mother.llm.providers.anthropic import AnthropicProvider
        
        provider = AnthropicProvider(api_key="test", model="claude-3")
        result = ToolResult(tool_call_id="call_123", content="Success")
        
        formatted = provider.format_tool_result(result)
        
        assert formatted["type"] == "tool_result"
        assert formatted["tool_use_id"] == "call_123"
        assert formatted["content"] == "Success"


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    def test_provider_type(self):
        from mother.llm.providers.openai import OpenAIProvider
        
        provider = OpenAIProvider(api_key="test", model="gpt-4")
        assert provider.provider_type == ProviderType.OPENAI

    def test_sanitize_tool_name(self):
        from mother.llm.providers.openai import OpenAIProvider
        
        assert OpenAIProvider._sanitize_tool_name("plugin.command") == "plugin__command"
        assert OpenAIProvider._sanitize_tool_name("simple") == "simple"

    def test_restore_tool_name(self):
        from mother.llm.providers.openai import OpenAIProvider
        
        assert OpenAIProvider._restore_tool_name("plugin__command") == "plugin.command"
        assert OpenAIProvider._restore_tool_name("simple") == "simple"

    def test_convert_tool_schema(self):
        from mother.llm.providers.openai import OpenAIProvider
        
        provider = OpenAIProvider(api_key="test", model="gpt-4")
        schema = {
            "name": "test.tool",
            "description": "Test description",
            "input_schema": {
                "type": "object",
                "properties": {"arg1": {"type": "string"}},
            },
        }
        
        result = provider.convert_tool_schema(schema)
        
        assert result["type"] == "function"
        assert result["function"]["name"] == "test__tool"
        assert result["function"]["description"] == "Test description"

    def test_format_tool_result(self):
        from mother.llm.providers.openai import OpenAIProvider
        
        provider = OpenAIProvider(api_key="test", model="gpt-4")
        result = ToolResult(tool_call_id="call_123", content="Success")
        
        formatted = provider.format_tool_result(result)
        
        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == "call_123"


class TestZhipuProvider:
    """Tests for ZhipuProvider."""

    def test_provider_type(self):
        from mother.llm.providers.zhipu import ZhipuProvider
        
        provider = ZhipuProvider(api_key="test", model="glm-4")
        assert provider.provider_type == ProviderType.ZHIPU

    def test_convert_tool_schema(self):
        from mother.llm.providers.zhipu import ZhipuProvider
        
        provider = ZhipuProvider(api_key="test", model="glm-4")
        schema = {
            "name": "test.tool",
            "description": "Test description",
            "input_schema": {"type": "object", "properties": {}},
        }
        
        result = provider.convert_tool_schema(schema)
        
        assert result["type"] == "function"
        assert result["function"]["name"] == "test__tool"


class TestGeminiProvider:
    """Tests for GeminiProvider."""

    def test_provider_type(self):
        from mother.llm.providers.gemini import GeminiProvider
        
        provider = GeminiProvider(api_key="test", model="gemini-pro")
        assert provider.provider_type == ProviderType.GEMINI

    def test_convert_tool_schema(self):
        from mother.llm.providers.gemini import GeminiProvider
        
        provider = GeminiProvider(api_key="test", model="gemini-pro")
        schema = {
            "name": "test_tool",
            "description": "Test description",
            "input_schema": {"type": "object", "properties": {}},
        }
        
        result = provider.convert_tool_schema(schema)
        
        assert result["name"] == "test_tool"
        assert result["description"] == "Test description"
