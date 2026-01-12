#!/bin/bash
# Mother AI OS - Repository Install Verification
#
# This script verifies that Mother can be installed from source and works correctly.
#
# Usage:
#   ./verify/verify_repo_install.sh
#
# Requirements:
#   - Python 3.11+
#   - git
#   - curl

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/.venv-verify"
LOG_FILE="${SCRIPT_DIR}/verify_repo_install.log"
REPORT_FILE="${SCRIPT_DIR}/verify_report.md"
SERVER_PID=""
SERVER_PORT="${MOTHER_PORT:-8080}"
API_URL="http://localhost:${SERVER_PORT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log_success() {
    log "${GREEN}[PASS]${NC} $1"
}

log_fail() {
    log "${RED}[FAIL]${NC} $1"
}

log_info() {
    log "${YELLOW}[INFO]${NC} $1"
}

# Cleanup on exit
cleanup() {
    log_info "Cleaning up..."
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        log_info "Stopping server (PID: $SERVER_PID)..."
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    # Clean up test workspace
    rm -rf "${PROJECT_DIR}/workspace/verify_*" 2>/dev/null || true
}

trap cleanup EXIT

# Initialize
init() {
    echo "" > "$LOG_FILE"
    log "=================================================="
    log "Mother AI OS - Repository Install Verification"
    log "=================================================="
    log "Date: $(date -Iseconds)"
    log "Project: $PROJECT_DIR"
    log ""
}

# Step 1: Check Python version
check_python() {
    log_info "Checking Python version..."

    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        log_success "Python $PYTHON_VERSION (>= 3.11 required)"
        return 0
    else
        log_fail "Python $PYTHON_VERSION (>= 3.11 required)"
        return 1
    fi
}

# Step 2: Create virtual environment
create_venv() {
    log_info "Creating virtual environment..."

    if [ -d "$VENV_DIR" ]; then
        log_info "Removing existing venv..."
        rm -rf "$VENV_DIR"
    fi

    python3 -m venv "$VENV_DIR"
    source "${VENV_DIR}/bin/activate"

    # Upgrade pip
    pip install --quiet --upgrade pip

    log_success "Virtual environment created at $VENV_DIR"
}

# Step 3: Install from source
install_from_source() {
    log_info "Installing Mother from source..."

    cd "$PROJECT_DIR"
    pip install --quiet -e .

    # Verify installation
    if command -v mother &> /dev/null; then
        VERSION=$(mother --version 2>&1 || echo "unknown")
        log_success "Mother installed: $VERSION"
        return 0
    else
        log_fail "Mother command not found after installation"
        return 1
    fi
}

# Step 4: Test CLI help
test_cli_help() {
    log_info "Testing CLI help..."

    if mother --help > /dev/null 2>&1; then
        log_success "mother --help works"
        return 0
    else
        log_fail "mother --help failed"
        return 1
    fi
}

# Step 5: Start server with mock LLM
start_server() {
    log_info "Starting server with mock LLM..."

    cd "$PROJECT_DIR"

    # Create directories
    mkdir -p workspace logs

    # Set environment for mock mode
    export MOTHER_MOCK_LLM=1
    export AI_PROVIDER=mock
    export MOTHER_POLICY_PATH="${SCRIPT_DIR}/policy.verification.yaml"
    export MOTHER_SAFE_MODE=true
    export MOTHER_AUDIT_ENABLED=true
    export MOTHER_HOST=127.0.0.1
    export MOTHER_PORT=$SERVER_PORT
    export MOTHER_API_KEY=test-key
    export MOTHER_REQUIRE_AUTH=false

    # Start server in background
    mother serve > "${SCRIPT_DIR}/server.log" 2>&1 &
    SERVER_PID=$!

    log_info "Server starting (PID: $SERVER_PID)..."

    # Wait for server to be ready
    local max_wait=30
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if curl -s "${API_URL}/health" > /dev/null 2>&1; then
            log_success "Server started and responding on port $SERVER_PORT"
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done

    log_fail "Server did not start within ${max_wait}s"
    cat "${SCRIPT_DIR}/server.log" >> "$LOG_FILE"
    return 1
}

# Step 6: Test health endpoint
test_health_endpoint() {
    log_info "Testing health endpoint..."

    RESPONSE=$(curl -s "${API_URL}/health")

    if echo "$RESPONSE" | grep -q "healthy"; then
        log_success "Health endpoint returns healthy"
        return 0
    else
        log_fail "Health endpoint failed: $RESPONSE"
        return 1
    fi
}

# Step 7: Test tools endpoint
test_tools_endpoint() {
    log_info "Testing tools endpoint..."

    RESPONSE=$(curl -s -H "X-API-Key: test-key" "${API_URL}/tools")

    # Check for tools array
    if echo "$RESPONSE" | grep -q "tools"; then
        TOOL_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('tools', [])))" 2>/dev/null || echo "0")
        if [ "$TOOL_COUNT" -gt 0 ]; then
            log_success "Tools endpoint returns $TOOL_COUNT tools"
            return 0
        fi
    fi

    log_fail "Tools endpoint failed: $RESPONSE"
    return 1
}

# Step 8: Run E2E verification
run_e2e_verification() {
    log_info "Running E2E verification suite..."

    cd "$PROJECT_DIR"

    # Install test dependencies
    pip install --quiet httpx

    # Run verification
    if python3 "${SCRIPT_DIR}/verify_run_e2e.py" \
        --url "$API_URL" \
        --key "test-key" \
        --output "$REPORT_FILE"; then
        log_success "E2E verification passed"
        return 0
    else
        log_fail "E2E verification failed"
        return 1
    fi
}

# Main execution
main() {
    init

    local failed=0

    check_python || failed=1
    [ $failed -eq 0 ] && create_venv || failed=1
    [ $failed -eq 0 ] && install_from_source || failed=1
    [ $failed -eq 0 ] && test_cli_help || failed=1
    [ $failed -eq 0 ] && start_server || failed=1
    [ $failed -eq 0 ] && test_health_endpoint || failed=1
    [ $failed -eq 0 ] && test_tools_endpoint || failed=1
    [ $failed -eq 0 ] && run_e2e_verification || failed=1

    log ""
    log "=================================================="
    if [ $failed -eq 0 ]; then
        log "${GREEN}REPOSITORY INSTALL VERIFICATION: PASSED${NC}"
    else
        log "${RED}REPOSITORY INSTALL VERIFICATION: FAILED${NC}"
    fi
    log "=================================================="
    log "Log file: $LOG_FILE"
    log "Report: $REPORT_FILE"

    return $failed
}

main
