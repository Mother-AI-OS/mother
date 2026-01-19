---
sidebar_position: 2
---

# Creating Tools

This guide explains how to create a Mother-compatible external tool.

## Repository Structure

```
my-tool/
  mother-tool.yaml    # Required manifest
  README.md           # Documentation
  src/                # Tool implementation
  setup.py            # If Python-based
  Dockerfile          # If Docker-based
```

## Manifest Reference

### Required Fields

```yaml
schema_version: "1.0"

tool:
  name: my-tool           # Lowercase, hyphens allowed
  version: 1.0.0          # Semantic versioning
  description: My tool    # Short description

integration:
  type: cli               # cli, python, http, docker
  cli:
    binary: my-tool       # Main executable
```

### Full Example

```yaml
schema_version: "1.0"

tool:
  name: code-formatter
  version: 1.2.0
  description: Format code in multiple languages
  author: Jane Developer
  license: MIT
  homepage: https://github.com/jane/code-formatter
  repository: https://github.com/jane/code-formatter
  risk_level: low
  tags:
    - formatting
    - code
    - developer-tools

integration:
  type: cli
  cli:
    binary: formatter
    install_check: ["formatter", "--version"]
    working_dir: "${PROJECT_ROOT}"
    env:
      FORMATTER_CONFIG: "${HOME}/.config/formatter/config.yaml"
    commands:
      - name: format
        description: Format source code files
        args: ["format", "--file", "{file}"]
        confirmation_required: false
      - name: check
        description: Check formatting without changes
        args: ["check", "--file", "{file}"]
        confirmation_required: false

config:
  - name: style
    type: string
    default: "standard"
    description: Formatting style to use
  - name: line_length
    type: integer
    default: 88
    description: Maximum line length

permissions:
  - filesystem_read
  - filesystem_write
```

## Integration Types

### CLI Integration

Best for wrapping command-line tools:

```yaml
integration:
  type: cli
  cli:
    binary: my-cli
    install_check: ["my-cli", "--version"]
    working_dir: "${PROJECT_ROOT}"
    timeout: 30
    commands:
      - name: run
        description: Run the command
        args: ["run", "--input", "{input}", "--output", "{output}"]
        confirmation_required: true
```

**Command Args Syntax:**
- `{param}` - Replaced with parameter value
- `--flag` - Static flag
- `["--option", "{value}"]` - Option with value

### Python Integration

For tools implemented in Python:

```yaml
integration:
  type: python
  python:
    module: my_tool.mother_plugin
    class: MyToolPlugin
    dependencies:
      - requests>=2.28.0
      - pyyaml>=6.0
```

Implement the plugin class:

```python
# my_tool/mother_plugin.py
from mother.plugins import PluginBase, PluginResult

class MyToolPlugin(PluginBase):
    async def execute(self, capability: str, params: dict) -> PluginResult:
        if capability == "process":
            result = self._process(params["input"])
            return PluginResult.success_result(data=result)
        raise ValueError(f"Unknown capability: {capability}")
```

### HTTP Integration

For tools exposing HTTP APIs:

```yaml
integration:
  type: http
  http:
    base_url: http://localhost:8080
    health_endpoint: /health
    timeout: 30
    headers:
      Authorization: "Bearer ${MY_TOOL_TOKEN}"
    endpoints:
      - name: query
        method: POST
        path: /api/query
        body_template: '{"query": "{query}", "limit": {limit}}'
      - name: status
        method: GET
        path: /api/status
```

### Docker Integration

For containerized tools:

```yaml
integration:
  type: docker
  docker:
    image: myorg/my-tool:1.0.0
    pull_policy: if-not-present
    ports:
      - "8080:8080"
    volumes:
      - "${HOME}/.config/mytool:/config:ro"
      - "${PROJECT_ROOT}:/workspace"
    environment:
      - "MY_TOOL_CONFIG=/config/settings.yaml"
    command: ["--server", "--port", "8080"]
```

## Risk Levels

Choose the appropriate risk level:

| Level | Criteria |
|-------|----------|
| `low` | Read-only operations, no network, no system changes |
| `medium` | File modifications, local network access |
| `high` | System commands, external network, credentials |
| `critical` | Root access, sensitive data, irreversible actions |

## Permissions

Declare required permissions:

```yaml
permissions:
  - filesystem_read      # Read files
  - filesystem_write     # Write/modify files
  - network_local        # Local network access
  - network_external     # External network access
  - execute_commands     # Run shell commands
  - access_credentials   # Access stored credentials
```

## Configuration Fields

Define configurable options:

```yaml
config:
  - name: api_key
    type: string
    required: true
    secret: true
    description: API key for authentication
  - name: max_retries
    type: integer
    default: 3
    description: Maximum retry attempts
  - name: features
    type: array
    item_type: string
    default: ["feature1", "feature2"]
    description: Enabled features
```

## Testing Your Tool

1. Validate the manifest:

```bash
mother tools validate /path/to/my-tool
```

2. Install locally:

```bash
mother tools install local:/path/to/my-tool
```

3. Check status:

```bash
mother tools status my-tool
```

4. Enable and test:

```bash
mother tools enable my-tool
mother tools health my-tool
```

## Publishing

### GitHub Repository

Push your tool to GitHub with the `mother-tool.yaml` manifest.

Users install with:

```bash
mother tools install git:https://github.com/you/my-tool
```

### Tool Catalog

Submit your tool to the official catalog:

1. Fork [mother-tool-catalog](https://github.com/mother-ai/tool-catalog)
2. Add entry to `catalog.yaml`
3. Submit pull request

Catalog entry format:

```yaml
- name: my-tool
  description: My awesome tool
  repository: https://github.com/you/my-tool
  risk_level: low
  integration_type: cli
  tags: [utility, developer-tools]
  author: Your Name
  verified: false
```

## Best Practices

1. **Start with low risk** - Request minimal permissions
2. **Document thoroughly** - Include README with examples
3. **Handle errors gracefully** - Return meaningful error messages
4. **Support dry-run** - Add `--dry-run` flags where applicable
5. **Version carefully** - Follow semantic versioning
6. **Test on clean systems** - Ensure install_check works correctly
