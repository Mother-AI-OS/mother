"""Built-in datacraft plugin for Mother AI OS.

Provides document processing capabilities: parse, store, search, extract tables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...base import PluginBase, PluginResult
from ...manifest import (
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
)
from .parsers import (
    SUPPORTED_EXTENSIONS,
    chunk_text,
    detect_document_type,
    is_supported,
    parse_document,
)
from .storage import Document, DocumentStore


def _create_manifest() -> PluginManifest:
    """Create the datacraft plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="datacraft",
            version="1.0.0",
            description="Document processing for Mother AI OS: parse, store, search, extract tables",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Process documents
            CapabilitySpec(
                name="process",
                description="Process a document: parse content, chunk text, extract entities, and store for search.",
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path to document or directory",
                        required=True,
                    ),
                    ParameterSpec(
                        name="doc_type",
                        type=ParameterType.STRING,
                        description="Document type override (invoice, receipt, bank_statement, contract, letter, report)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="recursive",
                        type=ParameterType.BOOLEAN,
                        description="Process directories recursively",
                        required=False,
                        default=False,
                    ),
                    ParameterSpec(
                        name="no_store",
                        type=ParameterType.BOOLEAN,
                        description="Don't store in database, just return parsed results",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Search documents
            CapabilitySpec(
                name="search",
                description="Search processed documents using full-text search.",
                parameters=[
                    ParameterSpec(
                        name="query",
                        type=ParameterType.STRING,
                        description="Search query",
                        required=True,
                    ),
                    ParameterSpec(
                        name="doc_type",
                        type=ParameterType.STRING,
                        description="Filter by document type",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum number of results (default: 10)",
                        required=False,
                        default=10,
                    ),
                ],
            ),
            # Extract tables
            CapabilitySpec(
                name="tables",
                description="Extract tables from a document.",
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path to document",
                        required=True,
                    ),
                    ParameterSpec(
                        name="format",
                        type=ParameterType.STRING,
                        description="Output format: json, csv, or markdown (default: json)",
                        required=False,
                        default="json",
                    ),
                ],
            ),
            # Get document
            CapabilitySpec(
                name="get",
                description="Get a processed document by ID.",
                parameters=[
                    ParameterSpec(
                        name="doc_id",
                        type=ParameterType.STRING,
                        description="Document ID",
                        required=True,
                    ),
                ],
            ),
            # List documents
            CapabilitySpec(
                name="list",
                description="List all processed documents.",
                parameters=[
                    ParameterSpec(
                        name="doc_type",
                        type=ParameterType.STRING,
                        description="Filter by document type",
                        required=False,
                    ),
                ],
            ),
            # Get stats
            CapabilitySpec(
                name="stats",
                description="Get storage statistics.",
                parameters=[],
            ),
            # Get graph
            CapabilitySpec(
                name="graph",
                description="Get knowledge graph (entities and relationships) for a document.",
                parameters=[
                    ParameterSpec(
                        name="doc_id",
                        type=ParameterType.STRING,
                        description="Document ID",
                        required=True,
                    ),
                ],
            ),
            # Delete document
            CapabilitySpec(
                name="delete",
                description="Delete a document from storage.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="doc_id",
                        type=ParameterType.STRING,
                        description="Document ID to delete",
                        required=True,
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.datacraft",
                **{"class": "DatacraftPlugin"},
            ),
        ),
        permissions=[
            "filesystem:read",
            "filesystem:write",
        ],
    )


class DatacraftPlugin(PluginBase):
    """Built-in plugin for document processing."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the datacraft plugin."""
        super().__init__(_create_manifest(), config)

        # Initialize document store
        db_path = None
        if config and "db_path" in config:
            db_path = Path(config["db_path"])
        self._store = DocumentStore(db_path)

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve and expand a path string."""
        path = Path(path_str).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a datacraft capability."""
        handlers = {
            "process": self._process,
            "search": self._search,
            "tables": self._tables,
            "get": self._get,
            "list": self._list,
            "stats": self._stats,
            "graph": self._graph,
            "delete": self._delete,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        try:
            return await handler(**params)
        except FileNotFoundError as e:
            return PluginResult.error_result(
                f"File not found: {e}",
                code="FILE_NOT_FOUND",
            )
        except PermissionError as e:
            return PluginResult.error_result(
                f"Permission denied: {e}",
                code="PERMISSION_DENIED",
            )
        except ValueError as e:
            return PluginResult.error_result(
                str(e),
                code="INVALID_INPUT",
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Document processing failed: {e}",
                code="PROCESSING_ERROR",
            )

    async def _process(
        self,
        path: str,
        doc_type: str | None = None,
        recursive: bool = False,
        no_store: bool = False,
    ) -> PluginResult:
        """Process document(s) and optionally store them."""
        input_path = self._resolve_path(path)

        if not input_path.exists():
            return PluginResult.error_result(
                f"Path not found: {input_path}",
                code="FILE_NOT_FOUND",
            )

        results = []

        if input_path.is_file():
            # Process single file
            result = await self._process_file(input_path, doc_type, no_store)
            results.append(result)
        else:
            # Process directory
            pattern = "**/*" if recursive else "*"
            files = [
                f
                for f in input_path.glob(pattern)
                if f.is_file() and is_supported(f)
            ]

            if not files:
                return PluginResult.error_result(
                    f"No supported documents found in {input_path}",
                    code="NO_DOCUMENTS",
                )

            for file_path in files:
                result = await self._process_file(file_path, doc_type, no_store)
                results.append(result)

        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]

        return PluginResult.success_result(
            data={
                "processed": len(successful),
                "failed": len(failed),
                "documents": results,
            },
            message=f"Processed {len(successful)} document(s), {len(failed)} failed",
        )

    async def _process_file(
        self,
        file_path: Path,
        doc_type: str | None,
        no_store: bool,
    ) -> dict[str, Any]:
        """Process a single file."""
        try:
            if not is_supported(file_path):
                return {
                    "success": False,
                    "filename": file_path.name,
                    "error": f"Unsupported file type: {file_path.suffix}",
                }

            # Parse document
            parsed = parse_document(file_path)

            # Detect type if not specified
            if doc_type:
                detected_type = doc_type
            else:
                detected_type = detect_document_type(file_path.name, parsed.content)

            # Create chunks
            chunks = chunk_text(parsed.content)

            # Generate document ID
            doc_id = self._store.generate_doc_id(parsed.content, file_path.name)

            # Create document object
            doc = Document(
                doc_id=doc_id,
                filename=file_path.name,
                doc_type=detected_type,
                content=parsed.content,
                chunks=chunks,
                metadata=parsed.metadata,
                entities=parsed.entities,
                file_hash=parsed.file_hash,
                pages=parsed.pages,
            )

            # Store if requested
            if not no_store:
                self._store.store_document(doc)

            return {
                "success": True,
                "doc_id": doc_id,
                "filename": file_path.name,
                "doc_type": detected_type,
                "pages": parsed.pages,
                "chunks": len(chunks),
                "entities": len(parsed.entities),
                "tables": len(parsed.tables),
            }

        except Exception as e:
            return {
                "success": False,
                "filename": file_path.name,
                "error": str(e),
            }

    async def _search(
        self,
        query: str,
        doc_type: str | None = None,
        limit: int = 10,
    ) -> PluginResult:
        """Search documents."""
        results = self._store.search(query, doc_type, limit)

        return PluginResult.success_result(
            data={
                "query": query,
                "count": len(results),
                "results": [r.to_dict() for r in results],
            },
            message=f"Found {len(results)} result(s) for '{query}'",
        )

    async def _tables(
        self,
        path: str,
        format: str = "json",
    ) -> PluginResult:
        """Extract tables from a document."""
        input_path = self._resolve_path(path)

        if not input_path.exists():
            return PluginResult.error_result(
                f"File not found: {input_path}",
                code="FILE_NOT_FOUND",
            )

        parsed = parse_document(input_path)

        if not parsed.tables:
            return PluginResult.success_result(
                data={"tables": [], "count": 0},
                message="No tables found in document",
            )

        # Format output
        if format == "csv":
            formatted_tables = []
            for table in parsed.tables:
                csv_rows = [",".join(f'"{c}"' for c in row) for row in table]
                formatted_tables.append("\n".join(csv_rows))
            output = formatted_tables
        elif format == "markdown":
            formatted_tables = []
            for table in parsed.tables:
                if not table:
                    continue
                # Header
                md = "| " + " | ".join(table[0]) + " |\n"
                md += "| " + " | ".join(["---"] * len(table[0])) + " |\n"
                # Rows
                for row in table[1:]:
                    md += "| " + " | ".join(row) + " |\n"
                formatted_tables.append(md)
            output = formatted_tables
        else:
            output = parsed.tables

        return PluginResult.success_result(
            data={
                "tables": output,
                "count": len(parsed.tables),
                "format": format,
            },
            message=f"Found {len(parsed.tables)} table(s)",
        )

    async def _get(self, doc_id: str) -> PluginResult:
        """Get a document by ID."""
        doc = self._store.get_document(doc_id)

        if not doc:
            return PluginResult.error_result(
                f"Document not found: {doc_id}",
                code="NOT_FOUND",
            )

        return PluginResult.success_result(
            data=doc.to_dict(),
            message=f"Retrieved document: {doc.filename}",
        )

    async def _list(self, doc_type: str | None = None) -> PluginResult:
        """List all documents."""
        docs = self._store.list_documents(doc_type)

        return PluginResult.success_result(
            data={
                "count": len(docs),
                "documents": docs,
            },
            message=f"Found {len(docs)} document(s)",
        )

    async def _stats(self) -> PluginResult:
        """Get storage statistics."""
        stats = self._store.get_stats()

        # Format size
        size_bytes = stats.get("db_size_bytes", 0)
        if size_bytes < 1024:
            size_human = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_human = f"{size_bytes / 1024:.1f} KB"
        else:
            size_human = f"{size_bytes / (1024 * 1024):.1f} MB"

        stats["db_size_human"] = size_human

        return PluginResult.success_result(
            data=stats,
            message=(
                f"Storage: {stats['total_documents']} docs, "
                f"{stats['total_chunks']} chunks, "
                f"{stats['total_entities']} entities"
            ),
        )

    async def _graph(self, doc_id: str) -> PluginResult:
        """Get knowledge graph for a document."""
        doc = self._store.get_document(doc_id)

        if not doc:
            return PluginResult.error_result(
                f"Document not found: {doc_id}",
                code="NOT_FOUND",
            )

        graph = self._store.get_graph(doc_id)

        return PluginResult.success_result(
            data=graph,
            message=f"Graph for {doc.filename}: {len(graph['entities'])} entities, {len(graph['relationships'])} relationships",
        )

    async def _delete(self, doc_id: str) -> PluginResult:
        """Delete a document."""
        doc = self._store.get_document(doc_id)

        if not doc:
            return PluginResult.error_result(
                f"Document not found: {doc_id}",
                code="NOT_FOUND",
            )

        deleted = self._store.delete_document(doc_id)

        if deleted:
            return PluginResult.success_result(
                data={"doc_id": doc_id, "filename": doc.filename},
                message=f"Deleted document: {doc.filename}",
            )
        else:
            return PluginResult.error_result(
                f"Failed to delete document: {doc_id}",
                code="DELETE_FAILED",
            )


__all__ = ["DatacraftPlugin"]
