"""LeadEngine CLI tool wrapper."""

import re
from typing import Any

from ..parsers.output import OutputParser, strip_ansi
from .base import ToolWrapper


class LeadsTool(ToolWrapper):
    """Wrapper for leads CLI - lead generation and analysis."""

    def __init__(self, binary: str, timeout: int = 300):
        super().__init__(
            binary=str(binary),
            timeout=timeout,
        )
        self._parser = OutputParser()

    @property
    def name(self) -> str:
        return "leads"

    @property
    def description(self) -> str:
        return "Lead generation tool - discover tenders, Upwork jobs, and analyze opportunities"

    def get_commands(self) -> dict[str, dict]:
        return {
            "fetch": {
                "description": "Fetch fresh leads from configured sources (German tenders, Upwork)",
                "parameters": [
                    {
                        "name": "source",
                        "type": "choice",
                        "choices": ["all", "tenders", "upwork"],
                        "flag": "--source",
                        "default": "all",
                        "description": "Source to fetch from",
                    },
                    {
                        "name": "days",
                        "type": "integer",
                        "flag": "--days",
                        "default": 1,
                        "description": "Fetch leads from last N days",
                    },
                    {
                        "name": "filter",
                        "type": "string",
                        "flag": "--filter",
                        "description": "Filter leads by keyword",
                    },
                    {
                        "name": "quiet",
                        "type": "boolean",
                        "flag": "--quiet",
                        "description": "Minimal output",
                    },
                ],
            },
            "list": {
                "description": "List cached leads with optional filters",
                "parameters": [
                    {
                        "name": "top",
                        "type": "integer",
                        "flag": "--top",
                        "default": 20,
                        "description": "Number of leads to show",
                    },
                    {
                        "name": "filter",
                        "type": "string",
                        "flag": "--filter",
                        "description": "Filter by keyword (ai, ki, ml, or custom)",
                    },
                    {
                        "name": "min_score",
                        "type": "integer",
                        "flag": "--min-score",
                        "description": "Minimum score threshold",
                    },
                    {
                        "name": "source",
                        "type": "choice",
                        "choices": ["all", "tenders", "upwork"],
                        "flag": "--source",
                        "default": "all",
                        "description": "Filter by source",
                    },
                ],
            },
            "show": {
                "description": "Show detailed information about a specific tender",
                "parameters": [
                    {
                        "name": "identifier",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Tender ID or URL",
                    },
                ],
            },
            "analyze": {
                "description": "Analyze tender documents with AI (downloads and reviews PDFs)",
                "parameters": [
                    {
                        "name": "identifier",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Tender ID to analyze",
                    },
                    {
                        "name": "download_only",
                        "type": "boolean",
                        "flag": "--download-only",
                        "description": "Only download documents, skip analysis",
                    },
                ],
            },
            "status": {
                "description": "Show system status (cache, API configuration, cron jobs)",
                "parameters": [],
            },
        }

    def parse_output(self, command: str, stdout: str, stderr: str) -> Any | None:
        """Parse leads output into structured data."""
        if command == "list":
            return self._parse_leads_list(stdout)
        elif command == "show":
            return self._parse_lead_details(stdout)
        elif command == "fetch":
            return self._parse_fetch_summary(stdout)
        elif command == "analyze":
            return self._parse_analysis(stdout)
        elif command == "status":
            return self._parse_status(stdout)

        return {"raw_output": strip_ansi(stdout)}

    def _parse_leads_list(self, output: str) -> dict:
        """Parse leads list output."""
        table = self._parser.parse_table(output)

        if table and table.rows:
            leads = []
            for row in table.rows:
                lead = {
                    "id": row.get("ID", row.get("Nr", "")),
                    "title": row.get("Title", row.get("Titel", "")),
                    "score": row.get("Score", ""),
                    "deadline": row.get("Deadline", row.get("Frist", "")),
                    "source": row.get("Source", row.get("Quelle", "")),
                }
                # Try to extract score as int
                try:
                    lead["score"] = int(str(lead["score"]).replace("%", ""))
                except (ValueError, TypeError):
                    pass
                leads.append(lead)

            return {"leads": leads, "count": len(leads)}

        # Fallback: extract summary
        summary = self._parser.extract_summary(output)
        return {"leads": [], "count": summary.get("leads", 0), "raw_output": strip_ansi(output)}

    def _parse_lead_details(self, output: str) -> dict:
        """Parse single lead details."""
        clean = strip_ansi(output)
        details = self._parser.extract_key_values(output)

        # Extract common fields
        result = {
            "title": details.get("Title", details.get("Titel", "")),
            "organization": details.get("Organization", details.get("Auftraggeber", "")),
            "deadline": details.get("Deadline", details.get("Frist", "")),
            "value": details.get("Value", details.get("Wert", "")),
            "location": details.get("Location", details.get("Ort", "")),
            "description": "",
            "documents": [],
        }

        # Try to extract description
        desc_match = re.search(r"Description[:\s]+(.+?)(?=\n\n|\Z)", clean, re.DOTALL | re.IGNORECASE)
        if desc_match:
            result["description"] = desc_match.group(1).strip()

        # Extract document list
        doc_pattern = r"(?:Documents?|Dokumente)[:\s]+(.+?)(?=\n\n|\Z)"
        doc_match = re.search(doc_pattern, clean, re.DOTALL | re.IGNORECASE)
        if doc_match:
            docs = doc_match.group(1).strip().split("\n")
            result["documents"] = [d.strip() for d in docs if d.strip()]

        return result

    def _parse_fetch_summary(self, output: str) -> dict:
        """Parse fetch summary."""
        summary = self._parser.extract_summary(output)
        clean = strip_ansi(output)

        result = {
            "fetched": summary.get("leads", summary.get("found", 0)),
            "new": summary.get("new", 0),
            "sources": [],
        }

        # Extract source info
        if "tenders" in clean.lower():
            result["sources"].append("tenders")
        if "upwork" in clean.lower():
            result["sources"].append("upwork")

        return result

    def _parse_analysis(self, output: str) -> dict:
        """Parse analysis output."""
        clean = strip_ansi(output)

        result = {
            "analyzed": True,
            "documents_processed": 0,
            "summary": "",
            "recommendations": [],
        }

        # Count documents
        doc_count = len(re.findall(r"(?:Downloaded|Analyzed|Processing)\s+\S+\.pdf", clean, re.IGNORECASE))
        result["documents_processed"] = doc_count

        # Extract AI summary if present
        summary_match = re.search(
            r"(?:Summary|Analysis)[:\s]+(.+?)(?=\n\n|Recommendations?|\Z)",
            clean,
            re.DOTALL | re.IGNORECASE,
        )
        if summary_match:
            result["summary"] = summary_match.group(1).strip()

        # Extract recommendations
        rec_match = re.search(r"Recommendations?[:\s]+(.+?)(?=\n\n|\Z)", clean, re.DOTALL | re.IGNORECASE)
        if rec_match:
            recs = rec_match.group(1).strip().split("\n")
            result["recommendations"] = [r.strip().lstrip("•-") for r in recs if r.strip()]

        return result

    def _parse_status(self, output: str) -> dict:
        """Parse status output."""
        details = self._parser.extract_key_values(output)
        summary = self._parser.extract_summary(output)

        return {
            "cache_leads": summary.get("leads", 0),
            "last_fetch": details.get("Last fetch", details.get("Last Fetch", "")),
            "upwork_configured": "upwork" in strip_ansi(output).lower(),
            "tenders_configured": "tenders" in strip_ansi(output).lower()
            or "it-ausschreibung" in strip_ansi(output).lower(),
        }
