"""Tests for the built-in datacraft plugin."""

import pytest
from pypdf import PdfWriter

from mother.plugins.builtin.datacraft import DatacraftPlugin
from mother.plugins.builtin.datacraft.parsers import (
    chunk_text,
    detect_document_type,
    extract_entities_simple,
)
from mother.plugins.builtin.datacraft.storage import Document, DocumentStore


class TestChunkText:
    """Tests for text chunking."""

    def test_empty_text(self):
        """Test empty text returns empty list."""
        result = chunk_text("")
        assert result == []

    def test_short_text(self):
        """Test short text returns single chunk."""
        result = chunk_text("Hello world")
        assert len(result) == 1
        assert result[0] == "Hello world"

    def test_long_text_chunking(self):
        """Test long text is chunked properly."""
        # Create text longer than default chunk size
        text = "This is a sentence. " * 100  # ~2000 chars
        result = chunk_text(text, chunk_size=500, overlap=100)
        assert len(result) > 1
        # Each chunk should be reasonable size
        for chunk in result:
            assert len(chunk) <= 600  # Some tolerance for sentence boundaries

    def test_preserves_sentence_boundaries(self):
        """Test chunks break at sentence boundaries when possible."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = chunk_text(text, chunk_size=40, overlap=10)
        # Should try to break at periods
        for chunk in result:
            if not chunk.endswith("."):
                # Last chunk might not end with period
                assert chunk == result[-1] or "." in chunk


class TestExtractEntities:
    """Tests for entity extraction."""

    def test_extract_email(self):
        """Test email extraction."""
        text = "Contact us at hello@example.com for more info."
        entities = extract_entities_simple(text)
        emails = [e for e in entities if e["type"] == "EMAIL"]
        assert len(emails) == 1
        assert emails[0]["value"] == "hello@example.com"

    def test_extract_phone(self):
        """Test phone number extraction."""
        text = "Call us at (555) 123-4567 or +1-555-987-6543."
        entities = extract_entities_simple(text)
        phones = [e for e in entities if e["type"] == "PHONE"]
        assert len(phones) >= 1

    def test_extract_date(self):
        """Test date extraction."""
        text = "The invoice is dated 15.03.2024 and due on 2024-04-15."
        entities = extract_entities_simple(text)
        dates = [e for e in entities if e["type"] == "DATE"]
        assert len(dates) >= 1

    def test_extract_money(self):
        """Test money amount extraction."""
        text = "Total: $1,234.56 or €500.00 EUR"
        entities = extract_entities_simple(text)
        money = [e for e in entities if e["type"] == "MONEY"]
        assert len(money) >= 1

    def test_extract_iban(self):
        """Test IBAN extraction."""
        text = "Bank account: DE89370400440532013000"
        entities = extract_entities_simple(text)
        ibans = [e for e in entities if e["type"] == "IBAN"]
        assert len(ibans) == 1


class TestDetectDocumentType:
    """Tests for document type detection."""

    def test_detect_invoice_from_filename(self):
        """Test invoice detection from filename."""
        assert detect_document_type("invoice_2024.pdf", "") == "invoice"
        assert detect_document_type("Rechnung_123.pdf", "") == "invoice"

    def test_detect_invoice_from_content(self):
        """Test invoice detection from content."""
        content = "Invoice Number: 12345\nTotal Amount: $500.00\nDue Date: 2024-03-15"
        assert detect_document_type("document.pdf", content) == "invoice"

    def test_detect_receipt(self):
        """Test receipt detection."""
        assert detect_document_type("receipt_store.pdf", "") == "receipt"

    def test_detect_bank_statement(self):
        """Test bank statement detection."""
        content = "Account Balance: $5,000.00\nTransaction History\nÜberweisung"
        assert detect_document_type("statement.pdf", content) == "bank_statement"

    def test_detect_contract(self):
        """Test contract detection."""
        content = "The parties hereby agree to the following terms and conditions."
        assert detect_document_type("document.pdf", content) == "contract"

    def test_fallback_to_other(self):
        """Test fallback to 'other' for unknown types."""
        assert detect_document_type("random.pdf", "Some random text") == "other"


class TestDocumentStore:
    """Tests for document storage."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a temporary document store."""
        db_path = tmp_path / "test.db"
        return DocumentStore(db_path)

    @pytest.fixture
    def sample_doc(self):
        """Create a sample document."""
        return Document(
            doc_id="test123",
            filename="test.pdf",
            doc_type="invoice",
            content="This is test content for the document.",
            chunks=["This is test", "content for the", "document."],
            metadata={"author": "Test"},
            entities=[{"type": "EMAIL", "value": "test@example.com"}],
            file_hash="abc123",
            pages=1,
        )

    def test_store_and_retrieve(self, store, sample_doc):
        """Test storing and retrieving a document."""
        store.store_document(sample_doc)
        retrieved = store.get_document("test123")

        assert retrieved is not None
        assert retrieved.doc_id == "test123"
        assert retrieved.filename == "test.pdf"
        assert retrieved.doc_type == "invoice"
        assert len(retrieved.chunks) == 3

    def test_list_documents(self, store, sample_doc):
        """Test listing documents."""
        store.store_document(sample_doc)
        docs = store.list_documents()

        assert len(docs) == 1
        assert docs[0]["doc_id"] == "test123"

    def test_list_documents_by_type(self, store, sample_doc):
        """Test filtering by document type."""
        store.store_document(sample_doc)

        # Create another document of different type
        other_doc = Document(
            doc_id="other456",
            filename="other.pdf",
            doc_type="receipt",
            content="Other content",
            chunks=["Other content"],
        )
        store.store_document(other_doc)

        invoices = store.list_documents(doc_type="invoice")
        assert len(invoices) == 1
        assert invoices[0]["doc_type"] == "invoice"

    def test_delete_document(self, store, sample_doc):
        """Test deleting a document."""
        store.store_document(sample_doc)
        assert store.get_document("test123") is not None

        deleted = store.delete_document("test123")
        assert deleted is True
        assert store.get_document("test123") is None

    def test_search(self, store, sample_doc):
        """Test full-text search."""
        store.store_document(sample_doc)
        results = store.search("test content")

        assert len(results) >= 1
        assert results[0].doc_id == "test123"

    def test_get_stats(self, store, sample_doc):
        """Test getting storage stats."""
        store.store_document(sample_doc)
        stats = store.get_stats()

        assert stats["total_documents"] == 1
        assert stats["total_chunks"] == 3
        assert stats["total_entities"] == 1

    def test_generate_doc_id(self, store):
        """Test document ID generation."""
        id1 = store.generate_doc_id("content1", "file1.pdf")
        id2 = store.generate_doc_id("content1", "file1.pdf")
        id3 = store.generate_doc_id("content2", "file2.pdf")

        # Same content/filename should produce same ID
        assert id1 == id2
        # Different content should produce different ID
        assert id1 != id3


class TestDatacraftPlugin:
    """Tests for the DatacraftPlugin class."""

    @pytest.fixture
    def plugin(self, tmp_path):
        """Create a plugin with temporary storage."""
        return DatacraftPlugin(config={"db_path": str(tmp_path / "test.db")})

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a sample PDF for testing."""
        pdf_path = tmp_path / "sample.pdf"
        writer = PdfWriter()
        # Add a page with some content
        writer.add_blank_page(width=612, height=792)
        with open(pdf_path, "wb") as f:
            writer.write(f)
        return pdf_path

    @pytest.fixture
    def sample_txt(self, tmp_path):
        """Create a sample text file."""
        txt_path = tmp_path / "sample.txt"
        txt_path.write_text(
            "Invoice Number: 12345\nTotal Amount: $500.00\nEmail: billing@example.com\nDue Date: 2024-03-15"
        )
        return txt_path

    def test_init(self, plugin):
        """Test plugin initialization."""
        assert plugin.manifest.plugin.name == "datacraft"
        assert plugin.manifest.plugin.version == "1.0.0"

    def test_capabilities(self, plugin):
        """Test plugin capabilities are defined."""
        caps = plugin.get_capabilities()
        assert len(caps) == 8
        cap_names = [c.name for c in caps]
        assert "process" in cap_names
        assert "search" in cap_names
        assert "tables" in cap_names
        assert "list" in cap_names
        assert "stats" in cap_names
        assert "delete" in cap_names

    def test_delete_requires_confirmation(self, plugin):
        """Test delete requires confirmation."""
        caps = plugin.get_capabilities()
        delete_cap = next(c for c in caps if c.name == "delete")
        assert delete_cap.confirmation_required is True

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin):
        """Test unknown capability returns error."""
        result = await plugin.execute("unknown_cap", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_process_txt(self, plugin, sample_txt):
        """Test processing a text file."""
        result = await plugin.execute("process", {"path": str(sample_txt)})
        assert result.success is True
        assert result.data["processed"] == 1
        assert result.data["documents"][0]["doc_type"] == "invoice"

    @pytest.mark.asyncio
    async def test_process_no_store(self, plugin, sample_txt):
        """Test processing without storing."""
        result = await plugin.execute(
            "process",
            {"path": str(sample_txt), "no_store": True},
        )
        assert result.success is True

        # Should not be in storage
        list_result = await plugin.execute("list", {})
        assert list_result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_process_file_not_found(self, plugin):
        """Test processing non-existent file."""
        result = await plugin.execute("process", {"path": "/nonexistent/file.pdf"})
        assert result.success is False
        assert result.error_code == "FILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_search(self, plugin, sample_txt):
        """Test searching documents."""
        # First process a document
        await plugin.execute("process", {"path": str(sample_txt)})

        # Then search
        result = await plugin.execute("search", {"query": "invoice"})
        assert result.success is True
        assert result.data["count"] >= 1

    @pytest.mark.asyncio
    async def test_list(self, plugin, sample_txt):
        """Test listing documents."""
        await plugin.execute("process", {"path": str(sample_txt)})

        result = await plugin.execute("list", {})
        assert result.success is True
        assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_stats(self, plugin, sample_txt):
        """Test getting stats."""
        await plugin.execute("process", {"path": str(sample_txt)})

        result = await plugin.execute("stats", {})
        assert result.success is True
        assert result.data["total_documents"] == 1

    @pytest.mark.asyncio
    async def test_delete(self, plugin, sample_txt):
        """Test deleting a document."""
        # Process
        process_result = await plugin.execute("process", {"path": str(sample_txt)})
        doc_id = process_result.data["documents"][0]["doc_id"]

        # Delete
        result = await plugin.execute("delete", {"doc_id": doc_id})
        assert result.success is True

        # Verify deleted
        list_result = await plugin.execute("list", {})
        assert list_result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_delete_not_found(self, plugin):
        """Test deleting non-existent document."""
        result = await plugin.execute("delete", {"doc_id": "nonexistent"})
        assert result.success is False
        assert result.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get(self, plugin, sample_txt):
        """Test getting a document by ID."""
        # Process
        process_result = await plugin.execute("process", {"path": str(sample_txt)})
        doc_id = process_result.data["documents"][0]["doc_id"]

        # Get
        result = await plugin.execute("get", {"doc_id": doc_id})
        assert result.success is True
        assert result.data["doc_id"] == doc_id

    @pytest.mark.asyncio
    async def test_get_not_found(self, plugin):
        """Test getting non-existent document."""
        result = await plugin.execute("get", {"doc_id": "nonexistent"})
        assert result.success is False
        assert result.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_tables(self, plugin, sample_txt):
        """Test extracting tables."""
        result = await plugin.execute("tables", {"path": str(sample_txt)})
        assert result.success is True
        # Text file likely has no tables
        assert "tables" in result.data

    @pytest.mark.asyncio
    async def test_tables_file_not_found(self, plugin):
        """Test tables with missing file."""
        result = await plugin.execute("tables", {"path": "/nonexistent.pdf"})
        assert result.success is False
        assert result.error_code == "FILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_graph(self, plugin, sample_txt):
        """Test getting knowledge graph."""
        # Process
        process_result = await plugin.execute("process", {"path": str(sample_txt)})
        doc_id = process_result.data["documents"][0]["doc_id"]

        # Get graph
        result = await plugin.execute("graph", {"doc_id": doc_id})
        assert result.success is True
        assert "entities" in result.data
        assert "relationships" in result.data

    @pytest.mark.asyncio
    async def test_process_directory(self, plugin, tmp_path):
        """Test processing a directory."""
        # Create multiple files
        (tmp_path / "doc1.txt").write_text("First document content")
        (tmp_path / "doc2.txt").write_text("Second document content")

        result = await plugin.execute("process", {"path": str(tmp_path)})
        assert result.success is True
        assert result.data["processed"] == 2

    @pytest.mark.asyncio
    async def test_unsupported_file_type(self, plugin, tmp_path):
        """Test handling unsupported file type."""
        unsupported = tmp_path / "file.xyz"
        unsupported.write_text("content")

        result = await plugin.execute("process", {"path": str(unsupported)})
        # Should fail gracefully
        assert result.data["failed"] == 1
