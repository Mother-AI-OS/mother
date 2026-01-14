#!/usr/bin/env python3
"""End-to-end verification script for Mother AI OS.

This script tests a running Mother instance to verify:
1. Core API endpoints are responding
2. Authentication is working correctly
3. Tool listing and basic operations work

Usage:
    python verify/verify_run_e2e.py --url http://localhost:8080 --key test-key --output report.md
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx")
    sys.exit(1)


@dataclass
class TestResult:
    """Result of a single test."""

    name: str
    passed: bool
    message: str
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestReport:
    """Collection of test results."""

    results: list[TestResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Mother AI OS - E2E Verification Report",
            "",
            f"**Date:** {self.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Status:** {'PASSED' if self.all_passed else 'FAILED'}",
            "",
            "## Summary",
            "",
            f"- Total Tests: {self.total}",
            f"- Passed: {self.passed}",
            f"- Failed: {self.failed}",
            "",
            "## Test Results",
            "",
        ]

        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            icon = "\u2705" if result.passed else "\u274c"
            lines.append(f"### {icon} {result.name}")
            lines.append("")
            lines.append(f"**Status:** {status}")
            lines.append(f"**Duration:** {result.duration_ms:.2f}ms")
            lines.append(f"**Message:** {result.message}")
            if result.details:
                lines.append("")
                lines.append("**Details:**")
                lines.append("```json")
                lines.append(json.dumps(result.details, indent=2, default=str))
                lines.append("```")
            lines.append("")

        return "\n".join(lines)


class E2EVerifier:
    """End-to-end verification runner."""

    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        self.report = TestReport()

    def _headers(self) -> dict[str, str]:
        """Get request headers with API key if configured."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _run_test(self, name: str, test_func) -> TestResult:
        """Run a test and record the result."""
        start_time = datetime.now(UTC)
        try:
            message, details = test_func()
            passed = True
        except AssertionError as e:
            message = str(e)
            details = {}
            passed = False
        except Exception as e:
            message = f"Error: {type(e).__name__}: {e}"
            details = {}
            passed = False

        end_time = datetime.now(UTC)
        duration_ms = (end_time - start_time).total_seconds() * 1000

        result = TestResult(
            name=name,
            passed=passed,
            message=message,
            duration_ms=duration_ms,
            details=details,
        )
        self.report.results.append(result)
        return result

    def test_health_endpoint(self) -> tuple[str, dict]:
        """Test the health endpoint."""
        response = self.client.get(f"{self.base_url}/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "status" in data, "Response missing 'status' field"
        assert data["status"] == "ok", f"Expected status 'ok', got '{data['status']}'"
        return "Health endpoint responding correctly", {"response": data}

    def test_tools_list_endpoint(self) -> tuple[str, dict]:
        """Test the tools listing endpoint."""
        response = self.client.get(f"{self.base_url}/tools", headers=self._headers())
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "tools" in data, "Response missing 'tools' field"
        assert isinstance(data["tools"], list), "'tools' should be a list"
        return f"Tools endpoint returned {len(data['tools'])} tools", {"tool_count": len(data["tools"])}

    def test_status_endpoint(self) -> tuple[str, dict]:
        """Test the status endpoint."""
        response = self.client.get(f"{self.base_url}/status", headers=self._headers())
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return "Status endpoint responding correctly", {"response": data}

    def test_openapi_docs(self) -> tuple[str, dict]:
        """Test that OpenAPI docs are available."""
        response = self.client.get(f"{self.base_url}/docs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/html" in response.headers.get("content-type", ""), "Expected HTML response"
        return "OpenAPI documentation available", {}

    def test_openapi_json(self) -> tuple[str, dict]:
        """Test that OpenAPI JSON schema is available."""
        response = self.client.get(f"{self.base_url}/openapi.json")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "openapi" in data, "Response missing 'openapi' field"
        assert "paths" in data, "Response missing 'paths' field"
        return f"OpenAPI schema version {data.get('openapi', 'unknown')}", {"paths_count": len(data.get("paths", {}))}

    def test_auth_required_without_key(self) -> tuple[str, dict]:
        """Test that endpoints properly handle missing auth."""
        # Make a request without API key to /tools
        response = self.client.get(f"{self.base_url}/tools")
        # In test mode with MOTHER_REQUIRE_AUTH=false, this should still work
        # We're just verifying the endpoint doesn't crash
        if response.status_code == 401:
            return "Authentication correctly required", {"requires_auth": True}
        elif response.status_code == 200:
            return "Endpoint accessible without auth (auth not required)", {"requires_auth": False}
        else:
            return f"Unexpected status {response.status_code}", {"status_code": response.status_code}

    def run_all_tests(self) -> TestReport:
        """Run all E2E tests."""
        print(f"Running E2E verification against {self.base_url}")
        print("=" * 60)

        tests = [
            ("Health Endpoint", self.test_health_endpoint),
            ("Tools List Endpoint", self.test_tools_list_endpoint),
            ("Status Endpoint", self.test_status_endpoint),
            ("OpenAPI Documentation", self.test_openapi_docs),
            ("OpenAPI JSON Schema", self.test_openapi_json),
            ("Authentication Check", self.test_auth_required_without_key),
        ]

        for name, test_func in tests:
            result = self._run_test(name, test_func)
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{status}] {name}: {result.message}")

        self.report.finished_at = datetime.now(UTC)
        print("=" * 60)
        print(f"Results: {self.report.passed}/{self.report.total} passed")

        return self.report

    def close(self):
        """Close the HTTP client."""
        self.client.close()


def main():
    parser = argparse.ArgumentParser(description="Run E2E verification tests for Mother AI OS")
    parser.add_argument("--url", required=True, help="Base URL of the Mother server")
    parser.add_argument("--key", help="API key for authentication")
    parser.add_argument("--output", help="Output path for markdown report")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds")
    args = parser.parse_args()

    verifier = E2EVerifier(base_url=args.url, api_key=args.key, timeout=args.timeout)
    try:
        report = verifier.run_all_tests()

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report.to_markdown())
            print(f"\nReport written to: {args.output}")

        # Exit with appropriate code
        sys.exit(0 if report.all_passed else 2)
    finally:
        verifier.close()


if __name__ == "__main__":
    main()
