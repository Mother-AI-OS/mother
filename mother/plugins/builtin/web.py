"""Built-in web plugin for Mother AI OS.

Provides HTTP requests and web content fetching.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from ..base import PluginBase, PluginResult
from ..manifest import (
    PluginManifest,
    PluginMetadata,
    CapabilitySpec,
    ParameterSpec,
    ParameterType,
    ExecutionSpec,
    ExecutionType,
    PythonExecutionSpec,
)


# Default user agent
DEFAULT_USER_AGENT = "Mother-AI/1.0 (https://github.com/lawkraft/mother)"

# Maximum response size (10MB)
MAX_RESPONSE_SIZE = 10 * 1024 * 1024


def _create_manifest() -> PluginManifest:
    """Create the web plugin manifest programmatically."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="web",
            version="1.0.0",
            description="HTTP requests and web content fetching for Mother AI OS",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Fetch URL content
            CapabilitySpec(
                name="fetch",
                description="Fetch content from a URL. Returns the response body as text. Good for fetching web pages, APIs, etc.",
                timeout=60,
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="The URL to fetch",
                        required=True,
                    ),
                    ParameterSpec(
                        name="headers",
                        type=ParameterType.OBJECT,
                        description="Additional HTTP headers to send",
                        required=False,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Request timeout in seconds (default: 30)",
                        required=False,
                        default=30,
                    ),
                    ParameterSpec(
                        name="follow_redirects",
                        type=ParameterType.BOOLEAN,
                        description="Follow HTTP redirects (default: true)",
                        required=False,
                        default=True,
                    ),
                ],
            ),
            # GET request with full control
            CapabilitySpec(
                name="get",
                description="Make an HTTP GET request with full control over headers, params, and response handling.",
                timeout=60,
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="The URL to request",
                        required=True,
                    ),
                    ParameterSpec(
                        name="params",
                        type=ParameterType.OBJECT,
                        description="Query parameters to add to URL",
                        required=False,
                    ),
                    ParameterSpec(
                        name="headers",
                        type=ParameterType.OBJECT,
                        description="HTTP headers to send",
                        required=False,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Request timeout in seconds (default: 30)",
                        required=False,
                        default=30,
                    ),
                ],
            ),
            # POST request
            CapabilitySpec(
                name="post",
                description="Make an HTTP POST request. Use for submitting forms, API calls, etc.",
                confirmation_required=True,
                timeout=60,
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="The URL to post to",
                        required=True,
                    ),
                    ParameterSpec(
                        name="data",
                        type=ParameterType.OBJECT,
                        description="Form data to send (application/x-www-form-urlencoded)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="json",
                        type=ParameterType.OBJECT,
                        description="JSON data to send (application/json)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="headers",
                        type=ParameterType.OBJECT,
                        description="HTTP headers to send",
                        required=False,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Request timeout in seconds (default: 30)",
                        required=False,
                        default=30,
                    ),
                ],
            ),
            # HEAD request
            CapabilitySpec(
                name="head",
                description="Make an HTTP HEAD request to get headers without downloading the body. Useful for checking if a URL exists or getting content info.",
                timeout=30,
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="The URL to check",
                        required=True,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Request timeout in seconds (default: 10)",
                        required=False,
                        default=10,
                    ),
                ],
            ),
            # Download file
            CapabilitySpec(
                name="download",
                description="Download a file from a URL to local disk.",
                timeout=300,
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="The URL to download from",
                        required=True,
                    ),
                    ParameterSpec(
                        name="destination",
                        type=ParameterType.STRING,
                        description="Local path to save the file",
                        required=True,
                    ),
                    ParameterSpec(
                        name="overwrite",
                        type=ParameterType.BOOLEAN,
                        description="Overwrite if file exists (default: false)",
                        required=False,
                        default=False,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Request timeout in seconds (default: 120)",
                        required=False,
                        default=120,
                    ),
                ],
            ),
            # Check URL
            CapabilitySpec(
                name="check_url",
                description="Check if a URL is accessible and get basic info (status, content type, size).",
                timeout=30,
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="The URL to check",
                        required=True,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Request timeout in seconds (default: 10)",
                        required=False,
                        default=10,
                    ),
                ],
            ),
            # Get JSON
            CapabilitySpec(
                name="get_json",
                description="Fetch JSON from a URL and parse it. Convenience method for JSON APIs.",
                timeout=60,
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="The URL to fetch JSON from",
                        required=True,
                    ),
                    ParameterSpec(
                        name="params",
                        type=ParameterType.OBJECT,
                        description="Query parameters",
                        required=False,
                    ),
                    ParameterSpec(
                        name="headers",
                        type=ParameterType.OBJECT,
                        description="HTTP headers",
                        required=False,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Request timeout in seconds (default: 30)",
                        required=False,
                        default=30,
                    ),
                ],
            ),
            # Extract links
            CapabilitySpec(
                name="extract_links",
                description="Fetch a web page and extract all links from it.",
                timeout=60,
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="The URL to fetch and extract links from",
                        required=True,
                    ),
                    ParameterSpec(
                        name="absolute",
                        type=ParameterType.BOOLEAN,
                        description="Convert relative URLs to absolute (default: true)",
                        required=False,
                        default=True,
                    ),
                    ParameterSpec(
                        name="filter_pattern",
                        type=ParameterType.STRING,
                        description="Regex pattern to filter links (e.g., '\\.pdf$' for PDF links)",
                        required=False,
                    ),
                ],
            ),
            # Parse URL
            CapabilitySpec(
                name="parse_url",
                description="Parse a URL into its components (scheme, host, path, query, etc.).",
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="The URL to parse",
                        required=True,
                    ),
                ],
            ),
            # Encode URL
            CapabilitySpec(
                name="encode_url",
                description="Build a URL with properly encoded query parameters.",
                parameters=[
                    ParameterSpec(
                        name="base_url",
                        type=ParameterType.STRING,
                        description="The base URL",
                        required=True,
                    ),
                    ParameterSpec(
                        name="params",
                        type=ParameterType.OBJECT,
                        description="Query parameters to add",
                        required=False,
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.web",
                **{"class": "WebPlugin"},
            ),
        ),
        permissions=[
            "network",
            "filesystem:write",  # For download capability
        ],
    )


class WebPlugin(PluginBase):
    """Built-in plugin for web requests and content fetching."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the web plugin."""
        super().__init__(_create_manifest(), config)

        # Configuration
        self._user_agent = (
            config.get("user_agent", DEFAULT_USER_AGENT) if config else DEFAULT_USER_AGENT
        )
        self._max_response_size = (
            config.get("max_response_size", MAX_RESPONSE_SIZE) if config else MAX_RESPONSE_SIZE
        )

        # Security: blocked domains
        self._blocked_domains: list[str] = []
        if config and "blocked_domains" in config:
            self._blocked_domains = config["blocked_domains"]

        # HTTP client (created lazily)
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            headers={"User-Agent": self._user_agent},
            follow_redirects=True,
            timeout=30.0,
        )

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _check_url_allowed(self, url: str) -> tuple[bool, str | None]:
        """Check if a URL is allowed.

        Returns:
            Tuple of (allowed, error_message)
        """
        try:
            parsed = urlparse(url)

            # Must have scheme
            if not parsed.scheme:
                return False, "URL must have a scheme (http:// or https://)"

            # Only allow http/https
            if parsed.scheme not in ("http", "https"):
                return False, f"Only http/https URLs are allowed, got: {parsed.scheme}"

            # Check blocked domains
            if parsed.netloc:
                for blocked in self._blocked_domains:
                    if blocked in parsed.netloc:
                        return False, f"Domain is blocked: {parsed.netloc}"

            return True, None

        except Exception as e:
            return False, f"Invalid URL: {e}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            await self.initialize()
        return self._client

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a web capability."""
        handlers = {
            "fetch": self._fetch,
            "get": self._get,
            "post": self._post,
            "head": self._head,
            "download": self._download,
            "check_url": self._check_url,
            "get_json": self._get_json,
            "extract_links": self._extract_links,
            "parse_url": self._parse_url,
            "encode_url": self._encode_url,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        try:
            return await handler(**params)
        except httpx.TimeoutException:
            return PluginResult.error_result(
                "Request timed out",
                code="TIMEOUT",
            )
        except httpx.ConnectError as e:
            return PluginResult.error_result(
                f"Connection failed: {e}",
                code="CONNECTION_ERROR",
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Error: {e}",
                code="WEB_ERROR",
            )

    async def _fetch(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        follow_redirects: bool = True,
    ) -> PluginResult:
        """Fetch content from a URL."""
        allowed, error = self._check_url_allowed(url)
        if not allowed:
            return PluginResult.error_result(error, code="URL_NOT_ALLOWED")

        client = await self._get_client()

        response = await client.get(
            url,
            headers=headers,
            timeout=timeout,
            follow_redirects=follow_redirects,
        )

        # Check response size
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > self._max_response_size:
            return PluginResult.error_result(
                f"Response too large: {content_length} bytes",
                code="RESPONSE_TOO_LARGE",
            )

        content = response.text

        # Truncate if too long
        if len(content) > self._max_response_size:
            content = content[: self._max_response_size] + "\n... (truncated)"

        return PluginResult.success_result(
            data={
                "url": str(response.url),
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "content_length": len(content),
                "content": content,
            }
        )

    async def _get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> PluginResult:
        """Make a GET request."""
        allowed, error = self._check_url_allowed(url)
        if not allowed:
            return PluginResult.error_result(error, code="URL_NOT_ALLOWED")

        client = await self._get_client()

        response = await client.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
        )

        content = response.text
        if len(content) > self._max_response_size:
            content = content[: self._max_response_size] + "\n... (truncated)"

        return PluginResult.success_result(
            data={
                "url": str(response.url),
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content_type": response.headers.get("content-type"),
                "content": content,
            }
        )

    async def _post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> PluginResult:
        """Make a POST request."""
        allowed, error = self._check_url_allowed(url)
        if not allowed:
            return PluginResult.error_result(error, code="URL_NOT_ALLOWED")

        client = await self._get_client()

        response = await client.post(
            url,
            data=data,
            json=json,
            headers=headers,
            timeout=timeout,
        )

        content = response.text
        if len(content) > self._max_response_size:
            content = content[: self._max_response_size] + "\n... (truncated)"

        return PluginResult.success_result(
            data={
                "url": str(response.url),
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content_type": response.headers.get("content-type"),
                "content": content,
            }
        )

    async def _head(
        self,
        url: str,
        timeout: int = 10,
    ) -> PluginResult:
        """Make a HEAD request."""
        allowed, error = self._check_url_allowed(url)
        if not allowed:
            return PluginResult.error_result(error, code="URL_NOT_ALLOWED")

        client = await self._get_client()

        response = await client.head(url, timeout=timeout)

        return PluginResult.success_result(
            data={
                "url": str(response.url),
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content_type": response.headers.get("content-type"),
                "content_length": response.headers.get("content-length"),
            }
        )

    async def _download(
        self,
        url: str,
        destination: str,
        overwrite: bool = False,
        timeout: int = 120,
    ) -> PluginResult:
        """Download a file from URL."""
        allowed, error = self._check_url_allowed(url)
        if not allowed:
            return PluginResult.error_result(error, code="URL_NOT_ALLOWED")

        dest_path = Path(destination).expanduser().resolve()

        # Check if destination exists
        if dest_path.exists() and not overwrite:
            return PluginResult.error_result(
                f"Destination already exists: {dest_path}",
                code="FILE_EXISTS",
            )

        # Create parent directories
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        client = await self._get_client()

        # Stream download
        async with client.stream("GET", url, timeout=timeout) as response:
            response.raise_for_status()

            total_size = 0
            with open(dest_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    total_size += len(chunk)
                    if total_size > self._max_response_size:
                        f.close()
                        dest_path.unlink()
                        return PluginResult.error_result(
                            f"Download too large (>{self._max_response_size} bytes)",
                            code="DOWNLOAD_TOO_LARGE",
                        )
                    f.write(chunk)

        return PluginResult.success_result(
            data={
                "url": url,
                "destination": str(dest_path),
                "size": total_size,
                "content_type": response.headers.get("content-type"),
            }
        )

    async def _check_url(
        self,
        url: str,
        timeout: int = 10,
    ) -> PluginResult:
        """Check if a URL is accessible."""
        allowed, error = self._check_url_allowed(url)
        if not allowed:
            return PluginResult.error_result(error, code="URL_NOT_ALLOWED")

        client = await self._get_client()

        try:
            response = await client.head(url, timeout=timeout)

            return PluginResult.success_result(
                data={
                    "url": str(response.url),
                    "accessible": True,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type"),
                    "content_length": response.headers.get("content-length"),
                    "server": response.headers.get("server"),
                }
            )
        except Exception as e:
            return PluginResult.success_result(
                data={
                    "url": url,
                    "accessible": False,
                    "error": str(e),
                }
            )

    async def _get_json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> PluginResult:
        """Fetch and parse JSON from URL."""
        allowed, error = self._check_url_allowed(url)
        if not allowed:
            return PluginResult.error_result(error, code="URL_NOT_ALLOWED")

        client = await self._get_client()

        response = await client.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
        )

        try:
            data = response.json()
            return PluginResult.success_result(
                data={
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "json": data,
                }
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Failed to parse JSON: {e}",
                code="JSON_PARSE_ERROR",
            )

    async def _extract_links(
        self,
        url: str,
        absolute: bool = True,
        filter_pattern: str | None = None,
    ) -> PluginResult:
        """Extract links from a web page."""
        allowed, error = self._check_url_allowed(url)
        if not allowed:
            return PluginResult.error_result(error, code="URL_NOT_ALLOWED")

        client = await self._get_client()

        response = await client.get(url, timeout=30)
        html = response.text

        # Simple regex to find links
        # Matches href="..." and href='...'
        link_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        links = link_pattern.findall(html)

        # Convert to absolute URLs if requested
        if absolute:
            base_url = str(response.url)
            links = [urljoin(base_url, link) for link in links]

        # Filter by pattern if provided
        if filter_pattern:
            try:
                pattern = re.compile(filter_pattern)
                links = [link for link in links if pattern.search(link)]
            except re.error as e:
                return PluginResult.error_result(
                    f"Invalid filter pattern: {e}",
                    code="INVALID_PATTERN",
                )

        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        return PluginResult.success_result(
            data={
                "url": str(response.url),
                "count": len(unique_links),
                "links": unique_links,
            }
        )

    async def _parse_url(self, url: str) -> PluginResult:
        """Parse a URL into components."""
        try:
            parsed = urlparse(url)

            return PluginResult.success_result(
                data={
                    "url": url,
                    "scheme": parsed.scheme,
                    "netloc": parsed.netloc,
                    "hostname": parsed.hostname,
                    "port": parsed.port,
                    "path": parsed.path,
                    "query": parsed.query,
                    "fragment": parsed.fragment,
                    "username": parsed.username,
                    "password": "***" if parsed.password else None,
                }
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Failed to parse URL: {e}",
                code="PARSE_ERROR",
            )

    async def _encode_url(
        self,
        base_url: str,
        params: dict[str, str] | None = None,
    ) -> PluginResult:
        """Build a URL with encoded query parameters."""
        try:
            if params:
                # Use httpx to build URL with params
                url = httpx.URL(base_url).copy_merge_params(params)
                result_url = str(url)
            else:
                result_url = base_url

            return PluginResult.success_result(
                data={
                    "url": result_url,
                    "base_url": base_url,
                    "params": params,
                }
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Failed to encode URL: {e}",
                code="ENCODE_ERROR",
            )


# Export the plugin class and manifest
__all__ = ["WebPlugin", "_create_manifest"]
