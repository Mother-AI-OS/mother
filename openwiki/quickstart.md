---
type: Repository Guide
title: Mother AI OS guide
description: Navigation and change-routing guide for Mother, a Python FastAPI agent that uses LLM-selected plugin capabilities under configurable controls.
tags: [agent, fastapi, plugins, security]
openwiki:
  roles: [repository, workflow]
  source_paths: [pyproject.toml, mother/main.py, mother/cli/__init__.py]
  validation_commands: [pytest -q tests/test_api_routes.py]
---
# Mother AI OS guide

Mother is a Python 3.11+ package and FastAPI service that turns natural-language requests into calls to discovered plugin capabilities. Its shipped CLI entry point is `mother.cli:main`; `mother serve` starts the FastAPI app in `mother.main`. The core implementation deliberately separates LLM orchestration from capability discovery and policy enforcement.

Start with [runtime and API](architecture/runtime.md) for request behavior, [plugin extension and execution](plugins/extension-and-execution.md) for capabilities and integration seams, [security control plane](security/control-plane.md) for authorization and policy order, and [deployment and validation](operations/deployment-and-validation.md) for packaging and operational checks.

## How the knowledge base is organized

- [Runtime and API](architecture/runtime.md) is the canonical home for service startup, HTTP routes, agent state, LLM selection, session persistence, and memory.
- [Plugin extension and execution](plugins/extension-and-execution.md) owns discovery precedence, manifests, loading, enabled-plugin resolution, and the complete third-party plugin change surface.
- [Security control plane](security/control-plane.md) owns key identity, scopes, policy evaluation, sandbox concepts, and auditable state.
- [Deployment and validation](operations/deployment-and-validation.md) owns configuration locations, container/service artifacts, CI, and the distinction between focused and release validation.

## Task routing

| Change area or user intent | Relevant wiki page | Exact source entry points | Important symbols or types | Focused tests | Minimal validation command |
| --- | --- | --- | --- | --- | --- |
| Start up the server, alter dependency wiring, or add an HTTP route | [Runtime and API](architecture/runtime.md) | `mother/main.py`, `mother/api/routes.py`, `mother/api/schemas.py` | `lifespan`, `init_dependencies`, `MotherAgent` | `tests/test_api_routes.py`, `tests/test_api_schemas.py` | `pytest -q tests/test_api_routes.py tests/test_api_schemas.py` |
| Change agent behavior, confirmation, plans, sessions, or memory | [Runtime and API](architecture/runtime.md) | `mother/agent/core.py`, `mother/agent/session.py`, `mother/memory/manager.py` | `MotherAgent`, `AgentState`, `PendingConfirmation`, `ExecutionPlan`, `MemoryManager` | `tests/test_agent_core.py`, `tests/test_agent_session.py`, `tests/test_memory_manager.py` | `pytest -q tests/test_agent_core.py tests/test_agent_session.py` |
| Add or modify a built-in or external capability | [Plugin extension and execution](plugins/extension-and-execution.md) | `mother/plugins/base.py`, `mother/plugins/manifest.py`, `mother/plugins/__init__.py`, `mother/plugins/loader.py` | `PluginBase`, `PluginManifest`, `CapabilitySpec`, `PluginManager` | `tests/test_plugin_manifest.py`, `tests/test_plugin_loader.py`, relevant `tests/test_builtin_*.py` | `pytest -q tests/test_plugin_manifest.py tests/test_plugin_loader.py` |
| Change discovery, high-risk enablement, execution, or timeouts | [Plugin extension and execution](plugins/extension-and-execution.md) | `mother/plugins/__init__.py`, `mother/plugins/executor.py`, `mother/tools/registry.py` | `resolve_enabled_plugins`, `PluginConfig`, `ExecutorBase`, `ToolRegistry` | `tests/test_plugin_manager.py`, `tests/test_executor.py`, `tests/test_tool_availability.py` | `pytest -q tests/test_plugin_manager.py tests/test_executor.py tests/test_tool_availability.py` |
| Change API keys, scopes, policy rules, sandboxing, or audit data | [Security control plane](security/control-plane.md) | `mother/api/auth.py`, `mother/auth/keys.py`, `mother/auth/scopes.py`, `mother/policy/engine.py`, `mother/plugins/executor.py` | `APIKeyStore`, `IdentityContext`, `PolicyEngine`, `check_scope`, `check_policy` | `tests/test_auth_keys.py`, `tests/test_policy.py`, `tests/test_plugin_sandbox.py` | `pytest -q tests/test_auth_keys.py tests/test_policy.py` |
| Change environment settings, Docker/systemd setup, package entry points, or CI | [Deployment and validation](operations/deployment-and-validation.md) | `mother/config/settings.py`, `pyproject.toml`, `Dockerfile`, `mother.service`, `.github/workflows/ci.yml` | `Settings`, `get_settings`, project scripts | `tests/test_cli_setup.py`, `tests/test_doctor.py` | `pytest -q tests/test_cli_setup.py tests/test_doctor.py` |

## Boundaries worth retaining

The `ToolRegistry` is a plugin adapter: its legacy `ToolWrapper` collection is empty in current code. Consequently `/tools/{tool_name}/{command}` still searches wrappers and is not a direct plugin-capability endpoint. Do not represent it as a path to `PluginManager.execute` without changing its implementation and tests. The agent uses registry schemas and `execute_plugin` instead.

External tool packages are optional integrations, not repository dependencies. The package exposes the `mother.plugins` entry-point group in `pyproject.toml`; the canonical integration contract remains [`docs/dev/INTEGRATION_CONTRACT.md`](../docs/dev/INTEGRATION_CONTRACT.md).

## Backlog

No evidence-blocked documentation areas are currently tracked.
