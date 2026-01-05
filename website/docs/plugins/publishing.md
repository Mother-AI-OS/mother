---
sidebar_position: 3
---

# Publishing to PyPI

Share your plugin with the Mother AI OS community.

## Prerequisites

1. PyPI account at [pypi.org](https://pypi.org)
2. Plugin tested and working locally
3. `build` and `twine` installed

## Project Structure

```
my-mother-plugin/
├── pyproject.toml
├── README.md
├── LICENSE
├── mother-plugin.yaml
└── src/
    └── my_plugin/
        ├── __init__.py
        └── plugin.py
```

## Configure pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "mother-plugin-example"
version = "1.0.0"
description = "Example plugin for Mother AI OS"
readme = "README.md"
license = {text = "MIT"}
authors = [{name = "Your Name", email = "you@example.com"}]
classifiers = [
    "Development Status :: 4 - Beta",
    "Framework :: Mother AI OS",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
]
dependencies = [
    "mother-ai-os>=0.1.0",
]

[project.entry-points."mother.plugins"]
my-plugin = "my_plugin:MyPlugin"

[project.urls]
Homepage = "https://github.com/you/mother-plugin-example"
```

## Build and Upload

```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Upload to PyPI
twine upload dist/*
```

## Best Practices

1. **Semantic versioning** - Use major.minor.patch
2. **Clear documentation** - Include usage examples in README
3. **Pin dependencies** - Specify compatible versions
4. **Add tests** - Include a test suite
5. **License clearly** - Use a standard open source license

## Plugin Naming Convention

Use the prefix `mother-plugin-` for discoverability:

- `mother-plugin-email`
- `mother-plugin-database`
- `mother-plugin-slack`
