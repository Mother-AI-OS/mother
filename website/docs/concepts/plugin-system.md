---
sidebar_position: 2
---

# Plugin System

Mother AI OS uses a flexible plugin architecture for extensibility.

## Plugin Types

### Built-in Plugins

Included with Mother AI OS:
- **filesystem** - File and directory operations
- **shell** - Command execution
- **web** - HTTP requests

### PyPI Plugins

Install from PyPI:

```bash
mother plugin install mother-plugin-email
```

### Local Plugins

Create custom plugins in `~/.mother/plugins/`.

## Plugin Structure

Every plugin needs:

1. **Manifest** (`mother-plugin.yaml`) - Metadata and capabilities
2. **Implementation** - Python class extending `PluginBase`

### Manifest Example

```yaml
schema_version: "1.0"

plugin:
  name: my-plugin
  version: 1.0.0
  description: My custom plugin
  author: Your Name

capabilities:
  - name: do_something
    description: Does something useful
    parameters:
      - name: input
        type: string
        required: true
        description: The input to process

execution:
  type: python
  python:
    module: my_plugin
    class: MyPlugin
```

### Implementation Example

```python
from mother.plugins import PluginBase, PluginResult

class MyPlugin(PluginBase):
    async def execute(self, capability: str, params: dict) -> PluginResult:
        if capability == "do_something":
            result = self._process(params["input"])
            return PluginResult.success_result(data={"output": result})

        raise ValueError(f"Unknown capability: {capability}")

    def _process(self, input: str) -> str:
        return input.upper()
```

## Capability Parameters

Supported parameter types:

| Type | Description |
|------|-------------|
| `string` | Text value |
| `integer` | Whole number |
| `number` | Decimal number |
| `boolean` | True/false |
| `array` | List of values |
| `object` | Key-value mapping |

## Plugin Discovery

Mother AI OS discovers plugins from:

1. Built-in plugins directory
2. User plugins (`~/.mother/plugins/`)
3. PyPI entry points (`mother.plugins`)

## Next Steps

- [Creating Your Own Plugins](/docs/plugins/creating-plugins)
- [Publishing to PyPI](/docs/plugins/publishing)
