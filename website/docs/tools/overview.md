---
sidebar_position: 1
---

# External Tools

Mother AI OS supports external tool repositories for extending functionality beyond the built-in plugin system.

## Tools vs Plugins

| Feature | Plugins | External Tools |
|---------|---------|----------------|
| Runtime | In-process Python | Subprocess, HTTP, Docker |
| Discovery | Entry points | Git repos, local paths |
| Installation | `pip install` | `mother tools install` |
| Capabilities | Python functions | CLI commands, APIs |
| Use case | Native integrations | Third-party CLIs, services |

## Quick Start

```bash
# List available tools
mother tools list --available

# Install from Git
mother tools install git:https://github.com/example/mother-tool-example

# Install from local path
mother tools install local:/path/to/tool

# Install from catalog
mother tools install example-tool

# Check tool status
mother tools status example-tool

# Enable a tool (disabled by default for security)
mother tools enable example-tool
```

## Tool Manifest

Every external tool repository needs a `mother-tool.yaml` manifest:

```yaml
schema_version: "1.0"

tool:
  name: my-tool
  version: 1.0.0
  description: My custom tool
  author: Your Name
  risk_level: low  # low, medium, high, critical

integration:
  type: cli  # cli, python, http, docker
  cli:
    binary: my-tool
    commands:
      - name: run
        description: Run the tool
        args: ["--input", "{input}"]
```

## Integration Types

### CLI Integration

Wraps command-line tools:

```yaml
integration:
  type: cli
  cli:
    binary: mytool
    install_check: ["mytool", "--version"]
    commands:
      - name: process
        description: Process data
        args: ["process", "--file", "{file}"]
```

### Python Integration

Loads Python modules directly:

```yaml
integration:
  type: python
  python:
    module: my_tool.plugin
    class: MyToolPlugin
    dependencies:
      - my-tool>=1.0.0
```

### HTTP Integration

Connects to HTTP APIs:

```yaml
integration:
  type: http
  http:
    base_url: http://localhost:8080
    health_endpoint: /health
    endpoints:
      - name: query
        method: POST
        path: /api/query
```

### Docker Integration

Runs tools in containers:

```yaml
integration:
  type: docker
  docker:
    image: my-org/my-tool:latest
    ports:
      - "8080:8080"
    volumes:
      - "${HOME}/.config/mytool:/config"
```

## Security

Tools are **disabled by default** after installation for security. Enable explicitly:

```bash
mother tools enable my-tool
```

### Risk Levels

| Level | Default Action | Use Case |
|-------|----------------|----------|
| `low` | Allow | Read-only tools, formatters |
| `medium` | Confirm | File modification, API calls |
| `high` | Confirm | System commands, network access |
| `critical` | Deny | Elevated privileges, sensitive data |

### Policy Configuration

Create `mother_tool_policy.yaml` to customize:

```yaml
enabled: true
default_action: confirm

risk_rules:
  low: allow
  medium: confirm
  high: confirm
  critical: deny

blocked_tools:
  - dangerous-tool

allowed_tools:
  - trusted-tool
```

## Next Steps

- [Creating Tools](/docs/tools/creating-tools) - Build your own tool
- [CLI Reference](/docs/tools/cli-reference) - Full command reference
