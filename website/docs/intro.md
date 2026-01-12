---
sidebar_position: 1
slug: /
---

# Welcome to Mother AI OS

Mother AI OS is an **extensible AI agent operating system** that orchestrates CLI tools via natural language.

## What is Mother AI OS?

Mother AI OS bridges the gap between human intent and system operations. Instead of memorizing complex command-line syntax, you simply describe what you want to accomplish in plain English.

```bash
# Instead of this:
find . -name "*.py" -type f -exec wc -l {} + | sort -rn | head -10

# You say this:
"Show me the 10 largest Python files by line count"
```

## Key Features

- **Natural Language Interface** - Describe tasks in plain English
- **Multi-LLM Provider Support** - Choose from Anthropic Claude, OpenAI, Zhipu GLM-4, or Google Gemini
- **Plugin Architecture** - 14 built-in plugins with 116+ capabilities, plus PyPI-installable extensions
- **Privacy & Anonymity** - Tor network integration for anonymous browsing and .onion access
- **Security Model** - Permission-based capability system with confirmation for destructive actions
- **Audit & Compliance** - Every action logged with timestamp, parameters, and result
- **Production Ready** - FastAPI server with REST API

## Multi-LLM Provider Support

Choose your preferred AI backend:

| Provider | Default Model |
|----------|---------------|
| **Anthropic Claude** | claude-sonnet-4-20250514 |
| **OpenAI GPT** | gpt-4-turbo-preview |
| **Zhipu GLM-4** | glm-4 |
| **Google Gemini** | gemini-1.5-pro |

```bash
# Switch providers with a single environment variable
export AI_PROVIDER=openai
export OPENAI_API_KEY=sk-...
mother serve
```

## Quick Example

```python
import httpx

response = httpx.post(
    "http://localhost:8080/command",
    json={"command": "List all Python files in the src directory"}
)

print(response.json()["response"])
# Found 12 Python files:
# - main.py
# - agent.py
# ...
```

## Built-in Plugins

Mother AI OS v0.3.0 comes with **14 built-in plugins** and **116+ capabilities**:

| Category | Plugins |
|----------|---------|
| **Core** | filesystem, shell, web, email, pdf, tasks, datacraft |
| **Communication** | transmit (email, fax, postal, beA) |
| **Privacy** | tor, tor-shell (anonymous browsing, .onion sites) |
| **Optional** | taxlord, leads, google-docs |

See the [full plugin documentation](/docs/plugins/built-in) for all capabilities.

## Getting Started

Ready to try Mother AI OS? Follow our [installation guide](/docs/getting-started/installation) to get up and running in minutes.

## Open Source

Mother AI OS is [MIT licensed](https://github.com/Mother-AI-OS/mother/blob/main/LICENSE) and open source. We welcome contributions!

- [GitHub Repository](https://github.com/Mother-AI-OS/mother)
- [Report Issues](https://github.com/Mother-AI-OS/mother/issues)
- [Discussions](https://github.com/Mother-AI-OS/mother/discussions)
