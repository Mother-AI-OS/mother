"""GCP-Draft CLI tool wrapper."""

from typing import Any, Optional

from .base import ToolWrapper
from ..parsers.output import OutputParser, strip_ansi


class GCPDraftTool(ToolWrapper):
    """Wrapper for gcp-draft CLI - Google Docs template tool.

    Note: This tool is interactive by design. Only non-interactive
    commands (like 'list') are supported through this wrapper.
    """

    def __init__(self, binary: str, timeout: int = 60):
        super().__init__(
            binary=str(binary),
            timeout=timeout,
        )
        self._parser = OutputParser()

    @property
    def name(self) -> str:
        return "gcp_draft"

    @property
    def description(self) -> str:
        return "Google Docs template tool - list recent documents (limited functionality, interactive features not supported)"

    def get_commands(self) -> dict[str, dict]:
        return {
            "list": {
                "description": "List recent Google Docs documents created with this tool",
                "parameters": [],
            },
            "help": {
                "description": "Show help information for gcp-draft",
                "parameters": [],
            },
        }

    def build_command(self, command: str, args: dict[str, Any]) -> list[str]:
        """Override to handle gcp-draft's command structure."""
        # gcp-draft uses positional commands
        return [self.binary, command]

    def parse_output(
        self, command: str, stdout: str, stderr: str
    ) -> Optional[Any]:
        """Parse gcp-draft output."""
        clean = strip_ansi(stdout)

        if command == "list":
            return self._parse_list(clean)
        elif command == "help":
            return {"help": clean}

        return {"raw_output": clean}

    def _parse_list(self, output: str) -> dict:
        """Parse document list."""
        documents = []
        lines = output.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Try to extract doc URL and title
            # Format varies, but URLs contain docs.google.com
            if "docs.google.com" in line:
                documents.append({
                    "url": line,
                    "title": line.split("/")[-1] if "/" in line else line,
                })
            elif line and not line.lower().startswith(("recent", "documents", "---")):
                documents.append({
                    "title": line,
                    "url": None,
                })

        return {"documents": documents, "count": len(documents)}
