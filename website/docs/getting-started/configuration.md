---
sidebar_position: 2
---

# Configuration

Configure Mother AI OS with your LLM provider and preferences.

## LLM Provider Selection

Mother supports multiple LLM providers. Choose your preferred AI backend:

| Provider | `AI_PROVIDER` | API Key Variable | Default Model |
|----------|---------------|------------------|---------------|
| **Anthropic Claude** | `anthropic` | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 |
| **OpenAI GPT** | `openai` | `OPENAI_API_KEY` | gpt-4-turbo-preview |
| **Zhipu GLM-4** | `zhipu` | `ZHIPU_API_KEY` | glm-4 |
| **Google Gemini** | `gemini` | `GEMINI_API_KEY` | gemini-1.5-pro |

## Environment Variables

Create a `.env` file in your project root (or set environment variables):

```bash
# Required: API key for authenticating requests
MOTHER_API_KEY=your-secret-key

# LLM Provider (default: anthropic)
AI_PROVIDER=anthropic

# API Key for your chosen provider
ANTHROPIC_API_KEY=sk-ant-api03-...   # For Anthropic
# OPENAI_API_KEY=sk-...              # For OpenAI
# ZHIPU_API_KEY=...                  # For Zhipu
# GEMINI_API_KEY=...                 # For Gemini

# Optional: Override default model
LLM_MODEL=claude-sonnet-4-20250514

# Optional: Server configuration
MOTHER_HOST=127.0.0.1
MOTHER_PORT=8080
```

## Quick Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Then edit `.env` with your API keys:

```bash
nano .env
# or
code .env
```

## Using Different Providers

### Anthropic Claude (Default)

```bash
export AI_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
mother serve
```

### OpenAI GPT

```bash
export AI_PROVIDER=openai
export OPENAI_API_KEY=sk-...
mother serve
```

### Google Gemini

```bash
export AI_PROVIDER=gemini
export GEMINI_API_KEY=...
mother serve
```

### Zhipu GLM-4

```bash
export AI_PROVIDER=zhipu
export ZHIPU_API_KEY=...
mother serve
```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `AI_PROVIDER` | LLM provider to use | `anthropic` |
| `MOTHER_API_KEY` | API authentication key | **Required** |
| `ANTHROPIC_API_KEY` | Anthropic API key | Required for `anthropic` |
| `OPENAI_API_KEY` | OpenAI API key | Required for `openai` |
| `ZHIPU_API_KEY` | Zhipu API key | Required for `zhipu` |
| `GEMINI_API_KEY` | Google Gemini API key | Required for `gemini` |
| `LLM_MODEL` | Override default model | Provider default |
| `MOTHER_HOST` | Server host | `127.0.0.1` |
| `MOTHER_PORT` | Server port | `8080` |
| `MOTHER_DEBUG` | Enable debug logging | `false` |

## Verify Configuration

Start the server to verify your configuration:

```bash
mother serve
```

You should see:

```
INFO - Starting Mother Agent v0.3.0
INFO - Agent initialized with provider: anthropic
INFO - Plugin system: 116 capabilities loaded
```

## Next Steps

Configuration complete! Try [your first command](/docs/getting-started/first-command).
