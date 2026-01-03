"""Mailcraft CLI tool wrapper."""

import re
from typing import Any, Optional

from .base import ToolWrapper, ToolResult
from ..parsers.output import OutputParser, strip_ansi


class MailcraftTool(ToolWrapper):
    """Wrapper for mailcraft CLI - email management."""

    def __init__(self, binary: str, password: Optional[str] = None, timeout: int = 300):
        env_vars = {}
        if password:
            env_vars["MAILCRAFT_PASSWORD"] = password

        super().__init__(
            binary=str(binary),
            env_vars=env_vars,
            timeout=timeout,
        )
        self._parser = OutputParser()

    @property
    def name(self) -> str:
        return "mailcraft"

    @property
    def description(self) -> str:
        return "Email management tool with AI features - fetch, list, read, search, send emails"

    def get_commands(self) -> dict[str, dict]:
        return {
            "fetch": {
                "description": "Fetch emails from server and store locally. By default fetches from all configured accounts.",
                "parameters": [
                    {
                        "name": "account",
                        "type": "string",
                        "flag": "--account",
                        "description": "Specific account name (omit for all accounts)",
                    },
                    {
                        "name": "folder",
                        "type": "string",
                        "flag": "--folder",
                        "default": "INBOX",
                        "description": "Folder to fetch from",
                    },
                    {
                        "name": "limit",
                        "type": "integer",
                        "flag": "--limit",
                        "default": 50,
                        "description": "Maximum messages to fetch per account",
                    },
                    {
                        "name": "since",
                        "type": "string",
                        "flag": "--since",
                        "description": "Fetch since date (YYYY-MM-DD)",
                    },
                ],
            },
            "list": {
                "description": "List emails in a folder, showing ID, read status, sender, subject, and date",
                "parameters": [
                    {
                        "name": "account",
                        "type": "string",
                        "flag": "--account",
                        "description": "Account name",
                    },
                    {
                        "name": "folder",
                        "type": "string",
                        "flag": "--folder",
                        "default": "INBOX",
                        "description": "Folder to list",
                    },
                    {
                        "name": "limit",
                        "type": "integer",
                        "flag": "--limit",
                        "default": 20,
                        "description": "Number of messages to show",
                    },
                    {
                        "name": "unread",
                        "type": "boolean",
                        "flag": "--unread",
                        "description": "Show only unread messages",
                    },
                ],
            },
            "read": {
                "description": "Read the full content of an email by its ID",
                "parameters": [
                    {
                        "name": "message_id",
                        "type": "integer",
                        "positional": True,
                        "required": True,
                        "description": "Email ID to read",
                    },
                ],
            },
            "search": {
                "description": "Search emails by subject, sender, or content",
                "parameters": [
                    {
                        "name": "query",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Search query",
                    },
                    {
                        "name": "account",
                        "type": "string",
                        "flag": "--account",
                        "description": "Account to search in",
                    },
                    {
                        "name": "folder",
                        "type": "string",
                        "flag": "--folder",
                        "description": "Folder to search in",
                    },
                    {
                        "name": "limit",
                        "type": "integer",
                        "flag": "--limit",
                        "default": 20,
                        "description": "Maximum results",
                    },
                ],
            },
            "send": {
                "description": "Send an email. Requires confirmation before sending.",
                "confirmation_required": True,
                "parameters": [
                    {
                        "name": "to",
                        "type": "array",
                        "flag": "--to",
                        "required": True,
                        "description": "Recipient email address(es)",
                    },
                    {
                        "name": "subject",
                        "type": "string",
                        "flag": "--subject",
                        "required": True,
                        "description": "Email subject",
                    },
                    {
                        "name": "body",
                        "type": "string",
                        "flag": "--body",
                        "required": True,
                        "description": "Email body text",
                    },
                    {
                        "name": "cc",
                        "type": "array",
                        "flag": "--cc",
                        "description": "CC recipients",
                    },
                    {
                        "name": "bcc",
                        "type": "array",
                        "flag": "--bcc",
                        "description": "BCC recipients",
                    },
                    {
                        "name": "attach",
                        "type": "array",
                        "flag": "--attach",
                        "description": "File paths to attach",
                    },
                    {
                        "name": "account",
                        "type": "string",
                        "flag": "--account",
                        "description": "Account to send from",
                    },
                ],
            },
            "reply": {
                "description": "Reply to an existing email",
                "confirmation_required": True,
                "parameters": [
                    {
                        "name": "message_id",
                        "type": "integer",
                        "positional": True,
                        "required": True,
                        "description": "ID of email to reply to",
                    },
                    {
                        "name": "body",
                        "type": "string",
                        "flag": "--body",
                        "required": True,
                        "description": "Reply body text",
                    },
                    {
                        "name": "reply_all",
                        "type": "boolean",
                        "flag": "--all",
                        "description": "Reply to all recipients",
                    },
                ],
            },
            "move": {
                "description": "Move an email to another folder",
                "parameters": [
                    {
                        "name": "message_id",
                        "type": "integer",
                        "positional": True,
                        "required": True,
                        "description": "Email ID to move",
                    },
                    {
                        "name": "dest_folder",
                        "type": "string",
                        "flag": "--to",
                        "required": True,
                        "description": "Destination folder",
                    },
                ],
            },
            "delete": {
                "description": "Delete an email (moves to trash by default)",
                "confirmation_required": True,
                "parameters": [
                    {
                        "name": "message_id",
                        "type": "integer",
                        "positional": True,
                        "required": True,
                        "description": "Email ID to delete",
                    },
                    {
                        "name": "permanent",
                        "type": "boolean",
                        "flag": "--permanent",
                        "description": "Permanently delete (skip trash)",
                    },
                    {
                        "name": "force",
                        "type": "boolean",
                        "flag": "--force",
                        "description": "Skip confirmation",
                    },
                ],
            },
            "semantic_search": {
                "description": "Search emails using AI-powered semantic similarity",
                "parameters": [
                    {
                        "name": "query",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Semantic search query",
                    },
                    {
                        "name": "account",
                        "type": "string",
                        "flag": "--account",
                        "description": "Account to search",
                    },
                    {
                        "name": "limit",
                        "type": "integer",
                        "flag": "--limit",
                        "default": 10,
                        "description": "Maximum results",
                    },
                ],
            },
            "categorize": {
                "description": "Categorize emails using AI",
                "parameters": [
                    {
                        "name": "account",
                        "type": "string",
                        "flag": "--account",
                        "description": "Account to categorize",
                    },
                    {
                        "name": "folder",
                        "type": "string",
                        "flag": "--folder",
                        "default": "INBOX",
                        "description": "Folder to categorize",
                    },
                    {
                        "name": "limit",
                        "type": "integer",
                        "flag": "--limit",
                        "default": 50,
                        "description": "Maximum emails to process",
                    },
                ],
            },
            "clean_spam": {
                "description": "Detect and clean spam/marketing emails using AI",
                "parameters": [
                    {
                        "name": "account",
                        "type": "string",
                        "flag": "--account",
                        "description": "Account to clean",
                    },
                    {
                        "name": "dry_run",
                        "type": "boolean",
                        "flag": "--dry-run",
                        "description": "Show what would be done without doing it",
                    },
                ],
            },
            "folders": {
                "description": "List email folders for an account",
                "parameters": [
                    {
                        "name": "account",
                        "type": "string",
                        "flag": "--account",
                        "description": "Account name",
                    },
                    {
                        "name": "refresh",
                        "type": "boolean",
                        "flag": "--refresh",
                        "description": "Refresh folders from server",
                    },
                ],
            },
        }

    def parse_output(
        self, command: str, stdout: str, stderr: str
    ) -> Optional[Any]:
        """Parse mailcraft output into structured data."""
        if command == "list":
            return self._parse_email_list(stdout)
        elif command == "read":
            return self._parse_email_content(stdout)
        elif command == "search":
            return self._parse_email_list(stdout)
        elif command == "fetch":
            return self._parse_fetch_summary(stdout)
        elif command in ("send", "reply"):
            return self._parse_send_confirmation(stdout)
        elif command == "folders":
            return self._parse_folders(stdout)

        return {"raw_output": strip_ansi(stdout)}

    def _parse_email_list(self, output: str) -> dict:
        """Parse email list table output."""
        # Use dedicated mailcraft parser
        emails = self._parser.parse_mailcraft_list(output)

        if emails:
            # Filter out header row if it got included
            emails = [e for e in emails if e.get("from") and "From" not in e.get("from", "")]

            # Clean up status to detect unread
            for email in emails:
                status = email.get("status", "")
                email["unread"] = "●" in status or "…" in status

            return {"emails": emails, "count": len(emails)}

        return {"emails": [], "count": 0, "raw_output": strip_ansi(output)}

    def _parse_email_content(self, output: str) -> dict:
        """Parse email read output."""
        headers = self._parser.extract_email_header(output)
        body = self._parser.extract_body(output, "Message")

        return {
            "headers": headers,
            "body": body,
        }

    def _parse_fetch_summary(self, output: str) -> dict:
        """Parse fetch command summary."""
        clean = strip_ansi(output)
        result = {"total": 0, "new": 0, "accounts": []}

        # Extract per-account info
        account_pattern = r"Fetching from\s+(\S+@\S+)"
        accounts = re.findall(account_pattern, clean)
        result["accounts"] = accounts

        # Sum up totals
        count_pattern = r"(\d+)\s+messages,\s+(\d+)\s+new"
        for total, new in re.findall(count_pattern, clean):
            result["total"] += int(total)
            result["new"] += int(new)

        return result

    def _parse_send_confirmation(self, output: str) -> dict:
        """Parse send/reply confirmation."""
        clean = strip_ansi(output).lower()
        success = "sent successfully" in clean

        msg_id = None
        match = re.search(r"message-id:\s*(.+)", strip_ansi(output), re.IGNORECASE)
        if match:
            msg_id = match.group(1).strip()

        return {"success": success, "message_id": msg_id}

    def _parse_folders(self, output: str) -> dict:
        """Parse folders list output."""
        clean = strip_ansi(output)
        folders = []

        for line in clean.split("\n"):
            line = line.strip()
            if line and not line.startswith("-") and not "folder" in line.lower():
                folders.append(line)

        return {"folders": folders}
