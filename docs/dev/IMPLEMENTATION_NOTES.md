# Enterprise Readiness Implementation Notes

## Step 0: Repository Orientation

### Directory Structure

```
mother/
├── mother/                    # Core application
│   ├── agent/                 # Agent logic (core.py, cognitive.py, session.py)
│   ├── api/                   # FastAPI routes and schemas
│   ├── cli/                   # CLI interface
│   ├── config/                # Settings (pydantic-settings)
│   ├── llm/                   # Multi-LLM provider abstraction
│   │   └── providers/         # Anthropic, OpenAI, Zhipu, Gemini
│   ├── memory/                # Semantic memory with vector search
│   ├── parsers/               # Output parsers
│   ├── plugins/               # Plugin system
│   │   └── builtin/           # Built-in plugins
│   └── tools/                 # Legacy tool wrappers
├── tests/                     # Test suite
├── website/                   # Documentation site (Docusaurus)
│   └── docs/                  # Markdown documentation
├── data/                      # LanceDB vector storage
└── .github/workflows/         # CI/CD
```

### Key Files and Their Roles

| File | Purpose |
|------|---------|
| `mother/agent/core.py` | Main agent loop, tool execution, confirmation handling |
| `mother/api/routes.py` | REST API endpoints |
| `mother/api/auth.py` | API key authentication (basic) |
| `mother/config/settings.py` | Configuration via environment variables |
| `mother/plugins/registry.py` | Plugin registration and capability tracking |
| `mother/plugins/manifest.py` | Plugin manifest schema (Pydantic models) |
| `mother/plugins/executor.py` | Plugin execution coordination |
| `mother/plugins/sandbox.py` | Basic sandbox interface (not fully implemented) |
| `mother/plugins/builtin/shell.py` | Shell command execution plugin |
| `mother/plugins/builtin/tor.py` | Tor/darknet access plugin |
| `mother/plugins/builtin/filesystem.py` | File operations plugin |
| `mother/plugins/builtin/web.py` | Web/HTTP operations plugin |
| `mother/tools/registry.py` | Tool registry (legacy + plugins) |

### Current Security Mechanisms

1. **Authentication** (`mother/api/auth.py`):
   - API key via `X-API-Key` header
   - Optional (can be disabled with `MOTHER_REQUIRE_AUTH=false`)
   - Single static key (no key rotation, no multi-tenant)

2. **Confirmation System** (`mother/agent/core.py`):
   - Capabilities can declare `confirmation_required=True`
   - User must confirm destructive actions via `/confirm` endpoint
   - No hard policy enforcement - only prompts

3. **Shell Plugin Security** (`mother/plugins/builtin/shell.py`):
   - Basic blocked command list (configurable)
   - Dangerous pattern detection (rm -rf /, fork bomb, etc.)
   - Optional working directory restrictions
   - **NOT enforced by default** - just checks in execute()

4. **Logging** (scattered):
   - Python logging module used throughout
   - No structured audit logging
   - No redaction of sensitive data
   - Log files in `~/.local/share/mother/logs/`

### Current Risks and Gaps

| Risk | Current State | Required Fix |
|------|---------------|--------------|
| **Unrestricted shell access** | Shell plugin enabled by default, any command allowed | Policy engine with command allowlist |
| **No policy enforcement** | Confirmation is advisory only | Hard policy gate before execution |
| **Filesystem access unrestricted** | Can read/write anywhere | Safe working directory + path allowlist |
| **Network egress unrestricted** | Web plugin can fetch any URL | Domain/IP allowlist |
| **No audit logging** | Basic Python logs only | Structured JSONL audit trail |
| **Secrets in logs** | Params logged as-is | Redaction rules |
| **No sandboxing** | Runs in main process | Container/jail isolation |
| **Tor/darknet enabled by default** | High-risk plugin loads on startup | Disabled by default, explicit enable |
| **No schema validation on startup** | Plugin manifests not validated | Strict validation + versioning |

### Plugin Count Inconsistency

The documentation claims vary:
- Some places mention "3 built-in plugins"
- Server logs show 14 plugins discovered
- Built-in plugins directory has: datacraft, email, german, google, tasks, transmit + shell, tor, filesystem, web, pdf, taxlord, leads, google-docs

**Fix needed**: Standardize on a packaging matrix showing core vs optional vs premium plugins.

---

## Implementation Plan

### A) Policy Engine

**Files to create:**
- `mother/policy/__init__.py`
- `mother/policy/engine.py` - PolicyEngine class
- `mother/policy/models.py` - PolicyDecision, Rule, Condition models
- `mother/policy/loader.py` - YAML policy file loader
- `mother/policy/conditions.py` - Filesystem, Command, Network condition evaluators

**Files to modify:**
- `mother/config/settings.py` - Add MOTHER_POLICY_PATH, MOTHER_SAFE_MODE
- `mother/plugins/executor.py` - Add policy check before execution
- `mother/agent/core.py` - Return policy errors to client

### B) Safe by Default Mode

**Files to modify:**
- `mother/config/settings.py` - Add MOTHER_SAFE_MODE=1 default
- `mother/plugins/loader.py` - Skip high-risk plugins in safe mode
- `mother/policy/defaults.py` - Default safe mode policy

### C) Capability Schema Validation

**Files to modify:**
- `mother/plugins/manifest.py` - Add risk_tier, enabled_by_default, api_version
- `mother/plugins/loader.py` - Strict validation on startup
- `mother/__init__.py` - Add CAPABILITY_API_VERSION

### D) Enterprise Audit Logging

**Files to create:**
- `mother/audit/__init__.py`
- `mother/audit/logger.py` - AuditLogger class with JSONL rotation
- `mother/audit/redaction.py` - SecretRedactor class
- `mother/audit/models.py` - AuditEntry, ToolCallAudit models

**Files to modify:**
- `mother/config/settings.py` - Add MOTHER_AUDIT_LOG_PATH
- `mother/agent/core.py` - Log all tool calls and decisions
- `mother/api/routes.py` - Log request/response metadata

### E) Sandbox Mode

**Files to create:**
- `mother/sandbox/__init__.py`
- `mother/sandbox/runner.py` - SandboxRunner interface
- `mother/sandbox/docker.py` - DockerSandbox implementation
- `mother/sandbox/subprocess.py` - SubprocessJail fallback

**Files to modify:**
- `mother/config/settings.py` - Add MOTHER_SANDBOX_MODE
- `mother/plugins/builtin/shell.py` - Route through sandbox
- `mother/plugins/builtin/filesystem.py` - Route through sandbox

### F) High-risk Plugins Disabled by Default

**Files to modify:**
- `mother/plugins/builtin/shell.py` - Set enabled_by_default=False, risk_tier=high
- `mother/plugins/builtin/tor.py` - Set enabled_by_default=False, risk_tier=high
- `mother/plugins/builtin/tor_shell.py` - Set enabled_by_default=False, risk_tier=high
- `mother/plugins/loader.py` - Honor enabled_by_default flag

### G) Documentation

**Files to create:**
- `docs/security/threat-model.md`
- `docs/security/security-whitepaper.md`
- `docs/security/high-risk-capabilities.md`
- `docs/product/packaging-matrix.md`

**Files to modify:**
- `website/docs/concepts/security.md` - Reference new docs
- `README.md` - Add enterprise security section

### H) Demo + Tests

**Files to create:**
- `examples/enterprise_readiness_demo/policy.yaml`
- `examples/enterprise_readiness_demo/run_demo.py`
- `tests/test_policy_engine.py`
- `tests/test_audit_logging.py`
- `tests/test_safe_mode.py`
- `tests/test_sandbox.py`

---

## Progress Tracking

- [ ] A) Policy Engine
- [ ] B) Safe by Default Mode
- [ ] C) Capability Schema Validation
- [ ] D) Enterprise Audit Logging
- [ ] E) Sandbox Mode
- [ ] F) High-risk Plugins Config
- [ ] G) Documentation
- [ ] H) Demo + Tests
