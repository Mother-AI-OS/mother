# Verification Guide

This guide explains how to verify that Mother AI OS installs and functions correctly.

## Overview

The verification harness tests:

1. **Installability** - Mother can be installed from source and via Docker
2. **Core Functionality** - Server starts, endpoints respond, plugins load
3. **Policy Enforcement** - Safe mode blocks dangerous operations
4. **Audit Logging** - Events are logged with proper redaction
5. **Plugin Inventory** - Core plugins are available

## Quick Start

### Run All Verifications

```bash
# Clone the repository
git clone https://github.com/Mother-AI-OS/mother.git
cd mother

# Run repository verification
./verify/verify_repo_install.sh

# Run Docker verification (requires Docker)
./verify/verify_docker_install.sh
```

### Run Individual Tests

```bash
# Start server in mock mode
export MOTHER_MOCK_LLM=1
export AI_PROVIDER=mock
export MOTHER_POLICY_PATH=./verify/policy.verification.yaml
mother serve &

# Run E2E tests
python verify/verify_run_e2e.py --url http://localhost:8080
```

## Verification Components

### 1. Mock LLM Provider

The mock provider enables offline testing without real API keys:

```bash
# Enable via environment variable
export MOTHER_MOCK_LLM=1

# Or set provider directly
export AI_PROVIDER=mock
```

The mock provider returns deterministic tool calls based on prompt patterns:

| Prompt Pattern | Tool Called | Arguments |
|----------------|-------------|-----------|
| "create file", "write file" | `filesystem_write` | `{path: "./workspace/test_file.txt"}` |
| "read file", "show file" | `filesystem_read` | `{path: "./workspace/test_file.txt"}` |
| "delete file" | `filesystem_delete` | `{path: "./workspace/test_file.txt"}` |
| "run command", "shell" | `shell_run_command` | `{command: "echo hello"}` |
| "fetch url", "http" | `web_fetch` | `{url: "https://example.com"}` |

### 2. Verification Policy

The verification policy (`verify/policy.verification.yaml`) enforces strict safety:

```yaml
safe_mode: true
default_action: deny

rules:
  # Allow workspace operations only
  - name: allow-workspace-read
    capability_pattern: "filesystem_read"
    action: allow
    conditions:
      param.path:
        regex: "^\\./workspace/.*"

  # Block dangerous operations
  - name: deny-delete
    capability_pattern: "filesystem_delete"
    action: deny

  - name: deny-shell
    capability_pattern: "shell_.*"
    action: deny

  - name: deny-network
    capability_pattern: "web_.*"
    action: deny
```

### 3. E2E Test Suite

The E2E test suite (`verify/verify_run_e2e.py`) runs 12 tests:

| # | Test | Description |
|---|------|-------------|
| 1 | Health Check | `/health` returns healthy |
| 2 | Status Endpoint | `/status` returns config |
| 3 | Tools Endpoint | `/tools` lists capabilities |
| 4 | Filesystem Write | Write to workspace succeeds |
| 5 | Filesystem Read | Read from workspace succeeds |
| 6 | Policy Blocks Delete | Delete is denied by policy |
| 7 | Policy Blocks Shell | Shell commands are denied |
| 8 | Policy Blocks Network | External fetch is denied |
| 9 | Audit Log Exists | Log file is created |
| 10 | Audit Log Structure | Entries have required fields |
| 11 | Audit Redaction | Secrets are redacted |
| 12 | Plugin Inventory | Core plugins are loaded |

### 4. Shell Verification Scripts

#### `verify_repo_install.sh`

Tests installation from source:

1. Check Python version (>= 3.11)
2. Create virtual environment
3. Install from source (`pip install -e .`)
4. Test CLI (`mother --help`)
5. Start server with mock LLM
6. Test health endpoint
7. Test tools endpoint
8. Run E2E verification

#### `verify_docker_install.sh`

Tests Docker deployment:

1. Check Docker availability
2. Build Docker image
3. Run container with mock LLM
4. Test health endpoint
5. Test tools endpoint
6. Verify security defaults
7. Test volume mounts
8. Verify non-root user
9. Run E2E verification

## GitHub Actions

The workflow `.github/workflows/verify-install.yml` runs automatically on:

- Push to `main`
- Pull requests to `main`
- Manual trigger

### Workflow Jobs

1. **verify-repo-install** - Install from source and run tests
2. **verify-docker-install** - Build Docker image and run tests
3. **verification-summary** - Combine reports and check results

### Artifacts

The workflow uploads these artifacts:

- `verification-report-repo` - Repository verification report
- `verification-report-docker` - Docker verification report
- `verification-summary` - Combined summary
- `logs-*` - Debug logs (on failure)

## Running Locally

### Prerequisites

- Python 3.11+
- Docker (optional, for Docker verification)
- curl

### Environment Variables

```bash
# Required for mock mode
export MOTHER_MOCK_LLM=1
export AI_PROVIDER=mock

# Policy configuration
export MOTHER_POLICY_PATH=./verify/policy.verification.yaml
export MOTHER_SAFE_MODE=true

# Server configuration
export MOTHER_HOST=127.0.0.1
export MOTHER_PORT=8080

# Disable auth for testing
export MOTHER_REQUIRE_AUTH=false
export MOTHER_API_KEY=test-key

# Enable audit logging
export MOTHER_AUDIT_ENABLED=true
```

### Manual Testing

```bash
# Create directories
mkdir -p workspace logs

# Start server
mother serve &

# Test health
curl http://localhost:8080/health

# Test tools
curl -H "X-API-Key: test-key" http://localhost:8080/tools

# Test command (should trigger mock tool call)
curl -X POST http://localhost:8080/command \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{"command": "create a test file"}'

# Test policy enforcement (should be denied)
curl -X POST http://localhost:8080/command \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{"command": "run shell command echo hello"}'

# Check audit log
cat logs/audit.jsonl | jq .

# Stop server
kill %1
```

## Verification Report

The verification produces a markdown report (`verify/verify_report.md`):

```markdown
# Mother AI OS - Verification Report

**Status:** PASS
**Timestamp:** 2024-01-12T15:30:00
**Commit:** abc1234

## Summary

- **Passed:** 12
- **Failed:** 0
- **Total:** 12

## Test Results

| Test | Status | Duration | Message |
|------|--------|----------|---------|
| 1. Health Check | PASS | 0.05s | Health check passed |
| 2. Status Endpoint | PASS | 0.03s | Provider: mock |
...
```

## Troubleshooting

### Server Won't Start

```bash
# Check for port conflicts
lsof -i :8080

# Check logs
cat verify/server.log

# Try different port
export MOTHER_PORT=9000
```

### Mock Provider Not Working

```bash
# Verify environment
echo $MOTHER_MOCK_LLM
echo $AI_PROVIDER

# Should output:
# 1 (or true)
# mock
```

### Policy Tests Failing

```bash
# Verify policy is loaded
export MOTHER_POLICY_PATH=./verify/policy.verification.yaml

# Check policy file exists
ls -la ./verify/policy.verification.yaml
```

### Docker Build Fails

```bash
# Check Docker daemon
docker info

# Build with verbose output
docker build -t mother-ai-os:test . --progress=plain

# Check build logs
docker build -t mother-ai-os:test . 2>&1 | tee build.log
```

## Adding New Tests

To add a new test to the E2E suite:

1. Add a test function in `verify/verify_run_e2e.py`:

```python
def test_my_new_test(client: VerificationClient):
    """Test X: Description."""
    def _test():
        # Your test logic
        resp = client.command("some command")
        if "expected" in resp:
            return True, "Test passed", resp
        return False, "Test failed", resp
    return _test
```

2. Add to the tests list in `run_verification()`:

```python
tests = [
    # ... existing tests ...
    ("13. My New Test", test_my_new_test(client)),
]
```

3. Update expected test count if checking in CI.

## Security Considerations

- Mock mode is for **testing only** - never use in production
- Verification policy is **restrictive** - only allows workspace access
- Audit logs may contain **redacted** sensitive data
- API key `test-key` is for testing - use strong keys in production
