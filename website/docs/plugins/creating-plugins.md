---
sidebar_position: 2
---

# Creating Plugins

Build your own Mother AI OS plugins.

## Quick Start

1. Create the manifest
2. Implement the plugin class
3. Register as entry point

## Step 1: Create Manifest

Create `mother-plugin.yaml`:

```yaml
schema_version: "1.0"

plugin:
  name: my-plugin
  version: 1.0.0
  description: My custom plugin
  author: Your Name

capabilities:
  - name: greet
    description: Greet someone by name
    parameters:
      - name: name
        type: string
        required: true
        description: Name to greet

execution:
  type: python
  python:
    module: my_plugin
    class: MyPlugin
```

## Step 2: Implement Plugin

Create `my_plugin.py`:

```python
from mother.plugins import PluginBase, PluginResult

class MyPlugin(PluginBase):
    async def execute(self, capability: str, params: dict) -> PluginResult:
        if capability == "greet":
            name = params["name"]
            message = f"Hello, {name}!"
            return PluginResult.success_result(data={"message": message})

        raise ValueError(f"Unknown capability: {capability}")
```

## Step 3: Register Plugin

In `pyproject.toml`:

```toml
[project.entry-points."mother.plugins"]
my-plugin = "my_plugin:MyPlugin"
```

## Testing Your Plugin

```bash
# Install in development mode
pip install -e .

# Restart Mother AI OS
mother serve

# Test it
curl -X POST localhost:8080/command \
  -H "Content-Type: application/json" \
  -d '{"command": "Greet David"}'
```

## Next Steps

- [Publishing to PyPI](/docs/plugins/publishing)
