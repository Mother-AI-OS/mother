# Mother Integration Contract

> A stable contract for tool repos to be "Mother-compatible"

This document defines what a tool repo should implement to integrate cleanly with Mother AI OS. Following these conventions ensures:
- Consistent user experience
- Proper permission enforcement
- Audit trail attribution
- Configuration discovery

---

## 1. Capability Naming Conventions

### Tool Name

Your tool name should be:
- Lowercase alphanumeric with hyphens
- Start with a letter
- 3-30 characters

```
✓ datacraft
✓ lead-engine
✓ tax-lord
✗ DataCraft (no uppercase)
✗ 123tool (no leading digits)
✗ my_tool (no underscores)
```

### Capability Names

Capabilities (actions your tool can perform) should be:
- Lowercase with underscores
- Verb-first when possible
- Descriptive but concise

```
✓ search_documents
✓ parse_invoice
✓ send_email
✓ list_leads
✗ documentSearch (no camelCase)
✗ do_the_thing (too vague)
```

### Full Capability Identifier

Mother constructs tool names as `{plugin}_{capability}`:

```
datacraft_search_documents
mailcraft_send_email
taxlord_parse_invoice
```

---

## 2. CLI Interface Contract

If your tool provides a CLI, follow these conventions for Mother's CLI wrapper integration.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Permission denied |
| 4 | Resource not found |
| 5 | Timeout |
| 10-19 | Tool-specific errors (document in README) |

### Output Format

Support `--output-format` flag:

```bash
mytool search --query "contracts" --output-format json
mytool search --query "contracts" --output-format text  # human-readable, default
```

**JSON output** should be:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "metadata": {
    "execution_time_ms": 142,
    "version": "1.2.3"
  }
}
```

**Error JSON** should be:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "Document 'contract.pdf' not found",
    "details": { ... }
  }
}
```

### Stdout vs Stderr

- **stdout**: Primary output (data, results)
- **stderr**: Logs, warnings, progress indicators

This allows Mother to capture output cleanly:

```bash
result=$(mytool search --query "x" --output-format json 2>/dev/null)
```

### Common Flags

Implement these standard flags for consistency:

| Flag | Purpose |
|------|---------|
| `--help` | Show usage |
| `--version` | Show version |
| `--output-format` | json, text, csv |
| `--verbose`, `-v` | Increase verbosity |
| `--quiet`, `-q` | Suppress non-essential output |
| `--config` | Path to config file |
| `--dry-run` | Show what would happen without executing |

### Example CLI Structure

```bash
# Good structure
mytool [global-flags] <command> [command-flags] [args]

# Examples
mytool --verbose search --query "contracts" --limit 10
mytool parse-invoice /path/to/invoice.pdf --output-format json
mytool list-leads --source "german-tenders" --since "2024-01-01"
```

---

## 3. HTTP Service Interface

If your tool provides an HTTP API, follow these conventions.

### Base URL

Default to `http://localhost:{port}` where port is tool-specific:

| Tool | Default Port | Environment Variable |
|------|--------------|---------------------|
| taxlord | 9001 | `TAXLORD_PORT` |
| datacraft | 9002 | `DATACRAFT_PORT` |
| leadengine | 9003 | `LEADENGINE_PORT` |

### Endpoints

Structure endpoints as:

```
POST /api/v1/{capability}
GET  /api/v1/{resource}
GET  /health
GET  /version
```

### Request Format

```http
POST /api/v1/search_documents HTTP/1.1
Content-Type: application/json
X-Request-ID: req_abc123

{
  "query": "contracts",
  "limit": 10
}
```

### Response Format

**Success:**

```json
{
  "success": true,
  "data": { ... },
  "metadata": {
    "request_id": "req_abc123",
    "execution_time_ms": 142
  }
}
```

**Error:**

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Parameter 'query' is required",
    "details": {
      "field": "query",
      "constraint": "required"
    }
  }
}
```

### Status Codes

| Code | Use Case |
|------|----------|
| 200 | Success |
| 400 | Bad request (validation error) |
| 401 | Unauthorized |
| 403 | Forbidden (permission denied) |
| 404 | Not found |
| 422 | Unprocessable entity |
| 500 | Internal server error |
| 503 | Service unavailable |

### Health Endpoint

Implement `/health` for liveness checks:

```json
GET /health

{
  "status": "healthy",
  "version": "1.2.3",
  "dependencies": {
    "database": "ok",
    "external_api": "ok"
  }
}
```

---

## 4. Python Plugin Interface

If your tool is importable as Python, implement the `PluginBase` interface.

### Minimal Implementation

```python
# mytool/mother_plugin.py
from mother.plugins import PluginBase, PluginResult
from mother.plugins.manifest import (
    PluginManifest,
    PluginMetadata,
    CapabilitySpec,
    ParameterSpec,
    ParameterType,
    ExecutionSpec,
    ExecutionType,
    PythonExecutionSpec,
)

def _create_manifest() -> PluginManifest:
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="mytool",
            version="1.0.0",
            description="What mytool does",
            author="Your Name",
            license="MIT",
        ),
        capabilities=[
            CapabilitySpec(
                name="do_something",
                description="Description for the LLM",
                parameters=[
                    ParameterSpec(
                        name="input",
                        type=ParameterType.STRING,
                        description="The input to process",
                        required=True,
                    ),
                ],
                confirmation_required=False,  # Set True for destructive ops
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mytool.mother_plugin",
                class_name="MyToolPlugin",
            ),
        ),
        permissions=["filesystem:read"],  # Declare required permissions
    )


class MyToolPlugin(PluginBase):
    def __init__(self, config: dict | None = None):
        super().__init__(_create_manifest(), config)

    async def execute(self, capability: str, params: dict) -> PluginResult:
        if capability == "do_something":
            result = await self._do_something(params["input"])
            return PluginResult.success_result(data={"result": result})

        return PluginResult.error_result(
            message=f"Unknown capability: {capability}",
            code="UNKNOWN_CAPABILITY",
        )

    async def _do_something(self, input: str) -> str:
        # Your actual logic
        return f"Processed: {input}"
```

### Registration

Register via entry point in `pyproject.toml`:

```toml
[project.entry-points."mother.plugins"]
mytool = "mytool.mother_plugin:MyToolPlugin"
```

Or place in user plugins directory:

```
~/.mother/plugins/mytool/
├── mother-plugin.yaml
└── plugin.py
```

---

## 5. Policy & Sandboxing

### Declaring Permissions

In your manifest, declare what permissions your tool needs:

```yaml
permissions:
  - "filesystem:read"
  - "filesystem:write:/tmp/mytool"  # Scoped to path
  - "network:external"
  - "secrets:read:MYTOOL_API_KEY"   # Specific secret
```

### Permission Types

| Permission | Description |
|------------|-------------|
| `filesystem:read` | Read any file |
| `filesystem:read:/path` | Read from specific path |
| `filesystem:write` | Write any file |
| `filesystem:write:/path` | Write to specific path |
| `network:external` | Make outbound network requests |
| `network:internal` | Localhost only |
| `shell` | Execute shell commands |
| `subprocess` | Spawn subprocesses |
| `secrets:read` | Read any secret |
| `secrets:read:KEY` | Read specific secret |
| `secrets:write` | Write secrets |

### Confirmation Gates

Mark destructive operations with `confirmation_required: true`:

```yaml
capabilities:
  - name: delete_document
    description: Permanently delete a document
    confirmation_required: true
```

Mother will pause and ask the user before executing:

```
Mother: I'll delete 'contract.pdf'. This cannot be undone. Proceed? [y/N]
```

### Workspace Isolation

If your tool writes files, respect the workspace config:

```python
import os

workspace = os.environ.get("MOTHER_WORKSPACE_DIR", "/tmp/mother")
output_path = os.path.join(workspace, "mytool", "output.txt")
```

---

## 6. Audit Attribution

Mother logs all tool executions. Your tool should support attribution.

### Request ID Propagation

If receiving requests from Mother, propagate the request ID:

```python
# In HTTP handler
request_id = request.headers.get("X-Request-ID", "unknown")
logger.info(f"[{request_id}] Processing request")
```

### Structured Logging

Log in JSON format for aggregation:

```python
import json
import sys

def audit_log(event: str, data: dict):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
        "tool": "mytool",
        **data
    }
    print(json.dumps(log_entry), file=sys.stderr)
```

### Events to Log

| Event | When | Include |
|-------|------|---------|
| `tool.start` | Execution begins | capability, params (redacted) |
| `tool.success` | Execution succeeds | execution_time, result_summary |
| `tool.error` | Execution fails | error_code, error_message |
| `tool.external_call` | Calling external API | service, endpoint (no credentials) |

---

## 7. Configuration Discovery

### Environment Variables

Use tool-specific prefix:

```bash
MYTOOL_API_KEY=xxx
MYTOOL_DATA_DIR=/data
MYTOOL_LOG_LEVEL=debug
```

### Configuration Files

Check in order:
1. `$MYTOOL_CONFIG` (explicit path)
2. `./.mytool.yaml` (project-local)
3. `~/.config/mytool/config.yaml` (user)
4. `/etc/mytool/config.yaml` (system)

### Mother Credentials Integration

If your tool needs credentials Mother manages, check:

```python
import os

# Mother's centralized credentials
mother_creds = os.path.expanduser("~/.config/mother/credentials.env")
if os.path.exists(mother_creds):
    from dotenv import load_dotenv
    load_dotenv(mother_creds)
```

### No Secrets in Repo

**CRITICAL:** Never commit secrets to your repository. Use:
- Environment variables
- `~/.config/` files (gitignored)
- Secret managers (for production)

---

## 8. Testing Your Integration

### Unit Tests

Test your plugin in isolation:

```python
import pytest
from mytool.mother_plugin import MyToolPlugin

@pytest.mark.asyncio
async def test_do_something():
    plugin = MyToolPlugin()
    result = await plugin.execute("do_something", {"input": "test"})
    assert result.success
    assert result.data["result"] == "Processed: test"
```

### Integration Test with Mother

```python
import pytest
from mother.plugins import PluginManager

@pytest.mark.asyncio
async def test_plugin_loads():
    manager = PluginManager()
    await manager.discover()

    info = manager.get_plugin_info("mytool")
    assert info is not None
    assert info.loaded
```

### CLI Test

```bash
# Test JSON output
output=$(mytool do-something --input "test" --output-format json)
echo "$output" | jq -e '.success == true'

# Test exit codes
mytool do-something --input "" && echo "FAIL: should error" || echo "OK: errored"
```

---

## 9. Checklist

Use this checklist before claiming "Mother-compatible":

### Required

- [ ] Tool name follows naming convention
- [ ] Capabilities have descriptive names
- [ ] CLI uses standard exit codes (if applicable)
- [ ] JSON output format supported (if CLI)
- [ ] No secrets committed to repo
- [ ] Permissions declared in manifest

### Recommended

- [ ] `--output-format` flag implemented
- [ ] `/health` endpoint (if HTTP)
- [ ] Structured logging to stderr
- [ ] Request ID propagation
- [ ] Unit tests for plugin class
- [ ] `confirmation_required` for destructive ops

### Optional

- [ ] Docker image available
- [ ] pyproject.toml entry point registered
- [ ] Integration test with Mother

---

## 10. Example: Complete CLI Integration

Here's a complete example of a Mother-compatible CLI tool:

```python
#!/usr/bin/env python3
"""mytool - A Mother-compatible CLI tool."""

import json
import sys
import click

@click.group()
@click.option("--output-format", type=click.Choice(["text", "json"]), default="text")
@click.option("--verbose", "-v", is_flag=True)
@click.pass_context
def cli(ctx, output_format, verbose):
    ctx.ensure_object(dict)
    ctx.obj["output_format"] = output_format
    ctx.obj["verbose"] = verbose

@cli.command()
@click.argument("input")
@click.pass_context
def process(ctx, input):
    """Process an input string."""
    try:
        result = f"Processed: {input}"

        if ctx.obj["output_format"] == "json":
            print(json.dumps({
                "success": True,
                "data": {"result": result},
                "error": None
            }))
        else:
            print(result)

        sys.exit(0)

    except Exception as e:
        if ctx.obj["output_format"] == "json":
            print(json.dumps({
                "success": False,
                "data": None,
                "error": {"code": "PROCESSING_ERROR", "message": str(e)}
            }))
        else:
            print(f"Error: {e}", file=sys.stderr)

        sys.exit(1)

if __name__ == "__main__":
    cli()
```

---

## Questions?

- [GitHub Issues](https://github.com/Mother-AI-OS/mother/issues) — Report bugs or request features
- [Ecosystem Overview](./OVERVIEW.md) — How Mother and tool repos relate

---

*This contract is part of [Mother AI OS](https://github.com/Mother-AI-OS/mother).*
