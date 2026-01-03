"""PDF Merge tool wrapper for Mother."""

from pathlib import Path
from typing import Any, Optional

from .base import ToolWrapper


class PDFMergeTool(ToolWrapper):
    """Merge multiple PDFs into a single file.

    Combines multiple PDF files into one and saves to ~/Downloads.
    """

    def __init__(
        self,
        binary: str | None = None,
        timeout: int = 60,
    ):
        """Initialize PDF merge wrapper.

        Args:
            binary: Path to pdf-merge script
            timeout: Command timeout in seconds
        """
        if binary is None:
            binary = str(Path.home() / ".local" / "bin" / "pdf-merge")

        super().__init__(
            binary=binary,
            timeout=timeout,
        )

    @property
    def name(self) -> str:
        return "pdf_merge"

    @property
    def description(self) -> str:
        return "Merge multiple PDFs into one file, saved to ~/Downloads"

    def get_commands(self) -> dict[str, dict]:
        return {
            "merge": {
                "description": "Merge multiple PDF files into one",
                "parameters": [
                    {
                        "name": "output_name",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Output filename (without path, saved to ~/Downloads)",
                    },
                    {
                        "name": "files",
                        "type": "array",
                        "positional": True,
                        "required": True,
                        "description": "List of PDF file paths to merge (in order)",
                    },
                ],
            },
        }

    def build_command(self, command: str, args: dict[str, Any]) -> list[str]:
        """Build command with positional args."""
        cmd = [self.binary]

        if command == "merge":
            output_name = args.get("output_name", "merged")
            files = args.get("files", [])

            cmd.append(output_name)
            if isinstance(files, list):
                cmd.extend(files)
            else:
                cmd.append(files)

        return cmd

    def parse_output(
        self, command: str, stdout: str, stderr: str
    ) -> Optional[Any]:
        """Parse pdf-merge output."""
        if "Merged" in stdout:
            # Extract output path from "Merged N PDFs -> /path/to/file.pdf"
            for line in stdout.split("\n"):
                if "->" in line:
                    parts = line.split("->")
                    if len(parts) == 2:
                        return {
                            "success": True,
                            "output_path": parts[1].strip(),
                        }

        return {"success": False, "raw_output": stdout + stderr}
