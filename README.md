# Mother AI OS

An extensible AI agent operating system that orchestrates CLI tools via natural language.

[![PyPI version](https://badge.fury.io/py/mother-ai-os.svg)](https://badge.fury.io/py/mother-ai-os)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Natural Language Interface** - Talk to your tools in plain English
- **Plugin Architecture** - Extensible system with PyPI-installable plugins
- **Multiple Backends** - Python, CLI, Docker, and HTTP execution
- **Built-in Plugins** - Filesystem, shell, and web operations out of the box
- **Security Model** - Permission-based capability system
- **FastAPI Server** - RESTful API with streaming support

## Installation

```bash
pip install mother-ai-os
```

Or install from source:

```bash
git clone https://github.com/Mother-AI-OS/mother.git
cd mother
pip install -e .
```

## Quick Start

1. **Configure environment:**

```bash
cp .env.example .env
# Edit .env with your API keys:
# ANTHROPIC_API_KEY=sk-ant-...
# MOTHER_API_KEY=your-secret-key
```

2. **Start the server:**

```bash
mother serve
# Or with options:
mother serve --host 0.0.0.0 --port 8080
```

3. **Send commands:**

```bash
curl -X POST http://localhost:8080/command \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"command": "List files in my home directory"}'
```

## CLI Commands

```bash
# Server
mother serve              # Start the server
mother status             # Show system status

# Plugin management
mother plugin list        # List available plugins
mother plugin info <name> # Show plugin details
mother plugin install <pkg>   # Install from PyPI
mother plugin uninstall <pkg> # Remove a plugin
mother plugin search [query]  # Search PyPI for plugins
```

## Built-in Plugins

| Plugin | Capabilities |
|--------|-------------|
| **filesystem** | read_file, write_file, list_directory, file_info, search_files |
| **shell** | run_command |
| **web** | fetch_url |

## Creating Plugins

Plugins are Python packages that register via entry points. Create a `mother-plugin.yaml` manifest:

```yaml
schema_version: "1.0"

plugin:
  name: my-plugin
  version: 1.0.0
  description: My custom plugin
  author: Your Name

capabilities:
  - name: do_something
    description: Does something useful
    parameters:
      - name: input
        type: string
        required: true

execution:
  type: python
  python:
    module: my_plugin
    class: MyPlugin
```

Then implement the plugin:

```python
from mother.plugins import PluginBase, PluginResult

class MyPlugin(PluginBase):
    async def execute(self, capability: str, params: dict) -> PluginResult:
        if capability == "do_something":
            result = self._do_something(params["input"])
            return PluginResult.success_result(data={"result": result})
        raise ValueError(f"Unknown capability: {capability}")
```

Register in `pyproject.toml`:

```toml
[project.entry-points."mother.plugins"]
my-plugin = "my_plugin:MyPlugin"
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/command` | POST | Execute a natural language command |
| `/tools` | GET | List available tools |
| `/health` | GET | Health check |
| `/stream` | POST | Stream command execution |

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key | Required |
| `MOTHER_API_KEY` | API authentication key | Required |
| `CLAUDE_MODEL` | Claude model to use | claude-sonnet-4-20250514 |
| `API_HOST` | Server host | 127.0.0.1 |
| `API_PORT` | Server port | 8080 |
| `OPENAI_API_KEY` | OpenAI key (for memory) | Optional |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy mother

# Linting
ruff check mother
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

David Sanker ([@lawkraft](https://github.com/lawkraft))
