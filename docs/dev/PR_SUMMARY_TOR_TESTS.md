# PR Summary: Tor Plugin Test Coverage

## Overview

This PR adds comprehensive test coverage for the Tor and Tor-shell plugins, focusing on policy gating behavior and safe mode enforcement.

## What Was Added

### New Test File: `tests/test_tor_plugins.py`

A focused test suite with **39 tests** covering:

#### A. Safe-Mode Blocks Tor (8 tests)
- Verifies policy engine correctly identifies `tor_*` capabilities as high-risk
- Confirms safe mode DENIES all Tor capabilities when no explicit allow rule exists
- Tests that default policy blocks all Tor capabilities
- Tests `is_capability_enabled()` and `get_allowed_capabilities()` filtering

#### B. Safe-Mode Blocks Tor-Shell (5 tests)
- Verifies policy engine correctly identifies `tor-shell_*` capabilities as high-risk
- Confirms safe mode DENIES all Tor-shell capabilities by default
- Tests that default policy blocks all Tor-shell capabilities

#### C. Explicit Policy Allow Enables Tor (4 tests)
- Tests that explicit ALLOW rule permits `tor_fetch` even in safe mode
- Verifies allowing one capability doesn't affect other Tor capabilities
- Tests plugin execution with mocked network (no real Tor calls)
- Tests `tor_verified_sites` returns data without network access

#### D. Explicit Policy Allow Enables Tor-Shell (5 tests)
- Tests that explicit ALLOW rule permits `tor-shell_darknet_dw`
- Verifies allowing one capability doesn't affect other Tor-shell capabilities
- Tests plugin execution with mocked subprocess (no real process spawning)
- Tests `darknet_bookmarks` and `darknet_news` return data without subprocess

#### E. High-Risk Classification (8 tests)
- Verifies Tor plugin manifest declares network permissions
- Verifies Tor-shell plugin manifest declares shell permissions
- Tests all expected capabilities exist in manifests
- Tests service control capabilities require confirmation
- Tests policy engine regex patterns match plugin names

#### Integration & Error Handling (9 tests)
- Full flow tests combining policy evaluation with plugin execution
- Error handling for timeout, connection errors, subprocess failures
- Wildcard policy rule tests

## How It Works

1. **Policy Gating**: Tests verify the `PolicyEngine._is_high_risk_capability()` method correctly matches:
   - `^tor_` pattern for Tor plugin capabilities
   - `^tor-shell_` pattern for Tor-shell plugin capabilities

2. **Safe Mode Blocking**: When `safe_mode=True` and no explicit allow rule exists, the policy engine returns a DENY decision with reason "blocked in safe mode"

3. **Explicit Allow Rules**: Tests create `PolicyConfig` with explicit `PolicyRule` objects that enable specific capabilities while keeping others blocked

4. **Offline Testing**: All tests use mocking:
   - `httpx.AsyncClient` mocked for Tor network operations
   - `asyncio.create_subprocess_exec` mocked for Tor-shell subprocess operations
   - No real Tor daemon or network calls are made

5. **Network Conditions**: Tests discovered that both safe mode AND network conditions must allow `.onion` domains. Test fixtures configure both layers appropriately.

## What It Does NOT Test

- **Real Tor daemon integration**: No actual Tor service is started or connected to
- **Real network calls**: All HTTP/SOCKS requests are mocked
- **Real subprocess execution**: All subprocess calls are mocked
- **End-to-end API tests**: Tests focus on policy + plugin layers, not FastAPI endpoints
- **Audit logging integration**: Tests don't verify audit entries are created

## Running the Tests

```bash
# Run only the new Tor policy tests
pytest tests/test_tor_plugins.py -v

# Run all Tor-related tests
pytest tests/test_tor_plugins.py tests/test_builtin_tor.py tests/test_builtin_tor_shell.py -v

# Run full test suite
pytest -q
```

## Test Matrix

| Test Category | Safe Mode | Allow Rule | Network Condition | Expected Result |
|--------------|-----------|------------|-------------------|-----------------|
| Default blocking | True | None | Default (*.onion denied) | DENY |
| Explicit allow | True | `tor_fetch` | `*.onion` allowed | ALLOW |
| Partial allow | True | `tor_fetch` only | `*.onion` allowed | ALLOW for tor_fetch, DENY for others |
| Wildcard allow | True | `tor_.*` | Any | ALLOW all tor_* |

## CI Compatibility

All tests are designed to run offline without:
- Tor daemon
- Network access
- Subprocess execution
- External dependencies

The full test suite passes: **1784 passed, 3 skipped, 8 warnings**
