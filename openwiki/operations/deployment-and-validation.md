---
type: Operations Guide
title: Configuration, deployment, packaging, and validation
description: Operational entry points and validation layers for the Mother Python package, FastAPI service, container deployment, systemd unit, and CI pipeline.
tags: [operations, deployment, configuration, testing]
openwiki:
  roles: [operations, delivery, testing]
  change_kinds: [configuration, packaging, deployment, validation]
  source_paths: [mother/config/settings.py, pyproject.toml, Dockerfile, docker-compose.yml, mother.service, .github/workflows/ci.yml]
  symbols: [Settings, get_settings, run, main]
  test_paths: [tests/test_cli_setup.py, tests/test_doctor.py, tests/test_llm_providers.py]
  validation_commands: [pytest -q tests/test_cli_setup.py tests/test_doctor.py]
---
# Configuration, deployment, packaging, and validation

Consult this page for operational behavior rather than request semantics: environment-backed settings, executable entry points, image/service packaging, and the right level of verification. Runtime construction is documented in [service runtime and API](../architecture/runtime.md); capability controls are documented in [security control plane](../security/control-plane.md).

## Configuration and entry points

`Settings` is a `pydantic-settings` model. It reads the user credentials location `~/.config/mother/credentials.env` and then `.env`, while allowing process environment values. The cached `get_settings()` returns one settings instance per process. Do not read, expose, or commit a real credentials file; `.env.example` is the non-sensitive setup template.

Important settings groups are API bind host/port and API key, provider/model/token/iteration selection, configuration/log/workspace paths, safe mode and policy path, audit path/enabled state, sandbox mode, and logging/tool timeout. Defaults bind the API to `127.0.0.1:8080`, enable safe mode and sandbox mode, and use `./workspace` as the workspace path.

`pyproject.toml` defines the distributable package `mother-ai-os`, requires Python 3.11+, takes its version from `mother/__init__.py`, and exports two console scripts: `mother = mother.cli:main` and `mother-credentials = mother.credentials:main`. `mother serve` routes to `mother.main.run`; direct Uvicorn uses the canonical ASGI target `mother.main:app`.

## Deployment artifacts

| Artifact | Responsibility | Change boundary |
| --- | --- | --- |
| `Dockerfile` | Builds the service image and its runtime defaults | Rebuild only when dependency, image, command, filesystem ownership, or health behavior changes. |
| `docker-compose.yml` | Local composed deployment configuration | Keep environment/volume/network expectations aligned with the image and `Settings`. |
| `mother.service` | systemd unit for a Linux service installation | Review user, writable paths, environment source, restart, and hardening directives when service behavior changes. |
| `.github/workflows/ci.yml` | CI lint, typecheck, test, coverage, and package build | This is the authoritative broad validation matrix, not a default local command. |
| `.github/workflows/publish.yml` and `verify-install.yml` | Publishing and install verification automation | Consult for release/package-consumer changes. |

The container and systemd layers deploy the same [FastAPI runtime](../architecture/runtime.md); they do not introduce a second application entry point. Settings configure the [policy and audit controls](../security/control-plane.md), so deployment changes that alter defaults can change effective security posture.

## Validation ladder

Use quiet focused pytest invocations first; `-q` suppresses normal success noise while retaining failure diagnostics.

1. **Local feature checks:** run only tests mapped to the changed subsystem, for example `pytest -q tests/test_cli_setup.py tests/test_doctor.py` for CLI setup/diagnostics, `pytest -q tests/test_llm_providers.py` for provider factory behavior, or the commands on the linked runtime/plugin/security page.
2. **Static checks:** run `ruff check .` and `ruff format --check .` for Python source changes; run `mypy mother` when edited code falls within meaningful typing coverage. CI runs both.
3. **Full suite (conditional):** `pytest -v --tb=short --cov=mother --cov-report=xml --cov-report=term-missing --cov-report=json` is CI's coverage command. Use it before a broad refactor, release, cross-cutting configuration change, or when focused tests cannot prove an interaction. It is not the default for a narrow plugin or route change.
4. **Package and consumer surface (conditional):** `python -m build` is required when changing `pyproject.toml`, package-data inclusion, console scripts, version source, or artifacts expected by consumers. The wheel force-includes `mother/tools/tools-catalog.yaml`; do not hand-copy a generated/package mirror. Use `.github/workflows/verify-install.yml` for release-level install verification.
5. **Container/service smoke test (conditional):** build or start the relevant deployment only when changing deployment artifacts, service startup, image dependencies, or bind/health behavior. It requires intentionally supplied runtime configuration and must not be treated as a credentials-free unit test.

## Operational change recipes

### Add or rename a setting

Add the field and alias to `Settings`, identify all consumers, and update only the non-sensitive sample configuration/setup help that source supports. Because `get_settings()` is cached, tests that change environment values must clear/avoid the cache according to existing settings tests. Verify provider and operational behavior separately: an accepted setting that no consumer reads is not a shipped feature.

Run the closest configuration/CLI suite—typically `pytest -q tests/test_cli_setup.py tests/test_doctor.py`—plus the subsystem suite owning the setting. Run a container smoke test only for Docker/Compose environment wiring changes.

### Change a shipped command or package asset

Trace the entire public surface: `pyproject.toml` script or build configuration, implementation target such as `mother.cli:main`, CLI parsing and dispatch, tests, and the built distribution. A passing module unit test is internal correctness; script resolution from an installed wheel is shipped-surface correctness.

Run focused CLI tests first, then `python -m build` and the install-verification workflow or an equivalent isolated-install smoke test when the public entry point or packaged assets changed.

## Change navigation

For service boot failures, begin at `Settings`, then `mother.main.lifespan`, then [runtime and API](../architecture/runtime.md). For a capability absent in a deployed process, inspect `MOTHER_ENABLED_PLUGINS`, `resolve_enabled_plugins`, and [plugin discovery](../plugins/extension-and-execution.md#discovery-and-enablement) before modifying the agent. For a capability that is visible but blocked, follow [policy semantics](../security/control-plane.md#policy-semantics-that-changes-must-preserve) rather than weakening the deployment defaults.
