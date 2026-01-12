"""Built-in Tor shell wrapper plugin for Mother AI OS.

Wraps existing darknet bash commands for Mother integration.
"""

from __future__ import annotations

import asyncio
from typing import Any

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
    """Create the Tor shell wrapper plugin manifest programmatically."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="tor-shell",
            version="1.0.0",
            description="Shell command wrappers for darknet functionality",
            author="David Sanker <david@lawkraft.com>",
            license="MIT",
        ),
        capabilities=[
            # Deutsche Welle
            CapabilitySpec(
                name="darknet_dw",
                description="Open Deutsche Welle news via Tor using the darknet command.",
                confirmation_required=False,
                timeout=120,
                parameters=[],
            ),
            # Voice of America
            CapabilitySpec(
                name="darknet_voa",
                description="Open Voice of America news via Tor using the darknet command.",
                confirmation_required=False,
                timeout=120,
                parameters=[],
            ),
            # Radio Free Europe
            CapabilitySpec(
                name="darknet_rferl",
                description="Open Radio Free Europe/Radio Liberty news via Tor using the darknet command.",
                confirmation_required=False,
                timeout=120,
                parameters=[],
            ),
            # Bellingcat
            CapabilitySpec(
                name="darknet_bellingcat",
                description="Open Bellingcat investigative journalism via Tor using the darknet command.",
                confirmation_required=False,
                timeout=120,
                parameters=[],
            ),
            # ProPublica
            CapabilitySpec(
                name="darknet_propublica",
                description="Open ProPublica investigative journalism via Tor using the darknet command.",
                confirmation_required=False,
                timeout=120,
                parameters=[],
            ),
            # The New York Times
            CapabilitySpec(
                name="darknet_nyt",
                description="Open The New York Times via Tor using the darknet command.",
                confirmation_required=False,
                timeout=120,
                parameters=[],
            ),
            # Show darknet bookmarks
            CapabilitySpec(
                name="darknet_bookmarks",
                description="List all available darknet shortcuts and bookmarks.",
                confirmation_required=False,
                timeout=10,
                parameters=[],
            ),
            # Show news sites
            CapabilitySpec(
                name="darknet_news",
                description="List all verified news onion sites available through darknet.",
                confirmation_required=False,
                timeout=10,
                parameters=[],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.tor_shell",
                **{"class": "TorShellPlugin"},
            ),
        ),
        permissions=[
            "shell:execute",
            "tor:read",
        ],
    )


class TorShellPlugin(PluginBase):
    """Built-in plugin for wrapping darknet shell commands."""

    # Verified onion sites for quick access
    _ONION_SITES = {
        "dw": "https://www.dwnewsgngmhlplxy6o2twtfgjnrnjxbegbwqx6wnotdhkzt562tszfid.onion/",
        "voa": "https://www.voanews5aitmne6gs2btokcacixclgfl43cv27sirgbauyyjylwpdtqd.onion/",
        "rferl": "https://www.rferlo7zkwfbdc3ind3qu4lgngci6tj4ssvvk5aook7qcd5tabzid.onion/",
        "bellingcat": "https://bellingcat4nqaoxbrq2mgaykkusg44trjqtjkqj7kqjxdrvm2i7sxyd.onion/",
        "propub": "https://www.propub3r6espa33w.onion/",
        "nyt": "https://www.nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljscujyd.onion/",
    }

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Tor shell plugin."""
        super().__init__(_create_manifest(), config)

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a Tor shell capability."""
        handlers = {
            "darknet_dw": ("dw", self._darknet_browse),
            "darknet_voa": ("voa", self._darknet_browse),
            "darknet_rferl": ("rferl", self._darknet_browse),
            "darknet_bellingcat": ("bellingcat", self._darknet_browse),
            "darknet_propublica": ("propub", self._darknet_browse),
            "darknet_nyt": ("nyt", self._darknet_browse),
            "darknet_bookmarks": (None, self._darknet_bookmarks),
            "darknet_news": (None, self._darknet_news),
        }

        handler_info = handlers.get(capability)
        if not handler_info:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        try:
            site_key, handler = handler_info
            if site_key is None:
                # Informational commands don't need a site key
                return await handler(**params)
            else:
                return await handler(site_key)
        except Exception as e:
            return PluginResult.error_result(
                f"Error: {e}",
                code="TOR_SHELL_ERROR",
            )

    async def _darknet_browse(self, site_key: str) -> PluginResult:
        """Browse to an onion site using torsocks w3m."""
        url = self._ONION_SITES.get(site_key)
        if not url:
            return PluginResult.error_result(
                f"Unknown site key: {site_key}",
                code="UNKNOWN_SITE",
            )

        site_names = {
            "dw": "Deutsche Welle",
            "voa": "Voice of America",
            "rferl": "Radio Free Europe/Radio Liberty",
            "bellingcat": "Bellingcat",
            "propub": "ProPublica",
            "nyt": "The New York Times",
        }

        site_name = site_names.get(site_key, site_key)

        try:
            # Use torsocks with w3m to browse
            process = await asyncio.create_subprocess_exec(
                "torsocks",
                "w3m",
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
                        "site": site_name,
                        "site_key": site_key,
                        "url": url,
                        "exit_code": process.returncode,
                        "content": stdout_str,
                    },
                    raw_output=stdout_str,
                )
            else:
                return PluginResult.error_result(
                    f"Browser failed for {site_name}: {stderr_str}",
                    code="BROWSER_FAILED",
                )

        except FileNotFoundError:
            return PluginResult.error_result(
                "w3m browser not found. Install with: sudo apt install w3m",
                code="BROWSER_NOT_FOUND",
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Failed to browse {site_name}: {e}",
                code="BROWSE_FAILED",
            )

    async def _darknet_bookmarks(self) -> PluginResult:
        """List all available darknet shortcuts."""
        bookmarks = {
            "search_engines": [
                {"name": "DuckDuckGo", "command": "darknet ddg", "onion": "duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion"},
            ],
            "news_sites": [
                {"name": "BBC News", "command": "darknet bbc", "onion": "bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion"},
                {"name": "CIA", "command": "darknet cia", "onion": "ciadotgov4sjwlzihbbgxnqg3xiyrg7so2r2o3lt5wz5ypk4sxyjstad.onion"},
                {"name": "Deutsche Welle", "command": "darknet dw", "onion": "dwnewsgngmhlplxy6o2twtfgjnrnjxbegbwqx6wnotdhkzt562tszfid.onion"},
                {"name": "Voice of America", "command": "darknet voa", "onion": "voanews5aitmne6gs2btokcacixclgfl43cv27sirgbauyyjylwpdtqd.onion"},
                {"name": "Radio Free Europe", "command": "darknet rferl", "onion": "rferlo7zkwfbdc3ind3qu4lgngci6tj4ssvvk5aook7qcd5tabzid.onion"},
                {"name": "Bellingcat", "command": "darknet bellingcat", "onion": "bellingcat4nqaoxbrq2mgaykkusg44trjqtjkqj7kqjxdrvm2i7sxyd.onion"},
                {"name": "ProPublica", "command": "darknet propublica", "onion": "propub3r6espa33w.onion"},
                {"name": "New York Times", "command": "darknet nyt", "onion": "nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljscujyd.onion"},
            ],
        }

        output = "=== Darknet Bookmarks ===\n\n"
        output += "Search Engines:\n"
        for site in bookmarks["search_engines"]:
            output += f"  {site['name']}: {site['command']}\n"

        output += "\nNews Sites:\n"
        for site in bookmarks["news_sites"]:
            output += f"  {site['name']}: {site['command']}\n"

        return PluginResult.success_result(
            data=bookmarks,
            raw_output=output,
        )

    async def _darknet_news(self) -> PluginResult:
        """List all verified news onion sites."""
        news_sites = [
            {
                "name": "BBC News",
                "onion": "bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion",
                "url": "https://www.bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion/",
                "category": "News",
                "verified": True,
            },
            {
                "name": "CIA",
                "onion": "ciadotgov4sjwlzihbbgxnqg3xiyrg7so2r2o3lt5wz5ypk4sxyjstad.onion",
                "url": "http://ciadotgov4sjwlzihbbgxnqg3xiyrg7so2r2o3lt5wz5ypk4sxyjstad.onion/index.html",
                "category": "Government",
                "verified": True,
            },
            {
                "name": "Deutsche Welle",
                "onion": "dwnewsgngmhlplxy6o2twtfgjnrnjxbegbwqx6wnotdhkzt562tszfid.onion",
                "url": "https://www.dwnewsgngmhlplxy6o2twtfgjnrnjxbegbwqx6wnotdhkzt562tszfid.onion/",
                "category": "News",
                "verified": True,
            },
            {
                "name": "Voice of America",
                "onion": "voanews5aitmne6gs2btokcacixclgfl43cv27sirgbauyyjylwpdtqd.onion",
                "url": "https://www.voanews5aitmne6gs2btokcacixclgfl43cv27sirgbauyyjylwpdtqd.onion/",
                "category": "News",
                "verified": True,
            },
            {
                "name": "Radio Free Europe/Radio Liberty",
                "onion": "rferlo7zkwfbdc3ind3qu4lgngci6tj4ssvvk5aook7qcd5tabzid.onion",
                "url": "https://www.rferlo7zkwfbdc3ind3qu4lgngci6tj4ssvvk5aook7qcd5tabzid.onion/",
                "category": "News",
                "verified": True,
            },
            {
                "name": "Bellingcat",
                "onion": "bellingcat4nqaoxbrq2mgaykkusg44trjqtjkqj7kqjxdrvm2i7sxyd.onion",
                "url": "https://bellingcat4nqaoxbrq2mgaykkusg44trjqtjkqj7kqjxdrvm2i7sxyd.onion/",
                "category": "Investigative Journalism",
                "verified": True,
            },
            {
                "name": "The New York Times",
                "onion": "nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljscujyd.onion",
                "url": "https://www.nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljscujyd.onion/",
                "category": "News",
                "verified": True,
            },
            {
                "name": "ProPublica",
                "onion": "propub3r6espa33w.onion",
                "url": "https://www.propub3r6espa33w.onion/",
                "category": "Investigative Journalism",
                "verified": True,
            },
        ]

        output = "=== Verified News Onions (2025) ===\n\n"
        for site in news_sites:
            output += f"{site['name']} ({site['category']})\n"
            output += f"  {site['onion']}\n\n"

        return PluginResult.success_result(
            data={"sites": news_sites},
            raw_output=output,
        )


# Export the plugin class and manifest
__all__ = ["TorShellPlugin", "_create_manifest"]
