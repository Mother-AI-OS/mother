---
sidebar_position: 3
---

# Enterprise Deployment

Guide for deploying Mother AI OS in enterprise environments with security, compliance, and scalability requirements.

## Editions

Mother AI OS is available in different editions:

| Feature | Community | Professional | Enterprise |
|---------|-----------|--------------|------------|
| Core Plugin System | Yes | Yes | Yes |
| Multi-LLM Support | Yes | Yes | Yes |
| Policy Engine | Basic | Advanced | Advanced |
| Safe Mode | Yes | Yes | Yes |
| Schema Validation | Yes | Yes | Yes |
| Audit Logging | 7-day retention | 30-day retention | Unlimited |
| PII Redaction | Basic patterns | Extended patterns | Custom patterns |
| Sandbox/Isolation | Basic | Advanced | Advanced |
| High-Risk Plugin Control | Yes | Yes | Yes |
| LDAP/SSO Integration | No | Yes | Yes |
| Custom Policy Rules | No | Yes | Yes |
| Dedicated Support | No | No | Yes |
| SLA | No | 99.5% | 99.9% |

## Quick Start

### Production Configuration

```bash
# Enable safe mode
export MOTHER_SAFE_MODE=1

# Configure API authentication
export MOTHER_API_KEY=$(openssl rand -hex 32)

# Set audit log directory
export MOTHER_AUDIT_DIR=/var/log/mother

# Configure workspace isolation
export MOTHER_WORKSPACE=/app/workspace

# Start with production settings
mother serve --host 0.0.0.0 --port 8080
```

### Docker Deployment

```dockerfile
FROM python:3.12-slim

# Install Mother AI OS
RUN pip install mother-ai-os[enterprise]

# Create non-root user
RUN useradd -m mother
USER mother

# Configure directories
WORKDIR /app
RUN mkdir -p /app/workspace /app/logs

# Set production environment
ENV MOTHER_SAFE_MODE=1
ENV MOTHER_AUDIT_DIR=/app/logs
ENV MOTHER_WORKSPACE=/app/workspace

EXPOSE 8080
CMD ["mother", "serve", "--host", "0.0.0.0", "--port", "8080"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  mother:
    build: .
    environment:
      - MOTHER_SAFE_MODE=1
      - MOTHER_API_KEY=${MOTHER_API_KEY}
      - MOTHER_AUDIT_DIR=/var/log/mother
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./workspace:/app/workspace
      - ./logs:/var/log/mother
    ports:
      - "8080:8080"
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Security Configuration

### Policy Engine Setup

Create a policy configuration file:

```python
# /etc/mother/policies.py
from mother.policy import Policy, PolicyAction

POLICIES = [
    # Block all shell execution
    Policy(
        name="no-shell",
        capability_pattern="*_shell_*",
        action=PolicyAction.DENY,
        reason="Shell execution disabled in production",
        priority=100,
    ),
    # Require confirmation for file deletion
    Policy(
        name="confirm-delete",
        capability_pattern="*_delete_*",
        action=PolicyAction.CONFIRM,
        reason="Deletion requires confirmation",
        priority=90,
    ),
    # Audit all filesystem operations
    Policy(
        name="audit-filesystem",
        capability_pattern="filesystem_*",
        action=PolicyAction.AUDIT,
        priority=50,
    ),
]
```

Load policies at startup:

```python
from mother.policy import get_policy_engine
from policies import POLICIES

engine = get_policy_engine()
for policy in POLICIES:
    engine.add_policy(policy)
```

### Sandbox Configuration

```python
from mother.plugins.sandbox import (
    SandboxConfig,
    ResourceLimits,
    WorkspaceConfig,
)

SANDBOX_CONFIG = SandboxConfig(
    enabled=True,
    resource_limits=ResourceLimits(
        max_cpu_seconds=30,
        max_memory_mb=256,
        max_execution_time=60,
        max_file_size_mb=50,
        max_subprocess=5,
    ),
    workspace=WorkspaceConfig(
        workspace_dir=Path("/app/workspace"),
        allow_read_outside=False,
        allowed_read_paths=[
            "/usr/share",
            "/etc/mother/templates",
        ],
    ),
    allow_shell=False,
    allow_network=True,
)
```

### High-Risk Plugin Management

```python
from mother.plugins import PluginConfig

# Whitelist specific high-risk plugins
PLUGIN_CONFIG = PluginConfig(
    allow_high_risk_plugins=False,
    explicitly_enabled_plugins=[
        "approved-filesystem-plugin",
        "approved-network-plugin",
    ],
    disabled_plugins=[
        "untrusted-plugin",
    ],
)
```

## Audit & Compliance

### Log Configuration

```python
from mother.audit import AuditLogConfig

AUDIT_CONFIG = AuditLogConfig(
    log_dir=Path("/var/log/mother"),
    max_file_size_mb=100,
    max_files=100,  # 100 * 100MB = 10GB retention
    flush_interval=1.0,
    include_params=True,
    redact_sensitive=True,
)
```

### Log Format

Audit logs are in JSONL format:

```json
{"timestamp":"2024-01-15T10:30:00Z","event_type":"CAPABILITY_REQUEST","correlation_id":"abc123","capability":"filesystem_write","plugin":"core","params":{"path":"[REDACTED]"},"user_id":"user_hash"}
{"timestamp":"2024-01-15T10:30:00Z","event_type":"POLICY_DECISION","correlation_id":"abc123","capability":"filesystem_write","action":"allow","allowed":true}
{"timestamp":"2024-01-15T10:30:01Z","event_type":"CAPABILITY_RESULT","correlation_id":"abc123","capability":"filesystem_write","success":true,"duration_ms":150}
```

### Log Aggregation

Configure log forwarding to SIEM:

```yaml
# Fluent Bit configuration
[INPUT]
    Name tail
    Path /var/log/mother/*.jsonl
    Parser json
    Tag mother.audit

[OUTPUT]
    Name splunk
    Match mother.*
    Host splunk.company.com
    Port 8088
    TLS On
    Splunk_Token ${SPLUNK_HEC_TOKEN}
```

### Compliance Reports

Generate compliance reports:

```python
from mother.audit import get_audit_logger
from datetime import datetime, timedelta

logger = get_audit_logger()

# Query recent activity
entries = logger.query(
    start_time=datetime.now() - timedelta(days=7),
    event_types=["CAPABILITY_REQUEST", "POLICY_DECISION"],
)

# Generate summary
denied = sum(1 for e in entries if e.get("allowed") is False)
total = len([e for e in entries if e["event_type"] == "CAPABILITY_REQUEST"])

print(f"Policy denials: {denied}/{total} requests")
```

## High Availability

### Load Balancer Configuration

```nginx
upstream mother {
    least_conn;
    server mother-1:8080 weight=1;
    server mother-2:8080 weight=1;
    server mother-3:8080 weight=1;
}

server {
    listen 443 ssl;
    server_name mother.company.com;

    ssl_certificate /etc/ssl/mother.crt;
    ssl_certificate_key /etc/ssl/mother.key;

    location / {
        proxy_pass http://mother;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-API-Key $http_x_api_key;
    }
}
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mother
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mother
  template:
    metadata:
      labels:
        app: mother
    spec:
      containers:
      - name: mother
        image: mother-ai-os:latest
        env:
        - name: MOTHER_SAFE_MODE
          value: "1"
        - name: MOTHER_API_KEY
          valueFrom:
            secretKeyRef:
              name: mother-secrets
              key: api-key
        resources:
          limits:
            cpu: "2"
            memory: "4Gi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        volumeMounts:
        - name: workspace
          mountPath: /app/workspace
        - name: logs
          mountPath: /var/log/mother
      volumes:
      - name: workspace
        persistentVolumeClaim:
          claimName: mother-workspace
      - name: logs
        persistentVolumeClaim:
          claimName: mother-logs
```

## Monitoring

### Health Endpoint

```bash
curl http://localhost:8080/health
# {"status": "healthy", "version": "1.0.0", "plugins_loaded": 15}
```

### Prometheus Metrics

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'mother'
    static_configs:
      - targets: ['mother:8080']
    metrics_path: '/metrics'
```

Available metrics:
- `mother_requests_total` - Total API requests
- `mother_request_duration_seconds` - Request latency histogram
- `mother_capability_executions_total` - Capability executions by name
- `mother_policy_decisions_total` - Policy decisions by action
- `mother_plugin_errors_total` - Plugin errors by type

## Troubleshooting

### Common Issues

**Plugin not loading:**
```bash
# Check if plugin is high-risk
mother plugins list --show-risk

# Enable specific plugin
export MOTHER_ENABLED_PLUGINS=my-plugin
```

**Policy blocking requests:**
```bash
# Check audit log for denials
grep "POLICY_DECISION" /var/log/mother/audit.jsonl | jq 'select(.allowed==false)'
```

**Sandbox limit exceeded:**
```bash
# Check execution context
grep "LIMIT_EXCEEDED" /var/log/mother/audit.jsonl
```

### Debug Mode

```bash
# Enable debug logging (not for production)
export MOTHER_LOG_LEVEL=DEBUG
mother serve
```

## Support

- Documentation: https://mother-ai.com/docs
- Enterprise Support: enterprise@mother-ai.com
- Security Issues: security@mother-ai.com
