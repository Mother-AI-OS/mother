"""Datacraft CLI tool wrapper for Mother."""

import re
from pathlib import Path
from typing import Any, Optional

from .base import ToolWrapper


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_pattern = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_pattern.sub("", text)


class DatacraftTool(ToolWrapper):
    """Wrapper for datacraft CLI - document and table processing.

    Datacraft provides:
    - Document parsing (PDF, images, DOCX)
    - Table extraction
    - Semantic search
    - Knowledge graph queries
    """

    def __init__(
        self,
        datacraft_path: str | None = None,
        timeout: int = 300,
    ):
        """Initialize datacraft wrapper.

        Args:
            datacraft_path: Path to datacraft project (for dev mode)
            timeout: Command timeout in seconds
        """
        # Try to find datacraft binary
        home = Path.home()

        if datacraft_path:
            # Development mode - run from source
            binary = "python"
            extra_args = ["-m", "datacraft"]
            cwd = datacraft_path
        else:
            # Check if installed globally
            global_bin = home / ".local" / "bin" / "datacraft"
            if global_bin.exists():
                binary = str(global_bin)
                extra_args = []
                cwd = None
            else:
                # Fallback to development path
                dev_path = home / "projects" / "datacraft"
                if dev_path.exists():
                    binary = str(dev_path / ".venv" / "bin" / "datacraft")
                    extra_args = []
                    cwd = None
                else:
                    binary = "datacraft"
                    extra_args = []
                    cwd = None

        super().__init__(
            binary=binary,
            extra_args=extra_args,
            cwd=cwd,
            timeout=timeout,
        )

    @property
    def name(self) -> str:
        return "datacraft"

    @property
    def description(self) -> str:
        return (
            "Document and table processing toolkit. "
            "Parse PDFs/images, extract tables, semantic search, knowledge graph."
        )

    def get_commands(self) -> dict[str, dict]:
        return {
            "process": {
                "description": "Process documents (parse, chunk, embed, store)",
                "parameters": [
                    {
                        "name": "path",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Path to document or directory",
                    },
                    {
                        "name": "doc_type",
                        "type": "choice",
                        "choices": [
                            "invoice",
                            "receipt",
                            "bank_statement",
                            "contract",
                            "letter",
                            "report",
                        ],
                        "flag": "--type",
                        "description": "Document type override",
                    },
                    {
                        "name": "mode",
                        "type": "choice",
                        "choices": ["project", "central", "gdrive"],
                        "flag": "--mode",
                        "default": "central",
                        "description": "Storage mode (central stores in shared KB)",
                    },
                    {
                        "name": "recursive",
                        "type": "boolean",
                        "flag": "--recursive",
                        "description": "Process directories recursively",
                    },
                    {
                        "name": "no_store",
                        "type": "boolean",
                        "flag": "--no-store",
                        "description": "Don't store, just return results",
                    },
                ],
            },
            "search": {
                "description": "Search documents using semantic search",
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
                        "type": "choice",
                        "choices": [
                            "invoice",
                            "receipt",
                            "bank_statement",
                            "contract",
                            "letter",
                            "report",
                        ],
                        "flag": "--type",
                        "description": "Filter by document type",
                    },
                ],
            },
            "tables": {
                "description": "Extract tables from a document",
                "parameters": [
                    {
                        "name": "path",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Path to document",
                    },
                    {
                        "name": "format",
                        "type": "choice",
                        "choices": ["table", "csv", "json"],
                        "flag": "--format",
                        "default": "table",
                        "description": "Output format",
                    },
                ],
            },
            "stats": {
                "description": "Show storage statistics",
                "parameters": [],
            },
            "graph": {
                "description": "Show knowledge graph for a document",
                "parameters": [
                    {
                        "name": "doc_id",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Document ID",
                    },
                ],
            },
            "list-docs": {
                "description": "List all processed documents",
                "parameters": [],
            },
            "delete": {
                "description": "Delete a document from storage",
                "confirmation_required": True,
                "parameters": [
                    {
                        "name": "doc_id",
                        "type": "string",
                        "positional": True,
                        "required": True,
                        "description": "Document ID to delete",
                    },
                    {
                        "name": "yes",
                        "type": "boolean",
                        "flag": "--yes",
                        "default": True,
                        "description": "Skip confirmation",
                    },
                ],
            },
        }

    def parse_output(
        self, command: str, stdout: str, stderr: str
    ) -> Optional[Any]:
        """Parse datacraft output into structured data."""
        clean = strip_ansi(stdout)

        if command == "process":
            return self._parse_process(clean)
        elif command == "search":
            return self._parse_search(clean)
        elif command == "tables":
            return self._parse_tables(clean)
        elif command == "stats":
            return self._parse_stats(clean)
        elif command == "graph":
            return self._parse_graph(clean)
        elif command == "list-docs":
            return self._parse_list_docs(clean)
        elif command == "delete":
            return self._parse_delete(clean)

        return {"raw_output": clean}

    def _parse_process(self, output: str) -> dict:
        """Parse process command output."""
        success = "processed" in output.lower() or "document processed" in output.lower()
        count_match = re.search(r"Processed (\d+)", output)

        result = {
            "success": success,
            "documents_processed": int(count_match.group(1)) if count_match else (1 if success else 0),
        }

        # Try to extract document details
        id_match = re.search(r"ID\s+([a-f0-9-]+)", output)
        if id_match:
            result["doc_id"] = id_match.group(1)

        type_match = re.search(r"Type\s+(\w+)", output)
        if type_match:
            result["doc_type"] = type_match.group(1)

        pages_match = re.search(r"Pages\s+(\d+)", output)
        if pages_match:
            result["pages"] = int(pages_match.group(1))

        chunks_match = re.search(r"Chunks\s+(\d+)", output)
        if chunks_match:
            result["chunks"] = int(chunks_match.group(1))

        entities_match = re.search(r"Entities\s+(\d+)", output)
        if entities_match:
            result["entities"] = int(entities_match.group(1))

        return result

    def _parse_search(self, output: str) -> dict:
        """Parse search results."""
        results = []

        # Parse result count
        count_match = re.search(r"Found (\d+) result", output)
        count = int(count_match.group(1)) if count_match else 0

        # Parse individual results
        # Pattern: #N XX% | type | filename followed by content
        pattern = r"#(\d+)\s+(\d+)%\s*\|\s*(\w+)\s*\|\s*([^\n]+)\n(.*?)(?=(?:#\d+|$))"
        for match in re.finditer(pattern, output, re.DOTALL):
            results.append({
                "rank": int(match.group(1)),
                "score": int(match.group(2)) / 100,
                "doc_type": match.group(3).strip(),
                "filename": match.group(4).strip(),
                "content_preview": match.group(5).strip()[:300],
            })

        return {
            "count": count,
            "results": results,
        }

    def _parse_tables(self, output: str) -> dict:
        """Parse tables extraction output."""
        tables_match = re.search(r"Found (\d+) table", output)
        count = int(tables_match.group(1)) if tables_match else 0

        return {
            "table_count": count,
            "raw_output": output,
        }

    def _parse_stats(self, output: str) -> dict:
        """Parse stats output."""
        stats = {}

        # Vector store stats
        doc_match = re.search(r"Documents\s+(\d+)", output)
        if doc_match:
            stats["total_documents"] = int(doc_match.group(1))

        chunks_match = re.search(r"Chunks\s+(\d+)", output)
        if chunks_match:
            stats["total_chunks"] = int(chunks_match.group(1))

        # Graph store stats
        entities_match = re.search(r"Entities\s+(\d+)", output)
        if entities_match:
            stats["total_entities"] = int(entities_match.group(1))

        relationships_match = re.search(r"Relationships\s+(\d+)", output)
        if relationships_match:
            stats["total_relationships"] = int(relationships_match.group(1))

        return stats

    def _parse_graph(self, output: str) -> dict:
        """Parse graph output."""
        entities = []
        relationships = []

        # Parse entities section
        entity_pattern = r"(\w{8,12})\s+(\w+)\s+(.+)"
        in_entities = False
        in_relationships = False

        for line in output.split("\n"):
            if "Entities" in line:
                in_entities = True
                in_relationships = False
                continue
            if "Relationships" in line:
                in_entities = False
                in_relationships = True
                continue

            if in_entities:
                match = re.match(entity_pattern, line.strip())
                if match:
                    entities.append({
                        "id": match.group(1),
                        "type": match.group(2),
                        "value": match.group(3).strip(),
                    })
            elif in_relationships:
                parts = line.strip().split()
                if len(parts) >= 3:
                    relationships.append({
                        "from_id": parts[0],
                        "relationship": parts[1],
                        "to_id": parts[2],
                    })

        return {
            "entities": entities,
            "relationships": relationships,
        }

    def _parse_list_docs(self, output: str) -> dict:
        """Parse list-docs output."""
        docs = []

        # Parse table rows
        for line in output.split("\n"):
            if not line.strip() or "Doc ID" in line or "---" in line:
                continue

            parts = line.split()
            if len(parts) >= 4:
                docs.append({
                    "doc_id": parts[0],
                    "doc_type": parts[1] if len(parts) > 1 else "unknown",
                    "chunks": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
                    "filename": parts[3] if len(parts) > 3 else "",
                })

        return {
            "count": len(docs),
            "documents": docs,
        }

    def _parse_delete(self, output: str) -> dict:
        """Parse delete output."""
        success = "deleted" in output.lower()
        return {
            "success": success,
            "message": output.strip(),
        }
