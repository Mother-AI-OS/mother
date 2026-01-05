---
sidebar_position: 2
---

# Configuration

Configure Mother AI OS with your API keys and preferences.

## Environment Variables

Create a `.env` file in your project root (or set environment variables):

```bash
# Required: Your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-api03-...

# Required: API key for authenticating requests
MOTHER_API_KEY=your-secret-key

# Optional: Claude model to use (default: claude-sonnet-4-20250514)
CLAUDE_MODEL=claude-sonnet-4-20250514

# Optional: Server configuration
MOTHER_HOST=127.0.0.1
MOTHER_PORT=8080

# Optional: For semantic memory (requires OpenAI)
OPENAI_API_KEY=sk-...
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

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key | **Required** |
| `MOTHER_API_KEY` | API authentication key | **Required** |
| `CLAUDE_MODEL` | Claude model to use | `claude-sonnet-4-20250514` |
| `MOTHER_HOST` | Server host | `127.0.0.1` |
| `MOTHER_PORT` | Server port | `8080` |
| `OPENAI_API_KEY` | OpenAI key for memory embeddings | Optional |
| `MOTHER_DEBUG` | Enable debug logging | `false` |

## Verify Configuration

Start the server to verify your configuration:

```bash
mother serve
```

You should see:

```
🚀 Mother AI OS running at http://127.0.0.1:8080
📚 Loaded 3 plugins: filesystem, shell, web
```

## Next Steps

Configuration complete! Try [your first command](/docs/getting-started/first-command).
