"""Tests for the built-in PDF plugin."""


import pytest
from pypdf import PdfWriter

from mother.plugins.builtin.pdf import PDFPlugin, parse_page_spec


class TestParsePageSpec:
    """Tests for page specification parsing."""

    def test_all_keyword(self):
        """Test 'all' keyword returns all pages."""
        result = parse_page_spec("all", 5)
        assert result == [0, 1, 2, 3, 4]

    def test_all_keyword_case_insensitive(self):
        """Test 'ALL' works too."""
        result = parse_page_spec("ALL", 3)
        assert result == [0, 1, 2]

    def test_single_page(self):
        """Test single page number."""
        result = parse_page_spec("3", 5)
        assert result == [2]  # 0-indexed

    def test_multiple_pages(self):
        """Test comma-separated pages."""
        result = parse_page_spec("1,3,5", 5)
        assert result == [0, 2, 4]

    def test_page_range(self):
        """Test page range with hyphen."""
        result = parse_page_spec("2-4", 5)
        assert result == [1, 2, 3]

    def test_mixed_spec(self):
        """Test mixed pages and ranges."""
        result = parse_page_spec("1,3-5,7", 10)
        assert result == [0, 2, 3, 4, 6]

    def test_pages_with_spaces(self):
        """Test spaces are ignored."""
        result = parse_page_spec("1, 3, 5", 5)
        assert result == [0, 2, 4]

    def test_out_of_range_pages_ignored(self):
        """Test pages beyond total are ignored."""
        result = parse_page_spec("1,5,10", 5)
        assert result == [0, 4]  # 10 is beyond 5 pages

    def test_zero_page_ignored(self):
        """Test page 0 is ignored (1-indexed input)."""
        result = parse_page_spec("0,1,2", 5)
        assert result == [0, 1]  # Only pages 1 and 2

    def test_empty_result_for_invalid_range(self):
        """Test completely out of range returns empty."""
        result = parse_page_spec("10-15", 5)
        assert result == []

    def test_sorted_output(self):
        """Test result is always sorted."""
        result = parse_page_spec("5,3,1", 5)
        assert result == [0, 2, 4]


class TestPDFPlugin:
    """Tests for the PDFPlugin class."""

    @pytest.fixture
    def plugin(self):
        """Create a plugin instance."""
        return PDFPlugin()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample PDF for testing."""
        pdf_path = tmp_path / "sample.pdf"
        writer = PdfWriter()
        # Add 3 blank pages
        for _ in range(3):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        return pdf_path

    @pytest.fixture
    def multi_pdfs(self, tmp_path):
        """Create multiple sample PDFs for merge testing."""
        pdfs = []
        for i in range(3):
            pdf_path = tmp_path / f"doc_{i}.pdf"
            writer = PdfWriter()
            # Each PDF has i+1 pages
            for _ in range(i + 1):
                writer.add_blank_page(width=612, height=792)
            with open(pdf_path, "wb") as f:
                writer.write(f)
            pdfs.append(pdf_path)
        return pdfs

    def test_init(self, plugin):
        """Test plugin initialization."""
        assert plugin.manifest.plugin.name == "pdf"
        assert plugin.manifest.plugin.version == "1.0.0"

    def test_capabilities(self, plugin):
        """Test plugin capabilities are defined."""
        caps = plugin.get_capabilities()
        assert len(caps) == 7
        cap_names = [c.name for c in caps]
        assert "merge" in cap_names
        assert "split" in cap_names
        assert "extract_pages" in cap_names
        assert "info" in cap_names
        assert "rotate" in cap_names
        assert "delete_pages" in cap_names
        assert "count_pages" in cap_names

    def test_delete_pages_requires_confirmation(self, plugin):
        """Test delete_pages requires confirmation."""
        caps = plugin.get_capabilities()
        delete_cap = next(c for c in caps if c.name == "delete_pages")
        assert delete_cap.confirmation_required is True

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin):
        """Test unknown capability returns error."""
        result = await plugin.execute("unknown_cap", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"


class TestPDFPluginMerge:
    """Tests for PDF merge capability."""

    @pytest.fixture
    def plugin(self):
        return PDFPlugin()

    @pytest.fixture
    def multi_pdfs(self, tmp_path):
        """Create multiple sample PDFs."""
        pdfs = []
        for i in range(3):
            pdf_path = tmp_path / f"doc_{i}.pdf"
            writer = PdfWriter()
            for _ in range(i + 1):  # 1, 2, 3 pages respectively
                writer.add_blank_page(width=612, height=792)
            with open(pdf_path, "wb") as f:
                writer.write(f)
            pdfs.append(pdf_path)
        return pdfs

    @pytest.mark.asyncio
    async def test_merge_success(self, plugin, multi_pdfs, tmp_path):
        """Test successful merge."""
        output = tmp_path / "merged.pdf"
        result = await plugin.execute(
            "merge",
            {"files": [str(p) for p in multi_pdfs], "output": str(output)},
        )
        assert result.success is True
        assert output.exists()
        assert result.data["merged_files"] == 3
        assert result.data["total_pages"] == 6  # 1+2+3

    @pytest.mark.asyncio
    async def test_merge_no_files(self, plugin, tmp_path):
        """Test merge with no files."""
        result = await plugin.execute(
            "merge",
            {"files": [], "output": str(tmp_path / "out.pdf")},
        )
        assert result.success is False
        assert result.error_code == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_merge_single_file(self, plugin, multi_pdfs, tmp_path):
        """Test merge with only one file."""
        result = await plugin.execute(
            "merge",
            {"files": [str(multi_pdfs[0])], "output": str(tmp_path / "out.pdf")},
        )
        assert result.success is False
        assert result.error_code == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_merge_file_not_found(self, plugin, tmp_path):
        """Test merge with missing file."""
        result = await plugin.execute(
            "merge",
            {"files": ["/nonexistent/a.pdf", "/nonexistent/b.pdf"], "output": str(tmp_path / "out.pdf")},
        )
        assert result.success is False
        assert result.error_code == "FILE_NOT_FOUND"


class TestPDFPluginSplit:
    """Tests for PDF split capability."""

    @pytest.fixture
    def plugin(self):
        return PDFPlugin()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample 5-page PDF."""
        pdf_path = tmp_path / "sample.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        return pdf_path

    @pytest.mark.asyncio
    async def test_split_success(self, plugin, sample_pdf, tmp_path):
        """Test successful split."""
        output_dir = tmp_path / "split_output"
        result = await plugin.execute(
            "split",
            {"input": str(sample_pdf), "output_dir": str(output_dir)},
        )
        assert result.success is True
        assert output_dir.exists()
        assert result.data["page_count"] == 5
        # Check individual files created
        for i in range(1, 6):
            assert (output_dir / f"page_{i:03d}.pdf").exists()

    @pytest.mark.asyncio
    async def test_split_custom_prefix(self, plugin, sample_pdf, tmp_path):
        """Test split with custom prefix."""
        output_dir = tmp_path / "split_output"
        result = await plugin.execute(
            "split",
            {"input": str(sample_pdf), "output_dir": str(output_dir), "prefix": "doc"},
        )
        assert result.success is True
        assert (output_dir / "doc_001.pdf").exists()

    @pytest.mark.asyncio
    async def test_split_file_not_found(self, plugin, tmp_path):
        """Test split with missing file."""
        result = await plugin.execute(
            "split",
            {"input": "/nonexistent.pdf", "output_dir": str(tmp_path)},
        )
        assert result.success is False
        assert result.error_code == "FILE_NOT_FOUND"


class TestPDFPluginExtractPages:
    """Tests for PDF extract_pages capability."""

    @pytest.fixture
    def plugin(self):
        return PDFPlugin()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample 5-page PDF."""
        pdf_path = tmp_path / "sample.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        return pdf_path

    @pytest.mark.asyncio
    async def test_extract_pages_success(self, plugin, sample_pdf, tmp_path):
        """Test successful page extraction."""
        output = tmp_path / "extracted.pdf"
        result = await plugin.execute(
            "extract_pages",
            {"input": str(sample_pdf), "output": str(output), "pages": "1,3,5"},
        )
        assert result.success is True
        assert output.exists()
        assert result.data["page_count"] == 3
        assert result.data["extracted_pages"] == [1, 3, 5]

    @pytest.mark.asyncio
    async def test_extract_pages_range(self, plugin, sample_pdf, tmp_path):
        """Test page range extraction."""
        output = tmp_path / "extracted.pdf"
        result = await plugin.execute(
            "extract_pages",
            {"input": str(sample_pdf), "output": str(output), "pages": "2-4"},
        )
        assert result.success is True
        assert result.data["page_count"] == 3
        assert result.data["extracted_pages"] == [2, 3, 4]

    @pytest.mark.asyncio
    async def test_extract_pages_invalid_spec(self, plugin, sample_pdf, tmp_path):
        """Test with no valid pages."""
        output = tmp_path / "extracted.pdf"
        result = await plugin.execute(
            "extract_pages",
            {"input": str(sample_pdf), "output": str(output), "pages": "10-15"},
        )
        assert result.success is False
        assert result.error_code == "INVALID_INPUT"


class TestPDFPluginInfo:
    """Tests for PDF info capability."""

    @pytest.fixture
    def plugin(self):
        return PDFPlugin()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample PDF."""
        pdf_path = tmp_path / "sample.pdf"
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        return pdf_path

    @pytest.mark.asyncio
    async def test_info_success(self, plugin, sample_pdf):
        """Test getting PDF info."""
        result = await plugin.execute("info", {"input": str(sample_pdf)})
        assert result.success is True
        assert result.data["pages"] == 3
        assert result.data["encrypted"] is False
        assert "size_bytes" in result.data
        assert "size_human" in result.data

    @pytest.mark.asyncio
    async def test_info_file_not_found(self, plugin):
        """Test info with missing file."""
        result = await plugin.execute("info", {"input": "/nonexistent.pdf"})
        assert result.success is False
        assert result.error_code == "FILE_NOT_FOUND"


class TestPDFPluginRotate:
    """Tests for PDF rotate capability."""

    @pytest.fixture
    def plugin(self):
        return PDFPlugin()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample PDF."""
        pdf_path = tmp_path / "sample.pdf"
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        return pdf_path

    @pytest.mark.asyncio
    async def test_rotate_all_pages(self, plugin, sample_pdf, tmp_path):
        """Test rotating all pages."""
        output = tmp_path / "rotated.pdf"
        result = await plugin.execute(
            "rotate",
            {"input": str(sample_pdf), "output": str(output), "angle": 90},
        )
        assert result.success is True
        assert output.exists()
        assert result.data["rotated_pages"] == 3
        assert result.data["angle"] == 90

    @pytest.mark.asyncio
    async def test_rotate_specific_pages(self, plugin, sample_pdf, tmp_path):
        """Test rotating specific pages."""
        output = tmp_path / "rotated.pdf"
        result = await plugin.execute(
            "rotate",
            {"input": str(sample_pdf), "output": str(output), "angle": 180, "pages": "1,3"},
        )
        assert result.success is True
        assert result.data["rotated_pages"] == 2

    @pytest.mark.asyncio
    async def test_rotate_invalid_angle(self, plugin, sample_pdf, tmp_path):
        """Test with invalid rotation angle."""
        result = await plugin.execute(
            "rotate",
            {"input": str(sample_pdf), "output": str(tmp_path / "out.pdf"), "angle": 45},
        )
        assert result.success is False
        assert result.error_code == "INVALID_INPUT"


class TestPDFPluginDeletePages:
    """Tests for PDF delete_pages capability."""

    @pytest.fixture
    def plugin(self):
        return PDFPlugin()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample 5-page PDF."""
        pdf_path = tmp_path / "sample.pdf"
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        return pdf_path

    @pytest.mark.asyncio
    async def test_delete_pages_success(self, plugin, sample_pdf, tmp_path):
        """Test deleting specific pages."""
        output = tmp_path / "deleted.pdf"
        result = await plugin.execute(
            "delete_pages",
            {"input": str(sample_pdf), "output": str(output), "pages": "2,4"},
        )
        assert result.success is True
        assert output.exists()
        assert result.data["deleted_count"] == 2
        assert result.data["remaining_pages"] == 3

    @pytest.mark.asyncio
    async def test_delete_cannot_delete_all(self, plugin, sample_pdf, tmp_path):
        """Test cannot delete all pages."""
        result = await plugin.execute(
            "delete_pages",
            {"input": str(sample_pdf), "output": str(tmp_path / "out.pdf"), "pages": "1-5"},
        )
        assert result.success is False
        assert result.error_code == "INVALID_INPUT"


class TestPDFPluginCountPages:
    """Tests for PDF count_pages capability."""

    @pytest.fixture
    def plugin(self):
        return PDFPlugin()

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample PDF."""
        pdf_path = tmp_path / "sample.pdf"
        writer = PdfWriter()
        for _ in range(7):
            writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        return pdf_path

    @pytest.mark.asyncio
    async def test_count_pages_success(self, plugin, sample_pdf):
        """Test counting pages."""
        result = await plugin.execute("count_pages", {"input": str(sample_pdf)})
        assert result.success is True
        assert result.data["pages"] == 7

    @pytest.mark.asyncio
    async def test_count_pages_file_not_found(self, plugin):
        """Test count with missing file."""
        result = await plugin.execute("count_pages", {"input": "/nonexistent.pdf"})
        assert result.success is False
        assert result.error_code == "FILE_NOT_FOUND"
