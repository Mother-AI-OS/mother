# Mother Ecosystem Overview

> Mother is an AI agent **runtime/orchestrator**. It can work standalone or integrate with specialized tool repos.

---

## Architecture

```
                         ┌─────────────────────────────────┐
                         │       Mother AI OS              │
                         │  ┌───────────────────────────┐  │
                         │  │     Agent Runtime          │  │
                         │  │  • Natural language parse  │  │
                         │  │  • Permission checking     │  │
                         │  │  • Audit logging           │  │
                         │  │  • Memory/session          │  │
                         │  └─────────────┬─────────────┘  │
                         │                │                │
                         │  ┌─────────────┴─────────────┐  │
                         │  │     Plugin System          │  │
                         │  │  PYTHON │ CLI │ HTTP │ ...│  │
                         │  └─────────────┬─────────────┘  │
                         └────────────────┼────────────────┘
                                          │
        ┌─────────────────────────────────┼─────────────────────────────────┐
        │                                 │                                 │
        ▼                                 ▼                                 ▼
┌───────────────┐               ┌───────────────┐               ┌───────────────┐
│   Built-in    │               │   Tool Repos  │               │  User Plugins │
│   Plugins     │               │   (Optional)  │               │   (Custom)    │
│               │               │               │               │               │
│ • filesystem  │               │ • contentcraft│               │ • your-plugin │
│ • email       │               │ • datacraft   │               │               │
│ • shell       │               │ • mailcraft   │               │               │
│ • web         │               │ • taxlord     │               │               │
│ • pdf         │               │ • leadengine  │               │               │
│ • tasks       │               │ • transmit    │               │               │
│ • tor         │               │ • acnjxn      │               │               │
└───────────────┘               └───────────────┘               └───────────────┘
```

---

## Key Concepts

### Mother = Runtime/Orchestrator

Mother provides:
- **Natural language understanding** — Converts user requests to tool calls
- **Permission system** — Capability-based security with confirmation gates
- **Audit logging** — Every action logged with full attribution
- **Memory & sessions** — Semantic memory and conversation context
- **Plugin execution** — Runs Python, CLI, HTTP, or Docker-based tools

Mother does **not** require any sibling tool repos to function. It ships with built-in plugins (filesystem, email, shell, web, pdf, tasks, tor).

### Tool Repos = Standalone Applications

Each tool repo in `/projects/` is:
1. **Independently useful** — Has its own CLI/API, can run without Mother
2. **Optionally integratable** — Can be wrapped as a Mother plugin
3. **Separately maintained** — Its own repo, tests, releases

This means you can:
- Run `taxlord` standalone for tax management
- Run `datacraft` standalone for document processing
- Run `mailcraft` standalone for email operations
- ...and so on

Mother simply provides a **unified AI interface** to these tools if desired.

---

## Tool Repository Catalog

| Repo | Purpose | Standalone Entrypoint | Mother Integration | Risk |
|------|---------|----------------------|-------------------|------|
| **contentcraft** | AI content creation for social media, blogs, YouTube | `content` CLI | CLI wrapper, Python plugin | LOW |
| **datacraft** | Document processing, embeddings, vector search | `datacraft` CLI | CLI wrapper, Python plugin | LOW |
| **mailcraft** | Email management with LLM categorization | `mailcraft` CLI | CLI wrapper, Python plugin | MEDIUM |
| **leadengine** | German tender and lead discovery | `leads` CLI | CLI wrapper, REST API | MEDIUM |
| **lawkraft-transmit** | Document transmission (email, fax, post, beA) | Python library | Python import | MEDIUM |
| **taxlord** | German tax and bookkeeping with ELSTER | `taxlord` CLI, FastAPI | HTTP service, CLI wrapper | HIGH |
| **acnjxn** | Task management with Google Tasks sync | `acnjxn` CLI | CLI wrapper, Python plugin | LOW |
| **helpers** | Utility scripts (pdf-merge, transmit) | Shell scripts | CLI wrappers | LOW |

### Risk Levels Explained

| Level | Meaning | Permissions Typically Required |
|-------|---------|-------------------------------|
| **LOW** | Read-only or local-only operations | `filesystem:read`, `network:external` |
| **MEDIUM** | Writes data or sends communications | `filesystem:write`, `email:send`, `secrets:read` |
| **HIGH** | Financial operations, PII handling | `secrets:write`, financial APIs, tax filings |

---

## Integration Modes

Mother supports four plugin execution types:

### 1. Python Plugin (Recommended)

Direct import and execution of Python classes.

```python
# In tool repo: myrepo/mother_plugin.py
from mother.plugins import PluginBase, PluginResult

class MyRepoPlugin(PluginBase):
    async def execute(self, capability: str, params: dict) -> PluginResult:
        # Your logic here
        return PluginResult.success_result(data={...})
```

**Pros:** Fastest, full access to Python APIs, native error handling
**Cons:** Tool repo must be importable in Mother's environment

### 2. CLI Wrapper

Subprocess execution of command-line tools.

```yaml
# mother-plugin.yaml
execution:
  type: cli
  cli:
    command: datacraft
    args_format: "--{param_name} {value}"
```

**Pros:** Language-agnostic, clean separation, easy to test independently
**Cons:** Slower (subprocess spawn), stdout/stderr parsing needed

### 3. HTTP Service

REST API calls to a running service.

```yaml
# mother-plugin.yaml
execution:
  type: http
  http:
    base_url: http://localhost:9000
    endpoints:
      do_something: POST /api/v1/action
```

**Pros:** True microservice isolation, can run on different hosts
**Cons:** Service must be running, network overhead

### 4. Docker Container

Run tools in isolated containers.

```yaml
# mother-plugin.yaml
execution:
  type: docker
  docker:
    image: myrepo:latest
    command: /app/entrypoint.sh
```

**Pros:** Maximum isolation, reproducible environment
**Cons:** Requires Docker, startup overhead

---

## Recommended Directory Layout

For local development with multiple repos:

```
/projects/                      # Your projects root
├── mother/                     # Mother AI OS (this repo)
│   ├── mother/                 # Python package
│   ├── docs/ecosystem/         # This documentation
│   └── scripts/ecosystem_scan.py  # Local scanner tool
│
├── contentcraft/               # Standalone: content generation
│   ├── contentcraft/           # Python package
│   └── pyproject.toml          # Defines 'content' CLI
│
├── datacraft/                  # Standalone: document processing
├── mailcraft/                  # Standalone: email management
├── leadengine/                 # Standalone: lead generation
├── lawkraft-transmit/          # Standalone: document transmission
├── taxlord/                    # Standalone: tax management
├── acnjxn/                     # Standalone: task management
└── helpers/                    # Utility scripts
```

This layout is **not required**. Repos can live anywhere. The `/projects/` convention is just convenient for local development.

---

## Using Mother Standalone

Mother works perfectly without any sibling repos:

```bash
pip install mother-ai-os
mother setup
mother serve
```

Built-in plugins provide:
- File operations (read, write, list, search)
- Shell commands
- Email (IMAP/SMTP)
- HTTP requests
- PDF manipulation
- Task management
- Tor networking

---

## Adding Tool Repo Integrations

To integrate a tool repo with Mother:

### Option A: Install as Python Package

```bash
cd /projects/datacraft
pip install -e .

# Now Mother can import datacraft modules
```

### Option B: Register as External Plugin

Create a plugin wrapper in `~/.mother/plugins/`:

```
~/.mother/plugins/datacraft/
├── mother-plugin.yaml    # Manifest
└── plugin.py             # Wrapper (if needed)
```

### Option C: Run as HTTP Service

```bash
# Start the tool's API
cd /projects/taxlord
uvicorn taxlord.api.main:app --port 9000

# Configure Mother to call it
export TAXLORD_API_URL=http://localhost:9000
```

---

## Scanning Your Environment

Use the ecosystem scanner to see what's available:

```bash
cd /projects/mother
python scripts/ecosystem_scan.py

# Output:
# Mother Ecosystem Scan
# Root: /projects
#
# Mother Core: /projects/mother (OK)
#
# Tool Repos Found:
#   contentcraft  present  CLI: content
#   datacraft     present  CLI: datacraft
#   mailcraft     present  CLI: mailcraft
#   ...
#
# Missing (optional):
#   (none)
```

Set `MOTHER_PROJECTS_ROOT` to scan a different directory:

```bash
MOTHER_PROJECTS_ROOT=/opt/ai-tools python scripts/ecosystem_scan.py
```

---

## FAQ

### Can I use Mother without any tool repos?
**Yes.** Mother has built-in plugins for common operations. Tool repos are optional enhancements.

### Can I use tool repos without Mother?
**Yes.** Each tool repo has its own CLI or API. They're designed to be useful standalone.

### Do tool repos need to be in /projects/?
**No.** That's a development convention. Tools can be installed via pip from anywhere.

### How do I make my own tool repo Mother-compatible?
See [INTEGRATION_CONTRACT.md](./INTEGRATION_CONTRACT.md) for the specification.

### Is there a central registry of tool repos?
Not yet. For now, tool repos are discovered locally or installed manually.

---

## Next Steps

- [INTEGRATION_CONTRACT.md](./INTEGRATION_CONTRACT.md) — How to make a tool repo Mother-compatible
- [Creating Plugins](../README.md#creating-plugins) — Plugin development guide
- [scripts/ecosystem_scan.py](../../scripts/ecosystem_scan.py) — Local scanner tool

---

*This documentation is part of [Mother AI OS](https://github.com/Mother-AI-OS/mother).*
