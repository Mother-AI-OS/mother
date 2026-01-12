---
sidebar_position: 3
---

# Security Model

Mother AI OS implements defense-in-depth security with enterprise-grade features for production deployments.

## Overview

Mother's security architecture includes:
- **Policy Engine**: Centralized capability authorization
- **Safe Mode**: Restrictive default configuration
- **Schema Validation**: Input validation with versioning
- **Audit Logging**: JSONL logs with rotation and PII redaction
- **Sandbox/Isolation**: Resource limits and workspace isolation
- **High-Risk Plugin Control**: Disabled-by-default for dangerous plugins

## Permission System

Every plugin capability declares required permissions:

```yaml
capabilities:
  - name: delete_file
    description: Delete a file
    confirmation_required: true  # Requires user confirmation
permissions:
  - filesystem:write
  - filesystem:delete
```

### Permission Types

| Permission | Description | Risk Level |
|------------|-------------|------------|
| `filesystem:read` | Read files | Low |
| `filesystem:write` | Write files | High |
| `filesystem:delete` | Delete files | High |
| `network:internal` | localhost only | Low |
| `network:external` | Internet access | High |
| `secrets:read` | Read credentials | High |
| `secrets:write` | Write credentials | High |
| `shell` | Execute shell commands | Critical |
| `subprocess` | Spawn processes | High |

## Policy Engine

The policy engine acts as a centralized gate for all capability execution:

```python
from mother.policy import PolicyEngine, Policy, PolicyAction, get_policy_engine

# Configure policies
engine = get_policy_engine()
engine.add_policy(Policy(
    name="block-shell-in-prod",
    capability_pattern="*_shell_*",
    action=PolicyAction.DENY,
    reason="Shell execution disabled in production",
    priority=100,
))

# Check before execution
result = engine.check("filesystem_delete_file", {"path": "/tmp/test.txt"})
if not result.allowed:
    raise PolicyViolationError(result.reason)
```

### Policy Actions

- `ALLOW`: Permit execution
- `DENY`: Block execution
- `AUDIT`: Allow but log for review
- `CONFIRM`: Require user confirmation

## Safe Mode

Safe mode provides a restrictive default configuration suitable for production:

```bash
# Enable via environment variable
export MOTHER_SAFE_MODE=1
mother serve
```

Safe mode enables:
- Strict policy enforcement
- High-risk plugins disabled
- All actions logged
- Confirmation required for destructive operations

```python
from mother.config import Settings

settings = Settings()
if settings.safe_mode:
    print("Running in safe mode")
```

## Capability Schema Validation

All capability parameters are validated against JSON Schema:

```yaml
capabilities:
  - name: send_email
    parameters:
      - name: to
        type: string
        required: true
        description: Recipient email
      - name: subject
        type: string
        required: true
      - name: body
        type: string
        required: true
```

### Version Compatibility

Plugins declare version requirements:

```yaml
plugin:
  name: my-plugin
  version: 2.1.0
  requires_mother: ">=1.0.0"
```

Version checking uses semantic versioning:

```python
from mother.plugins.schema import is_version_compatible

# Check compatibility
is_version_compatible("1.0.0", ">=1.0.0")  # True
is_version_compatible("0.9.0", ">=1.0.0")  # False
```

## Enterprise Audit Logging

Comprehensive audit logging for compliance:

```python
from mother.audit import get_audit_logger, AuditEventType

logger = get_audit_logger()

# Log capability request
correlation_id = logger.log_capability_request(
    capability="filesystem_write",
    plugin="core",
    params={"path": "/workspace/output.txt"},
    user_id="user_hash",
)

# Log policy decision
logger.log_policy_decision(
    capability="filesystem_write",
    plugin="core",
    action="allow",
    allowed=True,
    correlation_id=correlation_id,
)
```

### Log Configuration

```python
from mother.audit import AuditLogConfig, AuditLogger

config = AuditLogConfig(
    log_dir=Path("/var/log/mother"),
    max_file_size_mb=100,
    max_files=10,
    flush_interval=1.0,
)
logger = AuditLogger(config)
```

### PII Redaction

Sensitive data is automatically redacted:

```python
from mother.audit import redact

# Automatically redacts API keys, passwords, emails, etc.
safe_data = redact({
    "api_key": "sk-ant-abc123...",
    "user_email": "user@example.com",
})
# Result: {"api_key": "[REDACTED:ANTHROPIC_KEY]", "user_email": "[REDACTED:EMAIL]"}
```

Detected patterns include:
- OpenAI/Anthropic API keys
- AWS credentials
- GitHub tokens
- JWT tokens
- Passwords
- Email addresses
- Credit card numbers
- SSN

## Sandbox/Isolation

Plugins run in sandboxed environments with resource limits:

```python
from mother.plugins.sandbox import (
    SandboxConfig,
    ResourceLimits,
    WorkspaceConfig,
    SandboxManager,
)

config = SandboxConfig(
    enabled=True,
    resource_limits=ResourceLimits(
        max_cpu_seconds=60,
        max_memory_mb=512,
        max_execution_time=300,
        max_file_size_mb=100,
        max_subprocess=10,
    ),
    workspace=WorkspaceConfig(
        workspace_dir=Path("./workspace"),
        allow_read_outside=True,
        allowed_read_paths=["/usr/share"],
    ),
    allow_shell=False,
    allow_network=True,
)

manager = SandboxManager(config)
```

### Workspace Isolation

Write operations are restricted to the workspace directory:

```python
workspace = WorkspaceConfig(workspace_dir=Path("/app/workspace"))

workspace.is_path_allowed_write("/app/workspace/output.txt")  # True
workspace.is_path_allowed_write("/etc/passwd")  # False
```

## High-Risk Plugin Control

Plugins with dangerous permissions are disabled by default:

```python
from mother.plugins import PluginConfig, PluginManager, RiskLevel

# Default: high-risk plugins are skipped
config = PluginConfig()  # allow_high_risk_plugins=False

# Explicitly enable specific high-risk plugins
config = PluginConfig(
    explicitly_enabled_plugins=["trusted-shell-plugin"],
)

# Or allow all high-risk plugins (not recommended for production)
config = PluginConfig(allow_high_risk_plugins=True)
```

### Risk Levels

| Level | Description | Default State |
|-------|-------------|---------------|
| `LOW` | Safe operations | Enabled |
| `MEDIUM` | Limited external access | Enabled |
| `HIGH` | Write, network, external services | Disabled |
| `CRITICAL` | Shell, system access, credentials | Disabled |

### High-Risk Permissions

These permissions trigger disabled-by-default:
- `shell`
- `subprocess`
- `filesystem:write`
- `filesystem:delete`
- `secrets:read`
- `secrets:write`
- `network:external`

## Confirmation Requirements

Destructive actions require explicit confirmation:

- File deletion
- Shell command execution
- Bulk modifications
- External API calls with side effects

The API returns a `pending_confirmation` status that must be approved.

## Path Validation

All file paths are validated:
- No path traversal (`../`)
- Restricted to allowed directories
- Symlink resolution
- Workspace boundary enforcement

## API Authentication

All requests require an API key:

```bash
curl -H "X-API-Key: your-secret-key" ...
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MOTHER_SAFE_MODE` | Enable safe mode | `0` |
| `MOTHER_API_KEY` | Required API key | None |
| `MOTHER_AUDIT_DIR` | Audit log directory | `./logs` |
| `MOTHER_WORKSPACE` | Plugin workspace | `./workspace` |

## Best Practices

1. **Enable Safe Mode in Production**: `MOTHER_SAFE_MODE=1`
2. **Use Strong API Keys**: Generate with `openssl rand -hex 32`
3. **Review Plugin Permissions**: Check manifests before enabling
4. **Monitor Audit Logs**: Set up log aggregation
5. **Restrict Network Exposure**: Use reverse proxy
6. **Enable HTTPS**: Never expose HTTP in production
7. **Explicitly Enable High-Risk Plugins**: Don't use `allow_high_risk_plugins=True`
8. **Configure Workspace Isolation**: Restrict write paths
