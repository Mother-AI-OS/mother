# Mother AI OS

**The AI agent operating system built by a lawyer, for organizations that need control.**

[![CI](https://github.com/Mother-AI-OS/mother/actions/workflows/ci.yml/badge.svg)](https://github.com/Mother-AI-OS/mother/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-74%25-green)](https://github.com/Mother-AI-OS/mother)
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
- Configuring your LLM provider and API key
- Setting up email accounts (optional)
- Enabling optional features

### Multi-LLM Provider Support

Mother supports multiple LLM providers. Choose your preferred AI backend:

| Provider | Environment Variable | Default Model |
|----------|---------------------|---------------|
| **Anthropic Claude** | `AI_PROVIDER=anthropic` | claude-sonnet-4-20250514 |
| **OpenAI GPT** | `AI_PROVIDER=openai` | gpt-4-turbo-preview |
| **Zhipu GLM-4** | `AI_PROVIDER=zhipu` | glm-4 |
| **Google Gemini** | `AI_PROVIDER=gemini` | gemini-1.5-pro |

```bash
# Use OpenAI instead of Anthropic
export AI_PROVIDER=openai
export OPENAI_API_KEY=sk-...
mother serve
```

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
| **tor** | anonymous browsing, .onion sites, Tor proxy |
| **tor-shell** | curl/wget/ssh/nmap through Tor network |
| **taxlord** | German tax & document management (optional) |
| **leads** | German tender discovery (optional) |
| **google-docs** | Google Docs templates (optional) |

### Ecosystem: Tool Repos

Mother is designed to work **standalone** with its built-in plugins. However, it can also integrate with specialized **tool repos** — independent applications that provide additional capabilities.

```
/projects/                          # Your development root
├── mother/                         # Mother AI OS (this repo)
│   └── Built-in: filesystem, email, shell, web, pdf, tasks, tor
│
├── contentcraft/                   # Standalone: AI content creation
├── datacraft/                      # Standalone: Document processing
├── mailcraft/                      # Standalone: Email management
├── taxlord/                        # Standalone: Tax & bookkeeping
├── leadengine/                     # Standalone: Lead generation
└── ...                             # Your own tools
```

**Key principles:**
- Each tool repo has its own CLI/API and works independently
- Mother provides a unified AI interface to these tools (optional)
- Tool repos are never required — Mother works fine without them
- Integration modes: Python plugin, CLI wrapper, HTTP service, Docker

| Tool Repo | What It Does | Integration |
|-----------|--------------|-------------|
| [contentcraft](../contentcraft) | AI content for social media, blogs | CLI wrapper |
| [datacraft](../datacraft) | Document parsing, embeddings, search | Python plugin |
| [mailcraft](../mailcraft) | Email management with LLM categorization | CLI wrapper |
| [taxlord](../taxlord) | German tax, ELSTER, invoices | HTTP service |
| [leadengine](../leadengine) | German tender discovery | CLI wrapper |

**Learn more:**
- [Ecosystem Overview](docs/ecosystem/OVERVIEW.md) — Architecture and catalog
- [Integration Contract](docs/ecosystem/INTEGRATION_CONTRACT.md) — Make your tool Mother-compatible

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

### Docker

Run Mother in a container with all security defaults enabled:

```bash
# Quick start with Docker Compose
git clone https://github.com/Mother-AI-OS/mother.git
cd mother
cp .env.example .env
# Edit .env with your API keys (AI_PROVIDER, ANTHROPIC_API_KEY, etc.)
docker compose up -d
```

Or build and run manually:

```bash
# Build the image
docker build -t mother-ai-os:latest .

# Run with environment variables
docker run -d \
  --name mother \
  -p 8080:8080 \
  -e AI_PROVIDER=anthropic \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e MOTHER_API_KEY=your-secret-key \
  -v mother-logs:/app/logs \
  -v mother-workspace:/app/workspace \
  mother-ai-os:latest
```

The Docker image includes:
- **Non-root user** for security
- **Health check** at `/health`
- **Security defaults**: `MOTHER_SAFE_MODE=true`, `MOTHER_SANDBOX_MODE=true`
- **Persistent volumes** for logs and workspace

### systemd (Production)

For production Linux deployments, use the included systemd unit file:

```bash
# Create service user and directories
sudo useradd -r -s /bin/false mother
sudo mkdir -p /etc/mother /var/log/mother /var/lib/mother
sudo chown -R mother:mother /var/log/mother /var/lib/mother

# Install Mother
sudo pip install mother-ai-os

# Configure environment
sudo cp .env.example /etc/mother/environment
sudo chmod 600 /etc/mother/environment
# Edit /etc/mother/environment with your API keys

# Install and start service
sudo cp mother.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mother
sudo systemctl start mother

# View logs
journalctl -u mother -f
```

The systemd unit includes:
- **Security hardening**: `NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`
- **Automatic restart** on failure with rate limiting
- **Resource limits** for file descriptors and processes
- **Dedicated service user** with minimal permissions

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
export MOTHER_API_KEY="your-secret-key"  # API authentication

# LLM Provider (choose one)
export AI_PROVIDER="anthropic"           # anthropic, openai, zhipu, or gemini
export ANTHROPIC_API_KEY="sk-ant-..."    # For Anthropic Claude
export OPENAI_API_KEY="sk-..."           # For OpenAI GPT
export ZHIPU_API_KEY="..."               # For Zhipu GLM-4
export GEMINI_API_KEY="..."              # For Google Gemini

# Optional
export LLM_MODEL="claude-sonnet-4-20250514"  # Override default model
export MOTHER_HOST="127.0.0.1"
export MOTHER_PORT="8080"
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
