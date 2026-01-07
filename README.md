# Mother AI OS

**The AI agent operating system built by a lawyer, for organizations that need control.**

[![CI](https://github.com/Mother-AI-OS/mother/actions/workflows/ci.yml/badge.svg)](https://github.com/Mother-AI-OS/mother/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-69%25-yellowgreen)](https://github.com/Mother-AI-OS/mother)
[![PyPI version](https://badge.fury.io/py/mother-ai-os.svg)](https://badge.fury.io/py/mother-ai-os)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

Mother is an extensible AI agent system that orchestrates CLI tools via natural language. Unlike other AI frameworks, Mother was designed from day one for **auditability**, **permission control**, and **compliance** — because that's what enterprises actually need.

```
You: "Find all contracts expiring this quarter and email a summary to the legal team"

Mother: [filesystem.search] → [filter by date] → [generate summary] → [email.send]
        ↓
        Every action logged. Every permission checked. Every step auditable.
```

## Why Mother?

Most AI agent frameworks are built by developers for developers. Mother was built by a **practicing lawyer and legal engineer** who understands that organizations need:

| Requirement | How Mother Delivers |
|-------------|---------------------|
| **Audit Trails** | Every action logged with timestamp, user, parameters, and result |
| **Permission Model** | Capability-based security — agents only do what they're allowed to |
| **Explainability** | Execution plans shown before destructive actions |
| **Compliance-Ready** | Integrates with [UAPK](https://github.com/UAPK/gateway) governance layer |

### Who Is This For?

- **Legal & Compliance Teams** — Automate document workflows with full audit trails
- **Regulated Industries** — Finance, healthcare, legal tech requiring governance
- **Enterprise IT** — Deploy AI agents you can actually control
- **Developers** — Build AI automation without reinventing security

---

## Quick Start

```bash
# Install
pip install mother-ai-os

# First-time setup (interactive wizard)
mother setup

# Check configuration status
mother status

# Run the server
mother serve
```

The setup wizard will guide you through:
- Configuring your Anthropic API key
- Setting up email accounts (optional)
- Enabling optional features

Then send natural language commands:

```bash
curl -X POST http://localhost:8080/command \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"command": "List all PDF files modified this week"}'
```

Response:
```json
{
  "text": "Found 3 PDF files modified this week: contract_v2.pdf, invoice_dec.pdf, memo.pdf",
  "tools_used": ["filesystem.list_directory", "filesystem.file_info"],
  "audit_id": "exec_7f3a9c2b"
}
```

---

## Core Features

### Natural Language → Controlled Execution

```
┌─────────────────────────────────────────────────────────────┐
│                     Natural Language                         │
│              "Send the quarterly report to finance"          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Mother Agent (Claude)                     │
│     Understands intent → Plans execution → Checks perms      │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │filesystem│    │  email   │    │  audit   │
    │  plugin  │    │  plugin  │    │   log    │
    └──────────┘    └──────────┘    └──────────┘
```

### Built-in Plugins

| Plugin | Capabilities |
|--------|-------------|
| **filesystem** | read, write, copy, move, delete, list, search |
| **shell** | run commands, scripts, environment info |
| **web** | HTTP requests, fetch, download, parse URLs |
| **email** | send, list, read, search emails (IMAP/SMTP) |
| **pdf** | merge, split, extract, rotate, compress PDFs |
| **datacraft** | parse documents, search, extract tables |
| **tasks** | add, list, complete, prioritize tasks |
| **transmit** | send documents via email, fax, post, beA |
| **taxlord** | German tax & document management (optional) |
| **leads** | German tender discovery (optional) |
| **google-docs** | Google Docs templates (optional) |

### Permission & Confirmation System

Destructive actions require explicit confirmation:

```
Mother: I'll delete 47 files matching "*.tmp". Proceed? [y/N]

Plan:
  1. filesystem.list_directory → find *.tmp files
  2. filesystem.delete → remove each file (REQUIRES CONFIRMATION)
```

---

## Installation

### From PyPI

```bash
pip install mother-ai-os
```

### From Source

```bash
git clone https://github.com/Mother-AI-OS/mother.git
cd mother
pip install -e .
```

### Configuration

The recommended way to configure Mother is via the setup wizard:

```bash
mother setup    # Interactive first-time configuration
```

This creates `~/.config/mother/credentials.env` with your API keys.

#### Manual Configuration

You can also set environment variables directly:

```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-..."    # Claude API access
export MOTHER_API_KEY="your-secret-key"  # API authentication

# Optional
export CLAUDE_MODEL="claude-sonnet-4-20250514"
export MOTHER_HOST="127.0.0.1"
export MOTHER_PORT="8080"
export OPENAI_API_KEY="..."              # For memory/embeddings
```

#### Email Configuration

Add email accounts for the email plugin:

```bash
mother email add       # Interactive account setup
mother email list      # Show configured accounts
mother email test      # Verify connection
```

Credentials are stored securely using your system keyring.

---

## CLI Reference

```bash
# Setup & Configuration
mother setup                    # First-time setup wizard
mother status                   # System health & config check
mother credentials list         # Show credential status
mother credentials set KEY VAL  # Set a credential

# Email Management
mother email add                # Add email account (interactive)
mother email list               # List configured accounts
mother email remove NAME        # Remove an account
mother email test [NAME]        # Test account connection

# Server
mother serve                    # Start the API server
mother serve --port 9000        # Custom port

# Plugin Management
mother plugin list              # Show installed plugins
mother plugin info <name>       # Plugin details
mother plugin install <pkg>     # Install from PyPI
mother plugin uninstall <pkg>   # Remove plugin
mother plugin search <query>    # Find plugins
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/command` | POST | Execute natural language command |
| `/stream` | POST | Stream execution (SSE) |
| `/tools` | GET | List available capabilities |
| `/health` | GET | Health check |

### Example: Execute Command

```bash
curl -X POST http://localhost:8080/command \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "Read config.yaml and summarize the settings",
    "confirm_destructive": false
  }'
```

---

## Creating Plugins

Extend Mother with custom capabilities:

### 1. Create Manifest (`mother-plugin.yaml`)

```yaml
schema_version: "1.0"

plugin:
  name: my-plugin
  version: 1.0.0
  description: Custom integration
  author: Your Name

capabilities:
  - name: do_something
    description: Performs a task
    confirmation_required: false
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

### 2. Implement Plugin

```python
from mother.plugins import PluginBase, PluginResult

class MyPlugin(PluginBase):
    async def execute(self, capability: str, params: dict) -> PluginResult:
        if capability == "do_something":
            result = self._process(params["input"])
            return PluginResult.success_result(
                data={"result": result},
                message="Task completed"
            )
        raise ValueError(f"Unknown capability: {capability}")
```

### 3. Register Entry Point

```toml
# pyproject.toml
[project.entry-points."mother.plugins"]
my-plugin = "my_plugin:MyPlugin"
```

---

## Enterprise & Governance

### UAPK Integration

For organizations requiring policy enforcement and audit logging, Mother integrates with [UAPK (Universal AI Processing Key)](https://github.com/UAPK/gateway):

```
┌─────────────────────────────────────────┐
│              UAPK Gateway               │
│   Policy Enforcement │ Audit Logging    │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│              Mother Agent               │
│   Execution │ Plugins │ Memory          │
└─────────────────────────────────────────┘
```

UAPK provides:
- **Policy enforcement** — Define what agents can/cannot do
- **Audit logging** — Immutable record of all AI actions
- **Compliance reporting** — Export logs for regulatory review

### Enterprise Support

Need custom plugins, SLA, or on-premise deployment?

**Contact:** [david@lawkraft.com](mailto:david@lawkraft.com)

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (1,346 tests)
pytest

# Type checking
mypy mother

# Linting
ruff check mother
```

---

## Roadmap

- [ ] Plugin marketplace
- [ ] Cloud dashboard (Pro tier)
- [ ] UAPK deep integration
- [ ] Multi-agent orchestration
- [ ] Workflow templates for legal/finance

See [GitHub Issues](https://github.com/Mother-AI-OS/mother/issues) for detailed roadmap.

---

## About

Mother AI OS was created by [David Sanker](https://github.com/Amakua), a lawyer and legal engineer who builds AI infrastructure for regulated industries.

- **Law Practice:** Partner at [Hucke & Sanker](https://huckesanker.com)
- **Legal Engineering:** [Cleary Gottlieb Steen & Hamilton LLP](https://clearygottlieb.com)
- **AI Consulting:** [Lawkraft](https://lawkraft.com)

### Why "Mother"?

In the film *Alien*, "Mother" is the ship's AI that controls all systems. Unlike that Mother, this one asks for permission before doing anything dangerous.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Use it, fork it, build on it. Just don't blame me if your AI agent goes rogue (that's what [UAPK](https://github.com/UAPK/gateway) is for).

---

<p align="center">
  <strong>Built by a lawyer who codes.</strong><br>
  <a href="https://mother-os.info">Website</a> •
  <a href="https://github.com/Mother-AI-OS/mother/issues">Issues</a> •
  <a href="https://lawkraft.com">Lawkraft</a>
</p>
