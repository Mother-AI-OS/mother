"""Taxlord CLI tool wrapper."""

import re
from typing import Any

from ..parsers.output import OutputParser, strip_ansi
from .base import ToolWrapper


class TaxlordTool(ToolWrapper):
    """Wrapper for taxlord CLI - tax and document management."""

    def __init__(self, taxlord_dir: str, timeout: int = 300):
        super().__init__(
            binary="python",
            extra_args=["-m", "taxlord"],
            cwd=str(taxlord_dir),
            timeout=timeout,
        )
        self._parser = OutputParser()

    @property
    def name(self) -> str:
        return "taxlord"

    @property
    def description(self) -> str:
        return "Tax and document management - ingest invoices, search documents, prepare German tax filings"

    def get_commands(self) -> dict[str, dict]:
        return {
            "ingest": {
                "description": "Ingest documents (invoices, bank statements, receipts) into the system",
                "parameters": [
                    {
                        "name": "path",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Path to document or folder",
                    },
                    {
                        "name": "ledger",
                        "type": "string",
                        "flag": "--ledger",
                        "description": "Target ledger name",
                    },
                    {
                        "name": "doc_type",
                        "type": "choice",
                        "choices": ["invoice", "receipt", "bank_statement", "contract", "other"],
                        "flag": "--type",
                        "description": "Document type",
                    },
                    {
                        "name": "recursive",
                        "type": "boolean",
                        "flag": "--recursive",
                        "description": "Process folders recursively",
                    },
                    {
                        "name": "no_ocr",
                        "type": "boolean",
                        "flag": "--no-ocr",
                        "description": "Skip OCR processing",
                    },
                ],
            },
            "search": {
                "description": "Search documents using semantic similarity",
                "parameters": [
                    {
                        "name": "query",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Search query",
                    },
                    {
                        "name": "limit",
                        "type": "integer",
                        "flag": "--limit",
                        "default": 10,
                        "description": "Maximum results",
                    },
                    {
                        "name": "doc_type",
                        "type": "string",
                        "flag": "--type",
                        "description": "Filter by document type",
                    },
                ],
            },
            "ask": {
                "description": "Ask a question about your documents using AI",
                "parameters": [
                    {
                        "name": "question",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Question to ask",
                    },
                    {
                        "name": "doc_type",
                        "type": "string",
                        "flag": "--type",
                        "description": "Limit to specific document type",
                    },
                ],
            },
            "balance": {
                "description": "Show trial balance for the ledger",
                "parameters": [
                    {
                        "name": "demo",
                        "type": "boolean",
                        "flag": "--demo",
                        "description": "Use demo data",
                    },
                ],
            },
            "report": {
                "description": "Generate financial reports",
                "parameters": [
                    {
                        "name": "report_type",
                        "type": "choice",
                        "choices": ["income-statement", "balance-sheet", "tax-summary"],
                        "positional": True,
                        "required": True,
                        "description": "Type of report to generate",
                    },
                    {
                        "name": "year",
                        "type": "integer",
                        "flag": "--year",
                        "description": "Fiscal year",
                    },
                    {
                        "name": "demo",
                        "type": "boolean",
                        "flag": "--demo",
                        "description": "Use demo data",
                    },
                ],
            },
            "documents.list": {
                "description": "List all ingested documents",
                "parameters": [
                    {
                        "name": "limit",
                        "type": "integer",
                        "flag": "--limit",
                        "default": 50,
                        "description": "Maximum documents to list",
                    },
                    {
                        "name": "doc_type",
                        "type": "string",
                        "flag": "--type",
                        "description": "Filter by document type",
                    },
                ],
            },
            "documents.show": {
                "description": "Show details of a specific document",
                "parameters": [
                    {
                        "name": "doc_id",
                        "type": "integer",
                        "positional": True,
                        "required": True,
                        "description": "Document ID",
                    },
                ],
            },
            "ledgers.list": {
                "description": "List all ledgers",
                "parameters": [],
            },
            "ledgers.create": {
                "description": "Create a new ledger",
                "parameters": [
                    {
                        "name": "name",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Ledger name",
                    },
                    {
                        "name": "chart",
                        "type": "choice",
                        "choices": ["SKR03", "SKR04"],
                        "flag": "--chart",
                        "default": "SKR03",
                        "description": "Chart of accounts",
                    },
                ],
            },
            "elster.status": {
                "description": "Check ELSTER integration status",
                "parameters": [],
            },
            "elster.vat": {
                "description": "Prepare VAT advance return (Umsatzsteuer-Voranmeldung)",
                "parameters": [
                    {
                        "name": "period",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Period (e.g., 2024-Q1, 2024-01)",
                    },
                    {
                        "name": "preview",
                        "type": "boolean",
                        "flag": "--preview",
                        "description": "Preview without generating XML",
                    },
                    {
                        "name": "demo",
                        "type": "boolean",
                        "flag": "--demo",
                        "description": "Use demo data",
                    },
                ],
            },
            "sync.status": {
                "description": "Show Google Drive sync status",
                "parameters": [],
            },
            "sync.run": {
                "description": "Sync documents from Google Drive TAXLORD folders",
                "parameters": [
                    {
                        "name": "sync_type",
                        "type": "choice",
                        "choices": ["private", "business"],
                        "flag": "--type",
                        "description": "Sync type (private or business folder)",
                    },
                    {
                        "name": "dry_run",
                        "type": "boolean",
                        "flag": "--dry-run",
                        "description": "Show what would be synced without syncing",
                    },
                ],
            },
        }

    def parse_output(self, command: str, stdout: str, stderr: str) -> Any | None:
        """Parse taxlord output into structured data."""
        if command == "search":
            return self._parse_search_results(stdout)
        elif command == "ask":
            return self._parse_ask_response(stdout)
        elif command in ("documents.list", "ledgers.list"):
            return self._parse_list(stdout)
        elif command == "balance":
            return self._parse_balance(stdout)
        elif command == "ingest":
            return self._parse_ingest(stdout)
        elif command.startswith("elster."):
            return self._parse_elster(stdout)
        elif command.startswith("sync."):
            return self._parse_sync(stdout)

        return {"raw_output": strip_ansi(stdout)}

    def _parse_search_results(self, output: str) -> dict:
        """Parse search results."""
        table = self._parser.parse_table(output)

        if table and table.rows:
            results = []
            for row in table.rows:
                results.append(
                    {
                        "id": row.get("ID", ""),
                        "title": row.get("Title", row.get("Name", "")),
                        "type": row.get("Type", ""),
                        "score": row.get("Score", ""),
                        "date": row.get("Date", ""),
                    }
                )
            return {"results": results, "count": len(results)}

        summary = self._parser.extract_summary(output)
        return {"results": [], "count": summary.get("results", 0)}

    def _parse_ask_response(self, output: str) -> dict:
        """Parse AI question response."""
        clean = strip_ansi(output)

        # Extract the answer (usually after "Answer:" or similar)
        answer_match = re.search(r"(?:Answer|Response)[:\s]+(.+)", clean, re.DOTALL | re.IGNORECASE)
        if answer_match:
            return {"answer": answer_match.group(1).strip()}

        # Fallback: return everything that's not a header
        lines = [line for line in clean.split("\n") if line.strip() and not line.strip().endswith(":")]
        return {"answer": "\n".join(lines)}

    def _parse_list(self, output: str) -> dict:
        """Parse list output."""
        table = self._parser.parse_table(output)

        if table and table.rows:
            return {"items": table.rows, "count": len(table.rows)}

        return {"items": [], "count": 0}

    def _parse_balance(self, output: str) -> dict:
        """Parse trial balance."""
        table = self._parser.parse_table(output)

        if table and table.rows:
            accounts = []
            for row in table.rows:
                accounts.append(
                    {
                        "number": row.get("Account", row.get("Konto", "")),
                        "name": row.get("Name", row.get("Bezeichnung", "")),
                        "debit": row.get("Debit", row.get("Soll", "")),
                        "credit": row.get("Credit", row.get("Haben", "")),
                    }
                )
            return {"accounts": accounts}

        return {"accounts": [], "raw_output": strip_ansi(output)}

    def _parse_ingest(self, output: str) -> dict:
        """Parse ingest result."""
        clean = strip_ansi(output)
        summary = self._parser.extract_summary(output)

        success = self._parser.is_success_message(output)

        return {
            "success": success,
            "documents_processed": summary.get("documents", 1 if success else 0),
            "message": clean.split("\n")[0] if clean else "",
        }

    def _parse_elster(self, output: str) -> dict:
        """Parse ELSTER command output."""
        clean = strip_ansi(output)
        details = self._parser.extract_key_values(output)

        return {
            "status": "connected" if "connected" in clean.lower() or "ready" in clean.lower() else "unknown",
            "details": details,
            "raw_output": clean,
        }

    def _parse_sync(self, output: str) -> dict:
        """Parse sync output."""
        summary = self._parser.extract_summary(output)
        clean = strip_ansi(output)

        return {
            "synced": summary.get("documents", summary.get("files", 0)),
            "success": self._parser.is_success_message(output),
            "message": clean.split("\n")[-1] if clean else "",
        }
