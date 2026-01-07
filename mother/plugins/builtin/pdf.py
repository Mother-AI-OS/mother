"""Built-in PDF plugin for Mother AI OS.

Provides PDF manipulation capabilities: merge, split, extract pages, get info.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

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
    """Create the PDF plugin manifest programmatically."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="pdf",
            version="1.0.0",
            description="PDF manipulation for Mother AI OS: merge, split, extract, info",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Merge PDFs
            CapabilitySpec(
                name="merge",
                description="Merge multiple PDF files into a single PDF. Files are combined in the order provided.",
                parameters=[
                    ParameterSpec(
                        name="files",
                        type=ParameterType.ARRAY,
                        description="List of PDF file paths to merge (in order)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="output",
                        type=ParameterType.STRING,
                        description="Output file path for the merged PDF",
                        required=True,
                    ),
                ],
            ),
            # Split PDF
            CapabilitySpec(
                name="split",
                description="Split a PDF into individual page files.",
                parameters=[
                    ParameterSpec(
                        name="input",
                        type=ParameterType.STRING,
                        description="Input PDF file path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="output_dir",
                        type=ParameterType.STRING,
                        description="Output directory for split pages (creates if doesn't exist)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="prefix",
                        type=ParameterType.STRING,
                        description="Filename prefix for output files (default: 'page')",
                        required=False,
                        default="page",
                    ),
                ],
            ),
            # Extract pages
            CapabilitySpec(
                name="extract_pages",
                description="Extract specific pages from a PDF into a new PDF.",
                parameters=[
                    ParameterSpec(
                        name="input",
                        type=ParameterType.STRING,
                        description="Input PDF file path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="output",
                        type=ParameterType.STRING,
                        description="Output PDF file path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="pages",
                        type=ParameterType.STRING,
                        description="Page specification: '1,3,5' for specific pages, '1-5' for range, '1-3,7,9-11' for mixed",
                        required=True,
                    ),
                ],
            ),
            # Get PDF info
            CapabilitySpec(
                name="info",
                description="Get information and metadata from a PDF file.",
                parameters=[
                    ParameterSpec(
                        name="input",
                        type=ParameterType.STRING,
                        description="PDF file path",
                        required=True,
                    ),
                ],
            ),
            # Rotate pages
            CapabilitySpec(
                name="rotate",
                description="Rotate pages in a PDF.",
                parameters=[
                    ParameterSpec(
                        name="input",
                        type=ParameterType.STRING,
                        description="Input PDF file path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="output",
                        type=ParameterType.STRING,
                        description="Output PDF file path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="angle",
                        type=ParameterType.INTEGER,
                        description="Rotation angle in degrees (90, 180, or 270)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="pages",
                        type=ParameterType.STRING,
                        description="Pages to rotate (default: all). Format: '1,3,5' or '1-5' or 'all'",
                        required=False,
                        default="all",
                    ),
                ],
            ),
            # Delete pages
            CapabilitySpec(
                name="delete_pages",
                description="Delete specific pages from a PDF.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="input",
                        type=ParameterType.STRING,
                        description="Input PDF file path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="output",
                        type=ParameterType.STRING,
                        description="Output PDF file path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="pages",
                        type=ParameterType.STRING,
                        description="Pages to delete. Format: '1,3,5' or '2-4'",
                        required=True,
                    ),
                ],
            ),
            # Add page numbers
            CapabilitySpec(
                name="count_pages",
                description="Count the number of pages in a PDF file.",
                parameters=[
                    ParameterSpec(
                        name="input",
                        type=ParameterType.STRING,
                        description="PDF file path",
                        required=True,
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.pdf",
                **{"class": "PDFPlugin"},
            ),
        ),
        permissions=[
            "filesystem:read",
            "filesystem:write",
        ],
    )


def parse_page_spec(spec: str, total_pages: int) -> list[int]:
    """Parse a page specification string into a list of page numbers.

    Args:
        spec: Page specification like '1,3,5', '1-5', '1-3,7,9-11', or 'all'
        total_pages: Total number of pages in the PDF

    Returns:
        List of 0-indexed page numbers
    """
    if spec.lower() == "all":
        return list(range(total_pages))

    pages = set()
    parts = spec.replace(" ", "").split(",")

    for part in parts:
        if "-" in part:
            # Range: 1-5
            start, end = part.split("-", 1)
            start_num = int(start)
            end_num = int(end)
            for p in range(start_num, end_num + 1):
                if 1 <= p <= total_pages:
                    pages.add(p - 1)  # Convert to 0-indexed
        else:
            # Single page
            p = int(part)
            if 1 <= p <= total_pages:
                pages.add(p - 1)  # Convert to 0-indexed

    return sorted(pages)


class PDFPlugin(PluginBase):
    """Built-in plugin for PDF manipulation."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the PDF plugin."""
        super().__init__(_create_manifest(), config)

        # Default output directory
        self._default_output_dir = Path.home() / "Downloads"

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve and expand a path string."""
        path = Path(path_str).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a PDF capability."""
        handlers = {
            "merge": self._merge,
            "split": self._split,
            "extract_pages": self._extract_pages,
            "info": self._info,
            "rotate": self._rotate,
            "delete_pages": self._delete_pages,
            "count_pages": self._count_pages,
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
        except Exception as e:
            return PluginResult.error_result(
                f"PDF operation failed: {e}",
                code="PDF_ERROR",
            )

    async def _merge(self, files: list[str], output: str) -> PluginResult:
        """Merge multiple PDFs into one."""
        if not files:
            return PluginResult.error_result(
                "No input files provided",
                code="INVALID_INPUT",
            )

        if len(files) < 2:
            return PluginResult.error_result(
                "At least 2 files required for merge",
                code="INVALID_INPUT",
            )

        # Resolve paths
        input_paths = [self._resolve_path(f) for f in files]
        output_path = self._resolve_path(output)

        # Verify all input files exist
        for path in input_paths:
            if not path.exists():
                return PluginResult.error_result(
                    f"Input file not found: {path}",
                    code="FILE_NOT_FOUND",
                )

        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Merge PDFs
        writer = PdfWriter()
        total_pages = 0

        for path in input_paths:
            reader = PdfReader(str(path))
            for page in reader.pages:
                writer.add_page(page)
                total_pages += 1

        with open(output_path, "wb") as f:
            writer.write(f)

        return PluginResult.success_result(
            data={
                "output": str(output_path),
                "merged_files": len(input_paths),
                "total_pages": total_pages,
            },
            message=f"Merged {len(input_paths)} PDFs ({total_pages} pages) → {output_path}",
        )

    async def _split(
        self,
        input: str,
        output_dir: str,
        prefix: str = "page",
    ) -> PluginResult:
        """Split a PDF into individual pages."""
        input_path = self._resolve_path(input)
        output_dir_path = self._resolve_path(output_dir)

        if not input_path.exists():
            return PluginResult.error_result(
                f"Input file not found: {input_path}",
                code="FILE_NOT_FOUND",
            )

        # Create output directory
        output_dir_path.mkdir(parents=True, exist_ok=True)

        reader = PdfReader(str(input_path))
        output_files = []

        for i, page in enumerate(reader.pages, 1):
            writer = PdfWriter()
            writer.add_page(page)

            output_file = output_dir_path / f"{prefix}_{i:03d}.pdf"
            with open(output_file, "wb") as f:
                writer.write(f)
            output_files.append(str(output_file))

        return PluginResult.success_result(
            data={
                "output_dir": str(output_dir_path),
                "files": output_files,
                "page_count": len(output_files),
            },
            message=f"Split into {len(output_files)} pages → {output_dir_path}",
        )

    async def _extract_pages(
        self,
        input: str,
        output: str,
        pages: str,
    ) -> PluginResult:
        """Extract specific pages from a PDF."""
        input_path = self._resolve_path(input)
        output_path = self._resolve_path(output)

        if not input_path.exists():
            return PluginResult.error_result(
                f"Input file not found: {input_path}",
                code="FILE_NOT_FOUND",
            )

        reader = PdfReader(str(input_path))
        total_pages = len(reader.pages)

        # Parse page specification
        try:
            page_indices = parse_page_spec(pages, total_pages)
        except ValueError as e:
            return PluginResult.error_result(
                f"Invalid page specification: {e}",
                code="INVALID_INPUT",
            )

        if not page_indices:
            return PluginResult.error_result(
                "No valid pages specified",
                code="INVALID_INPUT",
            )

        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Extract pages
        writer = PdfWriter()
        for idx in page_indices:
            writer.add_page(reader.pages[idx])

        with open(output_path, "wb") as f:
            writer.write(f)

        # Convert back to 1-indexed for display
        extracted_pages = [i + 1 for i in page_indices]

        return PluginResult.success_result(
            data={
                "output": str(output_path),
                "extracted_pages": extracted_pages,
                "page_count": len(extracted_pages),
            },
            message=f"Extracted {len(extracted_pages)} pages → {output_path}",
        )

    async def _info(self, input: str) -> PluginResult:
        """Get PDF metadata and information."""
        input_path = self._resolve_path(input)

        if not input_path.exists():
            return PluginResult.error_result(
                f"File not found: {input_path}",
                code="FILE_NOT_FOUND",
            )

        reader = PdfReader(str(input_path))
        metadata = reader.metadata or {}

        # Extract metadata fields
        info = {
            "file": str(input_path),
            "pages": len(reader.pages),
            "encrypted": reader.is_encrypted,
        }

        # Standard PDF metadata fields
        if metadata:
            if metadata.title:
                info["title"] = metadata.title
            if metadata.author:
                info["author"] = metadata.author
            if metadata.subject:
                info["subject"] = metadata.subject
            if metadata.creator:
                info["creator"] = metadata.creator
            if metadata.producer:
                info["producer"] = metadata.producer
            if metadata.creation_date:
                info["created"] = str(metadata.creation_date)
            if metadata.modification_date:
                info["modified"] = str(metadata.modification_date)

        # File size
        info["size_bytes"] = input_path.stat().st_size
        info["size_human"] = self._human_size(info["size_bytes"])

        return PluginResult.success_result(
            data=info,
            message=f"{input_path.name}: {info['pages']} pages, {info['size_human']}",
        )

    async def _rotate(
        self,
        input: str,
        output: str,
        angle: int,
        pages: str = "all",
    ) -> PluginResult:
        """Rotate pages in a PDF."""
        if angle not in (90, 180, 270):
            return PluginResult.error_result(
                "Angle must be 90, 180, or 270 degrees",
                code="INVALID_INPUT",
            )

        input_path = self._resolve_path(input)
        output_path = self._resolve_path(output)

        if not input_path.exists():
            return PluginResult.error_result(
                f"Input file not found: {input_path}",
                code="FILE_NOT_FOUND",
            )

        reader = PdfReader(str(input_path))
        total_pages = len(reader.pages)

        # Parse page specification
        try:
            page_indices = parse_page_spec(pages, total_pages)
        except ValueError as e:
            return PluginResult.error_result(
                f"Invalid page specification: {e}",
                code="INVALID_INPUT",
            )

        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotate specified pages
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i in page_indices:
                page.rotate(angle)
            writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)

        rotated_count = len(page_indices)
        return PluginResult.success_result(
            data={
                "output": str(output_path),
                "rotated_pages": rotated_count,
                "angle": angle,
            },
            message=f"Rotated {rotated_count} pages by {angle}° → {output_path}",
        )

    async def _delete_pages(
        self,
        input: str,
        output: str,
        pages: str,
    ) -> PluginResult:
        """Delete specific pages from a PDF."""
        input_path = self._resolve_path(input)
        output_path = self._resolve_path(output)

        if not input_path.exists():
            return PluginResult.error_result(
                f"Input file not found: {input_path}",
                code="FILE_NOT_FOUND",
            )

        reader = PdfReader(str(input_path))
        total_pages = len(reader.pages)

        # Parse page specification
        try:
            pages_to_delete = set(parse_page_spec(pages, total_pages))
        except ValueError as e:
            return PluginResult.error_result(
                f"Invalid page specification: {e}",
                code="INVALID_INPUT",
            )

        if not pages_to_delete:
            return PluginResult.error_result(
                "No valid pages specified for deletion",
                code="INVALID_INPUT",
            )

        if len(pages_to_delete) >= total_pages:
            return PluginResult.error_result(
                "Cannot delete all pages from PDF",
                code="INVALID_INPUT",
            )

        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Keep pages not in the delete list
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i not in pages_to_delete:
                writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)

        remaining = total_pages - len(pages_to_delete)
        return PluginResult.success_result(
            data={
                "output": str(output_path),
                "deleted_count": len(pages_to_delete),
                "remaining_pages": remaining,
            },
            message=f"Deleted {len(pages_to_delete)} pages, {remaining} remaining → {output_path}",
        )

    async def _count_pages(self, input: str) -> PluginResult:
        """Count pages in a PDF."""
        input_path = self._resolve_path(input)

        if not input_path.exists():
            return PluginResult.error_result(
                f"File not found: {input_path}",
                code="FILE_NOT_FOUND",
            )

        reader = PdfReader(str(input_path))
        count = len(reader.pages)

        return PluginResult.success_result(
            data={"file": str(input_path), "pages": count},
            message=f"{input_path.name}: {count} pages",
        )

    def _human_size(self, size_bytes: int) -> str:
        """Convert bytes to human-readable size."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


__all__ = ["PDFPlugin"]
