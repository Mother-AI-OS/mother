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
- **Plugin Architecture** - Extend with PyPI-installable plugins
- **Multiple Backends** - Python, CLI, Docker, HTTP execution
- **Security Model** - Permission-based capability system
- **Production Ready** - FastAPI server with REST API

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

Mother AI OS comes with three powerful built-in plugins:

| Plugin | Description |
|--------|-------------|
| **filesystem** | Read, write, copy, move files and directories |
| **shell** | Execute commands and scripts safely |
| **web** | HTTP requests, downloads, link extraction |

## Getting Started

Ready to try Mother AI OS? Follow our [installation guide](/docs/getting-started/installation) to get up and running in minutes.

## Open Source

Mother AI OS is [MIT licensed](https://github.com/Mother-AI-OS/mother/blob/main/LICENSE) and open source. We welcome contributions!

- [GitHub Repository](https://github.com/Mother-AI-OS/mother)
- [Report Issues](https://github.com/Mother-AI-OS/mother/issues)
- [Discussions](https://github.com/Mother-AI-OS/mother/discussions)
