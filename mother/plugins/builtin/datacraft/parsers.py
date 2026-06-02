"""Document parsers for the Mother datacraft plugin.

This module is now a thin **adapter** over the unified DataCraft engine
(``datacraft.parsing``). All real file processing — PDF (OpenDataLoader →
Docling fallback), Office formats, images, and plain text — is delegated to
that single shared engine so Mother exposes exactly the same pipeline every
*Craft tool uses, rather than its own divergent pypdf/python-docx logic.

The public surface (``parse_document``, ``chunk_text``, ``detect_document_type``,
``is_supported`` and the ``ParsedDocument`` shape) is preserved so the plugin's
``__init__.py`` and ``storage.py`` need no changes.

Requires the ``datacraft`` package to be importable in Mother's environment
(``pip install -e ~/projects/datacraft``). There is intentionally no local
parsing fallback: a single engine is the whole point of the consolidation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedDocument:
    """Result of parsing a document (Mother plugin contract).

    ``tables`` is a list of tables, each a list of rows, each a list of string
    cells (header row first) — the shape the plugin's storage layer expects.
    """

    content: str
    pages: int
    tables: list[list[list[str]]]
    metadata: dict[str, Any]
    entities: list[dict[str, str]]
    file_hash: str


def _engine():
    """Import the unified DataCraft engine, with a clear error if missing."""
    try:
        from datacraft.parsing import get_registry, parse_document  # noqa: F401

        return get_registry, parse_document
    except ImportError as e:  # pragma: no cover - environment guard
        raise ImportError(
            "The unified DataCraft engine is required for document parsing in "
            "Mother. Install it with: pip install -e ~/projects/datacraft"
        ) from e


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file (delegates to the engine helper)."""
    from datacraft.parsing.common import compute_file_hash as _hash

    return _hash(file_path)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Chunk text using the engine's structure-aware chunker."""
    from datacraft.api.library import Datacraft

    return Datacraft.chunk_text(text, chunk_size=chunk_size, chunk_overlap=overlap)


def detect_document_type(filename: str, content: str) -> str:
    """Detect document type via the shared engine heuristics.

    Note the argument order (``filename, content``) is kept for the plugin's
    existing callers; the engine helper takes ``(text, file_path)``.
    """
    from datacraft.parsing.common import detect_document_type as _detect

    doc_type = _detect(content or "", filename or "")
    value = doc_type.value
    # The plugin's vocabulary uses "other" for the unknown bucket.
    return "other" if value == "unknown" else value


def is_supported(file_path: Path) -> bool:
    """Whether the unified engine can parse this file."""
    get_registry, _ = _engine()
    return get_registry().supports(file_path)


def _tables_to_grid(tables: list[Any]) -> list[list[list[str]]]:
    """Convert datacraft ExtractedTable objects to header-first string grids."""
    grids: list[list[list[str]]] = []
    for table in tables:
        grid: list[list[str]] = []
        if getattr(table, "headers", None):
            grid.append([str(h) for h in table.headers])
        for row in getattr(table, "rows", []) or []:
            grid.append([str(c) for c in row])
        if grid:
            grids.append(grid)
    return grids


def _extract_entities(doc: Any) -> list[dict[str, str]]:
    """Run the engine's type-aware entity extractor; degrade gracefully."""
    try:
        from datacraft.processing.extractors import get_extractor

        extractor = get_extractor(doc.doc_type)
        extracted = extractor.extract(doc)
        entities = extractor.extract_entities(doc, extracted)
        return [
            {"type": str(e.entity_type).upper(), "value": str(e.value)}
            for e in entities
        ]
    except Exception:
        # Entity enrichment is best-effort; parsing already succeeded.
        return []


def parse_document(file_path: Path) -> ParsedDocument:
    """Parse a document via the unified DataCraft engine.

    Args:
        file_path: Path to the document.

    Returns:
        ParsedDocument in the Mother plugin's contract shape.

    Raises:
        ValueError: if the engine supports no backend for this file type.
    """
    _, engine_parse = _engine()
    file_path = Path(file_path)

    doc = engine_parse(file_path)  # datacraft.core.models.ParsedDocument

    metadata = dict(doc.metadata or {})
    metadata.setdefault("parser_backend", metadata.get("parser_backend", "datacraft"))

    return ParsedDocument(
        content=doc.text,
        pages=doc.page_count,
        tables=_tables_to_grid(doc.tables),
        metadata=metadata,
        entities=_extract_entities(doc),
        file_hash=doc.file_hash,
    )


# Supported extensions are whatever the unified engine's registry advertises.
def _supported_extensions() -> set[str]:
    get_registry, _ = _engine()
    return get_registry().supported_extensions


# Backwards-compatible module constant (computed lazily on first access via
# is_supported); kept for any external importers that referenced it.
SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".xlsx",
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp",
    ".txt", ".md", ".markdown", ".text", ".csv", ".tsv",
    ".html", ".htm", ".json", ".xml", ".yaml", ".yml",
}
