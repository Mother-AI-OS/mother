"""Document transmission tool wrapper for Mother.

Transmit documents via Email, Fax, Post, or beA.
"""

import os
from pathlib import Path
from typing import Any

from .base import ToolWrapper


class TransmitTool(ToolWrapper):
    """Universal document transmission.

    Send documents via Email, Fax, Post, or beA (German lawyer mailbox).
    """

    def __init__(
        self,
        binary: str | None = None,
        timeout: int = 120,
    ):
        """Initialize transmit wrapper.

        Args:
            binary: Path to transmit script
            timeout: Command timeout in seconds
        """
        if binary is None:
            binary = str(Path.home() / ".local" / "bin" / "transmit")

        super().__init__(
            binary=binary,
            timeout=timeout,
        )
        # Ensure mailcraft password is set
        os.environ.setdefault("MAILCRAFT_PASSWORD", "fuckyou")

    @property
    def name(self) -> str:
        return "transmit"

    @property
    def description(self) -> str:
        return "Transmit documents via Email, Fax, Post, or beA"

    def get_commands(self) -> dict[str, dict]:
        return {
            "email": {
                "description": "Send document via email",
                "parameters": [
                    {
                        "name": "document",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Path to PDF document to send",
                    },
                    {
                        "name": "to",
                        "type": "string",
                        "required": True,
                        "description": "Recipient name",
                    },
                    {
                        "name": "email",
                        "type": "string",
                        "required": True,
                        "description": "Recipient email address",
                    },
                    {
                        "name": "subject",
                        "type": "string",
                        "required": False,
                        "description": "Email subject line",
                    },
                    {
                        "name": "cover",
                        "type": "string",
                        "required": False,
                        "description": "Cover letter / email body text",
                    },
                    {
                        "name": "reference",
                        "type": "string",
                        "required": False,
                        "description": "Case reference (Aktenzeichen)",
                    },
                ],
                "confirmation_required": True,
            },
            "fax": {
                "description": "Send document via fax (simple-fax.de)",
                "parameters": [
                    {
                        "name": "document",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Path to PDF document to send",
                    },
                    {
                        "name": "to",
                        "type": "string",
                        "required": True,
                        "description": "Recipient name",
                    },
                    {
                        "name": "fax",
                        "type": "string",
                        "required": True,
                        "description": "Recipient fax number (e.g., +49 221 12345678)",
                    },
                    {
                        "name": "subject",
                        "type": "string",
                        "required": False,
                        "description": "Fax subject/header",
                    },
                    {
                        "name": "cover",
                        "type": "string",
                        "required": False,
                        "description": "Cover page text",
                    },
                    {
                        "name": "reference",
                        "type": "string",
                        "required": False,
                        "description": "Case reference (Aktenzeichen)",
                    },
                ],
                "confirmation_required": True,
            },
            "post": {
                "description": "Send document via postal mail (LetterXpress)",
                "parameters": [
                    {
                        "name": "document",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Path to PDF document to send",
                    },
                    {
                        "name": "to",
                        "type": "string",
                        "required": True,
                        "description": "Recipient name",
                    },
                    {
                        "name": "street",
                        "type": "string",
                        "required": True,
                        "description": "Street address",
                    },
                    {
                        "name": "plz",
                        "type": "string",
                        "required": True,
                        "description": "Postal code (PLZ)",
                    },
                    {
                        "name": "city",
                        "type": "string",
                        "required": True,
                        "description": "City",
                    },
                    {
                        "name": "country",
                        "type": "string",
                        "required": False,
                        "description": "Country code (default: DE)",
                    },
                    {
                        "name": "reference",
                        "type": "string",
                        "required": False,
                        "description": "Case reference (Aktenzeichen)",
                    },
                ],
                "confirmation_required": True,
            },
            "bea": {
                "description": "Send document via beA (German lawyer mailbox)",
                "parameters": [
                    {
                        "name": "document",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Path to PDF document to send",
                    },
                    {
                        "name": "to",
                        "type": "string",
                        "required": True,
                        "description": "Recipient name (court or lawyer)",
                    },
                    {
                        "name": "safe_id",
                        "type": "string",
                        "required": True,
                        "description": "Recipient SAFE-ID (e.g., DE.BRAK.12345)",
                    },
                    {
                        "name": "subject",
                        "type": "string",
                        "required": False,
                        "description": "Message subject",
                    },
                    {
                        "name": "reference",
                        "type": "string",
                        "required": True,
                        "description": "Case reference / Aktenzeichen (e.g., 123 C 456/24)",
                    },
                ],
                "confirmation_required": True,
            },
            "channels": {
                "description": "List available transmission channels and their status",
                "parameters": [],
            },
            "history": {
                "description": "Show transmission history",
                "parameters": [
                    {
                        "name": "limit",
                        "type": "integer",
                        "required": False,
                        "description": "Number of entries to show",
                    },
                ],
            },
        }

    def build_command(self, command: str, args: dict[str, Any]) -> list[str]:
        """Build command for transmit CLI."""
        cmd = [self.binary]

        if command == "channels":
            cmd.append("channels")

        elif command == "history":
            cmd.append("history")
            if args.get("limit"):
                cmd.extend(["--limit", str(args["limit"])])

        elif command in ("email", "fax", "post", "bea"):
            # Document path first
            document = args.get("document", "")
            cmd.append(document)

            # Channel
            cmd.extend(["--via", command])

            # Common options
            if args.get("to"):
                cmd.extend(["--to", args["to"]])
            if args.get("subject"):
                cmd.extend(["--subject", args["subject"]])
            if args.get("cover"):
                cmd.extend(["--cover", args["cover"]])
            if args.get("reference"):
                cmd.extend(["--reference", args["reference"]])

            # Channel-specific options
            if command == "email" and args.get("email"):
                cmd.extend(["--email", args["email"]])
            elif command == "fax" and args.get("fax"):
                cmd.extend(["--fax", args["fax"]])
            elif command == "post":
                if args.get("street"):
                    cmd.extend(["--street", args["street"]])
                if args.get("plz"):
                    cmd.extend(["--plz", args["plz"]])
                if args.get("city"):
                    cmd.extend(["--city", args["city"]])
                if args.get("country"):
                    cmd.extend(["--country", args["country"]])
            elif command == "bea" and args.get("safe_id"):
                cmd.extend(["--safe-id", args["safe_id"]])

            # No confirmation flag - Mother handles confirmation
            cmd.append("--no-confirm")

        return cmd

    def parse_output(self, command: str, stdout: str, stderr: str) -> Any | None:
        """Parse transmit output."""
        output = stdout + stderr

        if "successfully" in output.lower() or "sent" in output.lower():
            return {
                "success": True,
                "message": output.strip(),
            }
        elif "error" in output.lower() or "failed" in output.lower():
            return {
                "success": False,
                "error": output.strip(),
            }

        return {"raw_output": output.strip()}
