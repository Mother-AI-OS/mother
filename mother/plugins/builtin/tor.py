"""Built-in Tor plugin for Mother AI OS.

Provides anonymous browsing and darknet access through Tor network.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import httpx

from ..base import PluginBase, PluginResult
from ..manifest import (
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
)


def _create_manifest() -> PluginManifest:
    """Create the Tor plugin manifest programmatically."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="tor",
            version="1.0.0",
            description="Tor Browser and darknet access for Mother AI OS",
            author="David Sanker <david@lawkraft.com>",
            license="MIT",
        ),
        capabilities=[
            # Check Tor status
            CapabilitySpec(
                name="tor_check_status",
                description="Check if Tor service is running and accessible. Verifies Tor proxy connection and checks current exit node IP.",
                confirmation_required=False,
                timeout=15,
                parameters=[],
            ),
            # Fetch via Tor
            CapabilitySpec(
                name="tor_fetch",
                description="Fetch content from a URL through Tor proxy. Supports both regular HTTP/HTTPS and .onion addresses.",
                confirmation_required=False,
                timeout=60,
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="URL to fetch (can be .onion address)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Request timeout in seconds (default: 30)",
                        required=False,
                        default=30,
                    ),
                    ParameterSpec(
                        name="method",
                        type=ParameterType.STRING,
                        description="HTTP method (default: GET)",
                        required=False,
                        default="GET",
                    ),
                ],
            ),
            # Browse onion site
            CapabilitySpec(
                name="tor_browse",
                description="Browse a .onion site using terminal browser (w3m) through Tor. Opens interactive text-based browser.",
                confirmation_required=False,
                timeout=120,
                parameters=[
                    ParameterSpec(
                        name="url",
                        type=ParameterType.STRING,
                        description="Onion URL to browse",
                        required=True,
                    ),
                ],
            ),
            # Start Tor service
            CapabilitySpec(
                name="tor_start",
                description="Start the Tor service. Requires system permissions to start tor@default service.",
                confirmation_required=True,
                timeout=30,
                parameters=[],
            ),
            # Stop Tor service
            CapabilitySpec(
                name="tor_stop",
                description="Stop the Tor service.",
                confirmation_required=True,
                timeout=15,
                parameters=[],
            ),
            # Get new identity
            CapabilitySpec(
                name="tor_new_identity",
                description="Request a new Tor circuit to change exit node IP. Uses Tor control port signal.",
                confirmation_required=False,
                timeout=10,
                parameters=[],
            ),
            # Get verified onion sites
            CapabilitySpec(
                name="tor_verified_sites",
                description="Get list of verified working onion sites for major news organizations and services.",
                confirmation_required=False,
                timeout=5,
                parameters=[],
            ),
            # Darknet shortcuts - BBC
            CapabilitySpec(
                name="darknet_bbc",
                description="Open BBC News onion site through Tor.",
                confirmation_required=False,
                timeout=120,
                parameters=[],
            ),
            # Darknet shortcuts - CIA
            CapabilitySpec(
                name="darknet_cia",
                description="Open CIA official onion site through Tor.",
                confirmation_required=False,
                timeout=120,
                parameters=[],
            ),
            # Darknet shortcuts - DuckDuckGo
            CapabilitySpec(
                name="darknet_ddg",
                description="Open DuckDuckGo onion search through Tor.",
                confirmation_required=False,
                timeout=120,
                parameters=[],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.tor",
                **{"class": "TorPlugin"},
            ),
        ),
        permissions=[
            "tor:read",
            "tor:write",
            "network:proxy",
        ],
    )


class TorPlugin(PluginBase):
    """Built-in plugin for Tor network access and darknet browsing."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Tor plugin."""
        super().__init__(_create_manifest(), config)

        # Tor proxy configuration
        self._tor_proxy_host = config.get("tor_proxy_host", "127.0.0.1") if config else "127.0.0.1"
        self._tor_proxy_port = config.get("tor_proxy_port", 9050) if config else 9050
        self._tor_control_port = config.get("tor_control_port", 9051) if config else 9051
        self._tor_dns_port = config.get("tor_dns_port", 9053) if config else 9053

        # Browser for interactive browsing
        self._browser = config.get("browser", "w3m") if config else "w3m"

        # Verified onion sites
        self._verified_sites = {
            "news": [
                {
                    "name": "BBC News",
                    "url": "https://www.bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion/",
                    "status": "verified",
                },
                {
                    "name": "CIA",
                    "url": "http://ciadotgov4sjwlzihbbgxnqg3xiyrg7so2r2o3lt5wz5ypk4sxyjstad.onion/index.html",
                    "status": "verified",
                },
                {
                    "name": "Deutsche Welle",
                    "url": "https://www.dwnewsgngmhlplxy6o2twtfgjnrnjxbegbwqx6wnotdhkzt562tszfid.onion/",
                    "status": "verified",
                },
                {
                    "name": "Voice of America",
                    "url": "https://www.voanews5aitmne6gs2btokcacixclgfl43cv27sirgbauyyjylwpdtqd.onion/",
                    "status": "verified",
                },
                {
                    "name": "Radio Free Europe/Radio Liberty",
                    "url": "https://www.rferlo7zkwfbdc3ind3qu4lgngci6tj4ssvvk5aook7qcd5tabzid.onion/",
                    "status": "verified",
                },
                {
                    "name": "Bellingcat",
                    "url": "https://bellingcat4nqaoxbrq2mgaykkusg44trjqtjkqj7kqjxdrvm2i7sxyd.onion/",
                    "status": "verified",
                },
                {
                    "name": "The New York Times",
                    "url": "https://www.nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljscujyd.onion/",
                    "status": "verified",
                },
                {
                    "name": "ProPublica",
                    "url": "https://www.propub3r6espa33w.onion/",
                    "status": "verified",
                },
            ],
            "search": [
                {
                    "name": "DuckDuckGo",
                    "url": "https://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/",
                    "status": "verified",
                },
            ],
        }

    def _get_proxy_transport(self) -> httpx.AsyncHTTPTransport:
        """Get the SOCKS5 proxy transport for httpx."""
        proxy_url = f"socks5://{self._tor_proxy_host}:{self._tor_proxy_port}"
        return httpx.AsyncHTTPTransport(proxy=proxy_url)

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a Tor capability."""
        handlers = {
            "tor_check_status": self._tor_check_status,
            "tor_fetch": self._tor_fetch,
            "tor_browse": self._tor_browse,
            "tor_start": self._tor_start,
            "tor_stop": self._tor_stop,
            "tor_new_identity": self._tor_new_identity,
            "tor_verified_sites": self._tor_verified_sites,
            "darknet_bbc": self._darknet_bbc,
            "darknet_cia": self._darknet_cia,
            "darknet_ddg": self._darknet_ddg,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        try:
            return await handler(**params)
        except Exception as e:
            return PluginResult.error_result(
                f"Error: {e}",
                code="TOR_ERROR",
            )

    async def _tor_check_status(self) -> PluginResult:
        """Check if Tor service is running and accessible."""
        # First check if Tor proxy port is accessible
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self._tor_proxy_host, self._tor_proxy_port))
            sock.close()

            if result != 0:
                return PluginResult.success_result(
                    data={
                        "status": "inactive",
                        "proxy_accessible": False,
                        "proxy_host": self._tor_proxy_host,
                        "proxy_port": self._tor_proxy_port,
                    }
                )
        except Exception as e:
            return PluginResult.error_result(
                f"Failed to check Tor proxy: {e}",
                code="PROXY_CHECK_FAILED",
            )

        # Verify Tor is actually working by checking IP
        try:
            async with httpx.AsyncClient(
                transport=self._get_proxy_transport(),
                timeout=10.0,
            ) as client:
                response = await client.get("https://check.torproject.org/api/ip")

                if response.status_code == 200:
                    data = response.json()
                    return PluginResult.success_result(
                        data={
                            "status": "active",
                            "proxy_accessible": True,
                            "proxy_host": self._tor_proxy_host,
                            "proxy_port": self._tor_proxy_port,
                            "is_tor": data.get("IsTor", False),
                            "ip": data.get("IP", "unknown"),
                        }
                    )
                else:
                    return PluginResult.success_result(
                        data={
                            "status": "active",
                            "proxy_accessible": True,
                            "proxy_host": self._tor_proxy_host,
                            "proxy_port": self._tor_proxy_port,
                            "is_tor": "unknown",
                            "ip": "unknown",
                        }
                    )
        except Exception as e:
            return PluginResult.success_result(
                data={
                    "status": "active",
                    "proxy_accessible": True,
                    "proxy_host": self._tor_proxy_host,
                    "proxy_port": self._tor_proxy_port,
                    "is_tor": "unknown",
                    "ip": "unknown",
                    "note": f"Could not verify Tor status: {e}",
                }
            )

    async def _tor_fetch(self, url: str, timeout: int = 30, method: str = "GET") -> PluginResult:
        """Fetch content from URL through Tor proxy."""
        # Ensure URL starts with http:// or https://
        if not url.startswith(("http://", "https://")):
            if url.endswith(".onion"):
                url = "http://" + url
            else:
                url = "https://" + url

        try:
            async with httpx.AsyncClient(
                transport=self._get_proxy_transport(),
                timeout=timeout,
                follow_redirects=True,
            ) as client:
                if method.upper() == "GET":
                    response = await client.get(url)
                elif method.upper() == "POST":
                    response = await client.post(url)
                elif method.upper() == "HEAD":
                    response = await client.head(url)
                else:
                    return PluginResult.error_result(
                        f"Unsupported HTTP method: {method}",
                        code="UNSUPPORTED_METHOD",
                    )

                return PluginResult.success_result(
                    data={
                        "url": str(response.url),
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "content": response.text,
                        "content_length": len(response.content),
                        "encoding": response.encoding,
                    },
                    raw_output=response.text[:10000],  # First 10k chars
                )
        except httpx.TimeoutException:
            return PluginResult.timeout_result(timeout)
        except httpx.ConnectError as e:
            return PluginResult.error_result(
                f"Connection failed. Tor may not be running: {e}",
                code="CONNECT_ERROR",
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Failed to fetch URL: {e}",
                code="FETCH_FAILED",
            )

    async def _tor_browse(self, url: str) -> PluginResult:
        """Browse .onion site in terminal browser through Tor."""
        # Ensure URL starts with http:// or https://
        if not url.startswith(("http://", "https://")):
            if url.endswith(".onion"):
                url = "http://" + url
            else:
                url = "https://" + url

        try:
            # Use torsocks to force w3m through Tor
            process = await asyncio.create_subprocess_exec(
                "torsocks",
                self._browser,
                "-dump",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=120,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return PluginResult.timeout_result(120)

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if process.returncode == 0:
                return PluginResult.success_result(
                    data={
                        "url": url,
                        "browser": self._browser,
                        "exit_code": process.returncode,
                        "content": stdout_str,
                    },
                    raw_output=stdout_str,
                )
            else:
                return PluginResult.error_result(
                    f"Browser failed with exit code {process.returncode}: {stderr_str}",
                    code="BROWSER_FAILED",
                )

        except FileNotFoundError:
            return PluginResult.error_result(
                f"Browser '{self._browser}' not found. Install with: sudo apt install w3m",
                code="BROWSER_NOT_FOUND",
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Failed to browse URL: {e}",
                code="BROWSE_FAILED",
            )

    async def _tor_start(self) -> PluginResult:
        """Start Tor service."""
        try:
            process = await asyncio.create_subprocess_exec(
                "systemctl",
                "start",
                "tor@default",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if process.returncode == 0:
                return PluginResult.success_result(
                    data={
                        "action": "start",
                        "service": "tor@default",
                        "success": True,
                        "output": stdout_str,
                    }
                )
            else:
                return PluginResult.error_result(
                    f"Failed to start Tor: {stderr_str}",
                    code="START_FAILED",
                )

        except Exception as e:
            return PluginResult.error_result(
                f"Failed to start Tor service: {e}",
                code="START_ERROR",
            )

    async def _tor_stop(self) -> PluginResult:
        """Stop Tor service."""
        try:
            process = await asyncio.create_subprocess_exec(
                "systemctl",
                "stop",
                "tor@default",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if process.returncode == 0:
                return PluginResult.success_result(
                    data={
                        "action": "stop",
                        "service": "tor@default",
                        "success": True,
                        "output": stdout_str,
                    }
                )
            else:
                return PluginResult.error_result(
                    f"Failed to stop Tor: {stderr_str}",
                    code="STOP_FAILED",
                )

        except Exception as e:
            return PluginResult.error_result(
                f"Failed to stop Tor service: {e}",
                code="STOP_ERROR",
            )

    async def _tor_new_identity(self) -> PluginResult:
        """Request new Tor circuit (change IP)."""
        try:
            # Send NEWNYM signal to Tor control port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self._tor_proxy_host, self._tor_control_port))

            # Authenticate (default is no password for local)
            sock.sendall(b'AUTHENTICATE ""\r\n')
            auth_response = sock.recv(1024).decode()

            if "250" not in auth_response:
                sock.close()
                return PluginResult.error_result(
                    f"Tor control authentication failed: {auth_response}",
                    code="AUTH_FAILED",
                )

            # Send NEWNYM signal
            sock.sendall(b"SIGNAL NEWNYM\r\n")
            signal_response = sock.recv(1024).decode()
            sock.close()

            if "250" in signal_response:
                return PluginResult.success_result(
                    data={
                        "action": "new_identity",
                        "success": True,
                        "message": "New Tor circuit requested. IP will change on next connection.",
                    }
                )
            else:
                return PluginResult.error_result(
                    f"NEWNYM signal failed: {signal_response}",
                    code="SIGNAL_FAILED",
                )

        except ConnectionRefusedError:
            return PluginResult.error_result(
                "Tor control port not accessible. Ensure ControlPort is set in torrc.",
                code="CONTROL_PORT_CLOSED",
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Failed to request new identity: {e}",
                code="NEW_IDENTITY_FAILED",
            )

    async def _tor_verified_sites(self) -> PluginResult:
        """Get list of verified working onion sites."""
        return PluginResult.success_result(
            data=self._verified_sites,
        )

    async def _darknet_bbc(self) -> PluginResult:
        """Open BBC News via Tor."""
        bbc_url = "https://www.bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion/"
        return await self._tor_browse(bbc_url)

    async def _darknet_cia(self) -> PluginResult:
        """Open CIA site via Tor."""
        cia_url = "http://ciadotgov4sjwlzihbbgxnqg3xiyrg7so2r2o3lt5wz5ypk4sxyjstad.onion/index.html"
        return await self._tor_browse(cia_url)

    async def _darknet_ddg(self) -> PluginResult:
        """Open DuckDuckGo via Tor."""
        ddg_url = "https://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/"
        return await self._tor_browse(ddg_url)


# Export the plugin class and manifest
__all__ = ["TorPlugin", "_create_manifest"]
