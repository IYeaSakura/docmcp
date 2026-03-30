"""
Test handlers for document processing.

This module tests:
- Document format detection
- Document creation from bytes and files
- Document metadata handling
- Document content extraction
- All supported document formats
"""

import pytest
from pathlib import Path
from datetime import datetime

from docmcp.core.document import (
    BaseDocument,
    DocumentFormat,
    DocumentType,
    DocumentMetadata,
    DocumentContent,
    ContentType,
)


# ============================================================================
# DocumentFormat Tests
# ============================================================================

class TestDocumentFormat:
    """Test DocumentFormat enum and utilities."""

    def test_format_from_extension_with_dot(self):
        """Test format detection from extension with dot."""
        assert DocumentFormat.from_extension(".pdf") == DocumentFormat.PDF
        assert DocumentFormat.from_extension(".docx") == DocumentFormat.DOCX
        assert DocumentFormat.from_extension(".xlsx") == DocumentFormat.XLSX
        assert DocumentFormat.from_extension(".pptx") == DocumentFormat.PPTX

    def test_format_from_extension_without_dot(self):
        """Test format detection from extension without dot."""
        assert DocumentFormat.from_extension("pdf") == DocumentFormat.PDF
        assert DocumentFormat.from_extension("docx") == DocumentFormat.DOCX
        assert DocumentFormat.from_extension("txt") == DocumentFormat.TXT

    def test_format_from_extension_case_insensitive(self):
        """Test format detection is case insensitive."""
        assert DocumentFormat.from_extension(".PDF") == DocumentFormat.PDF
        assert DocumentFormat.from_extension(".Docx") == DocumentFormat.DOCX

    def test_format_from_extension_unknown(self):
        """Test format detection for unknown extension."""
        assert DocumentFormat.from_extension(".unknown") == DocumentFormat.UNKNOWN
        assert DocumentFormat.from_extension("") == DocumentFormat.UNKNOWN

    def test_format_from_mime_type(self):
        """Test format detection from MIME type."""
        assert DocumentFormat.from_mime_type("application/pdf") == DocumentFormat.PDF
        assert DocumentFormat.from_mime_type(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ) == DocumentFormat.DOCX
        assert DocumentFormat.from_mime_type("text/plain") == DocumentFormat.TXT

    def test_format_mime_type_property(self):
        """Test MIME type property for each format."""
        assert DocumentFormat.PDF.mime_type == "application/pdf"
        assert DocumentFormat.DOCX.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert DocumentFormat.TXT.mime_type == "text/plain"

    def test_format_extensions_property(self):
        """Test extensions property for each format."""
        assert ".pdf" in DocumentFormat.PDF.extensions
        assert ".docx" in DocumentFormat.DOCX.extensions
        assert ".txt" in DocumentFormat.TXT.extensions
        assert ".html" in DocumentFormat.HTML.extensions
        assert ".htm" in DocumentFormat.HTML.extensions


# ============================================================================
# DocumentType Tests
# ============================================================================

class TestDocumentType:
    """Test DocumentType enum and utilities."""

    def test_type_from_format_word(self):
        """Test document type detection for Word formats."""
        assert DocumentType.from_format(DocumentFormat.DOC) == DocumentType.WORD_PROCESSING
        assert DocumentType.from_format(DocumentFormat.DOCX) == DocumentType.WORD_PROCESSING

    def test_type_from_format_spreadsheet(self):
        """Test document type detection for spreadsheet formats."""
        assert DocumentType.from_format(DocumentFormat.XLS) == DocumentType.SPREADSHEET
        assert DocumentType.from_format(DocumentFormat.XLSX) == DocumentType.SPREADSHEET

    def test_type_from_format_presentation(self):
        """Test document type detection for presentation formats."""
        assert DocumentType.from_format(DocumentFormat.PPT) == DocumentType.PRESENTATION
        assert DocumentType.from_format(DocumentFormat.PPTX) == DocumentType.PRESENTATION

    def test_type_from_format_pdf(self):
        """Test document type detection for PDF."""
        assert DocumentType.from_format(DocumentFormat.PDF) == DocumentType.PDF

    def test_type_from_format_text(self):
        """Test document type detection for text formats."""
        assert DocumentType.from_format(DocumentFormat.TXT) == DocumentType.TEXT
        assert DocumentType.from_format(DocumentFormat.MD) == DocumentType.TEXT

    def test_type_from_format_unknown(self):
        """Test document type detection for unknown format."""
        assert DocumentType.from_format(DocumentFormat.UNKNOWN) == DocumentType.UNKNOWN


# ============================================================================
# DocumentMetadata Tests
# ============================================================================

class TestDocumentMetadata:
    """Test DocumentMetadata class."""

    def test_default_metadata(self):
        """Test default metadata values."""
        metadata = DocumentMetadata()
        assert metadata.filename == "unknown"
        assert metadata.file_size == 0
        assert metadata.author is None
        assert metadata.tags == []
        assert metadata.custom_properties == {}

    def test_metadata_creation(self):
        """Test metadata creation with values."""
        metadata = DocumentMetadata(
            filename="test.pdf",
            file_size=1024,
            author="Test Author",
            title="Test Title",
            tags=["test", "pdf"],
            custom_properties={"key": "value"},
        )
        assert metadata.filename == "test.pdf"
        assert metadata.file_size == 1024
        assert metadata.author == "Test Author"
        assert metadata.tags == ["test", "pdf"]
        assert metadata.custom_properties == {"key": "value"}

    def test_metadata_to_dict(self):
        """Test metadata serialization to dict."""
        metadata = DocumentMetadata(
            filename="test.pdf",
            file_size=1024,
            author="Test Author",
        )
        data = metadata.to_dict()
        assert data["filename"] == "test.pdf"
        assert data["file_size"] == 1024
        assert data["author"] == "Test Author"
        assert "created_at" in data

    def test_metadata_from_dict(self):
        """Test metadata deserialization from dict."""
        data = {
            "filename": "test.pdf",
            "file_size": 1024,
            "author": "Test Author",
            "created_at": datetime.utcnow().isoformat(),
            "modified_at": datetime.utcnow().isoformat(),
        }
        metadata = DocumentMetadata.from_dict(data)
        assert metadata.filename == "test.pdf"
        assert metadata.file_size == 1024
        assert metadata.author == "Test Author"


# ============================================================================
# DocumentContent Tests
# ============================================================================

class TestDocumentContent:
    """Test DocumentContent class."""

    def test_default_content(self):
        """Test default content values."""
        content = DocumentContent()
        assert content.text == ""
        assert content.structured_content == {}
        assert content.images == []
        assert content.tables == []
        assert content.hyperlinks == []

    def test_content_creation(self):
        """Test content creation with values."""
        content = DocumentContent(
            text="Hello World",
            structured_content={"paragraphs": [{"text": "Hello"}]},
            images=[{"id": "img1"}],
            tables=[{"headers": ["A", "B"]}],
            hyperlinks=[{"url": "https://example.com"}],
        )
        assert content.text == "Hello World"
        assert content.structured_content == {"paragraphs": [{"text": "Hello"}]}
        assert len(content.images) == 1
        assert len(content.tables) == 1
        assert len(content.hyperlinks) == 1

    def test_get_text_chunks(self):
        """Test text chunking functionality."""
        text = "ABCDEFGHIJ" * 10  # 100 characters
        content = DocumentContent(text=text)

        chunks = content.get_text_chunks(chunk_size=30, overlap=5)
        assert len(chunks) > 1
        # First chunk should be 30 characters
        assert len(chunks[0]) == 30

    def test_get_text_chunks_empty(self):
        """Test text chunking with empty text."""
        content = DocumentContent(text="")
        chunks = content.get_text_chunks()
        assert chunks == []

    def test_get_text_chunks_small_text(self):
        """Test text chunking with small text."""
        content = DocumentContent(text="Small")
        chunks = content.get_text_chunks(chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == "Small"

    def test_content_to_dict(self):
        """Test content serialization to dict."""
        content = DocumentContent(
            text="Hello",
            structured_content={"key": "value"},
        )
        data = content.to_dict()
        assert data["text"] == "Hello"
        assert data["structured_content"] == {"key": "value"}


# ============================================================================
# BaseDocument Tests
# ============================================================================

class TestBaseDocument:
    """Test BaseDocument class."""

    def test_document_creation_defaults(self):
        """Test document creation with default values."""
        doc = BaseDocument()
        assert doc.id is not None
        assert doc.format == DocumentFormat.UNKNOWN
        assert doc.content is None
        assert doc.checksum is None

    def test_document_from_bytes(self):
        """Test document creation from bytes."""
        content = b"Test content"
        doc = BaseDocument.from_bytes(
            content=content,
            filename="test.pdf",
            format=DocumentFormat.PDF,
        )
        assert doc.format == DocumentFormat.PDF
        assert doc.content == content
        assert doc.metadata.filename == "test.pdf"
        assert doc.metadata.file_size == len(content)
        assert doc.checksum is not None

    def test_document_from_bytes_auto_format(self):
        """Test document creation with auto-detected format."""
        content = b"Test content"
        doc = BaseDocument.from_bytes(
            content=content,
            filename="test.docx",
        )
        assert doc.format == DocumentFormat.DOCX

    def test_document_from_file(self, temp_file: Path):
        """Test document creation from file."""
        doc = BaseDocument.from_file(temp_file)
        assert doc.format == DocumentFormat.TXT
        assert doc.content is not None
        assert doc.metadata.filename == temp_file.name

    def test_document_checksum_computation(self):
        """Test checksum computation."""
        content = b"Test content"
        doc = BaseDocument.from_bytes(
            content=content,
            filename="test.txt",
        )
        assert doc.checksum is not None
        assert len(doc.checksum) == 64  # SHA-256 hex length

    def test_document_verify_checksum_valid(self):
        """Test checksum verification with valid content."""
        content = b"Test content"
        doc = BaseDocument.from_bytes(
            content=content,
            filename="test.txt",
        )
        assert doc.verify_checksum() is True

    def test_document_verify_checksum_invalid(self):
        """Test checksum verification with modified content."""
        content = b"Test content"
        doc = BaseDocument.from_bytes(
            content=content,
            filename="test.txt",
        )
        # Modify content
        doc.content = b"Modified content"
        assert doc.verify_checksum() is False

    def test_document_verify_checksum_no_content(self):
        """Test checksum verification with no content."""
        doc = BaseDocument()
        assert doc.verify_checksum() is False

    def test_document_type_property(self):
        """Test document type property."""
        doc_pdf = BaseDocument(format=DocumentFormat.PDF)
        assert doc_pdf.document_type == DocumentType.PDF

        doc_docx = BaseDocument(format=DocumentFormat.DOCX)
        assert doc_docx.document_type == DocumentType.WORD_PROCESSING

    def test_has_content_property(self):
        """Test has_content property."""
        doc_empty = BaseDocument()
        assert doc_empty.has_content is False

        doc_with_content = BaseDocument(content=b"test")
        assert doc_with_content.has_content is True

    def test_has_extracted_content_property(self):
        """Test has_extracted_content property."""
        doc_empty = BaseDocument()
        assert doc_empty.has_extracted_content is False

        doc_with_content = BaseDocument(
            extracted_content=DocumentContent(text="test")
        )
        assert doc_with_content.has_extracted_content is True

    def test_document_to_dict(self):
        """Test document serialization to dict."""
        doc = BaseDocument.from_bytes(
            content=b"test",
            filename="test.txt",
            format=DocumentFormat.TXT,
        )
        data = doc.to_dict()
        assert data["format"] == "txt"
        assert data["has_content"] is True
        assert data["has_extracted_content"] is False
        assert "id" in data
        assert "metadata" in data


# ============================================================================
# Format-Specific Document Tests
# ============================================================================

class TestFormatSpecificDocuments:
    """Test documents for all supported formats."""

    def test_pdf_document(self, sample_documents: dict):
        """Test PDF document."""
        doc = sample_documents[DocumentFormat.PDF]
        assert doc.format == DocumentFormat.PDF
        assert doc.document_type == DocumentType.PDF
        assert doc.content.startswith(b"%PDF")

    def test_docx_document(self, sample_documents: dict):
        """Test DOCX document."""
        doc = sample_documents[DocumentFormat.DOCX]
        assert doc.format == DocumentFormat.DOCX
        assert doc.document_type == DocumentType.WORD_PROCESSING

    def test_xlsx_document(self, sample_documents: dict):
        """Test XLSX document."""
        doc = sample_documents[DocumentFormat.XLSX]
        assert doc.format == DocumentFormat.XLSX
        assert doc.document_type == DocumentType.SPREADSHEET

    def test_pptx_document(self, sample_documents: dict):
        """Test PPTX document."""
        doc = sample_documents[DocumentFormat.PPTX]
        assert doc.format == DocumentFormat.PPTX
        assert doc.document_type == DocumentType.PRESENTATION

    def test_txt_document(self, sample_documents: dict):
        """Test TXT document."""
        doc = sample_documents[DocumentFormat.TXT]
        assert doc.format == DocumentFormat.TXT
        assert doc.document_type == DocumentType.TEXT


# ============================================================================
# ContentType Tests
# ============================================================================

class TestContentType:
    """Test ContentType enum."""

    def test_content_type_values(self):
        """Test content type values."""
        assert ContentType.TEXT.value == "text"
        assert ContentType.IMAGE.value == "image"
        assert ContentType.TABLE.value == "table"
        assert ContentType.CHART.value == "chart"
        assert ContentType.HYPERLINK.value == "hyperlink"
        assert ContentType.METADATA.value == "metadata"
        assert ContentType.STRUCTURE.value == "structure"


# ============================================================================
# Integration Tests with Sample Files
# ============================================================================

class TestWithSampleFiles:
    """Test using actual sample files."""

    def test_load_sample_pdf(self):
        """Test loading sample PDF file."""
        sample_path = Path(__file__).parent / "data" / "sample.pdf"
        if sample_path.exists():
            doc = BaseDocument.from_file(sample_path)
            assert doc.format == DocumentFormat.PDF
            assert doc.content is not None
            assert doc.metadata.file_size > 0

    def test_load_sample_docx(self):
        """Test loading sample DOCX file."""
        sample_path = Path(__file__).parent / "data" / "sample.docx"
        if sample_path.exists():
            doc = BaseDocument.from_file(sample_path)
            assert doc.format == DocumentFormat.DOCX
            assert doc.content is not None

    def test_load_sample_txt(self):
        """Test loading sample TXT file."""
        sample_path = Path(__file__).parent / "data" / "sample.txt"
        if sample_path.exists():
            doc = BaseDocument.from_file(sample_path)
            assert doc.format == DocumentFormat.TXT
            content_text = doc.content.decode('utf-8')
            assert "Test Text Document" in content_text

    def test_load_sample_html(self):
        """Test loading sample HTML file."""
        sample_path = Path(__file__).parent / "data" / "sample.html"
        if sample_path.exists():
            doc = BaseDocument.from_file(sample_path)
            assert doc.format == DocumentFormat.HTML
            content_text = doc.content.decode('utf-8')
            assert "<html" in content_text.lower()

    def test_load_sample_md(self):
        """Test loading sample Markdown file."""
        sample_path = Path(__file__).parent / "data" / "sample.md"
        if sample_path.exists():
            doc = BaseDocument.from_file(sample_path)
            assert doc.format == DocumentFormat.MD
            content_text = doc.content.decode('utf-8')
            assert "#" in content_text  # Markdown header


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestDocumentErrorHandling:
    """Test error handling in document operations."""

    def test_nonexistent_file(self):
        """Test loading a nonexistent file."""
        with pytest.raises(FileNotFoundError):
            BaseDocument.from_file("/nonexistent/path/file.pdf")

    def test_empty_bytes(self):
        """Test creating document from empty bytes."""
        doc = BaseDocument.from_bytes(
            content=b"",
            filename="empty.txt",
        )
        assert doc.metadata.file_size == 0
        assert doc.checksum is not None


# ============================================================================
# Performance Tests
# ============================================================================

class TestDocumentPerformance:
    """Test document processing performance."""

    def test_large_content_checksum(self):
        """Test checksum computation for large content."""
        import time

        # Create 1MB of content
        large_content = b"x" * (1024 * 1024)

        start = time.time()
        doc = BaseDocument.from_bytes(
            content=large_content,
            filename="large.bin",
        )
        elapsed = time.time() - start

        # Should complete in reasonable time (< 1 second)
        assert elapsed < 1.0
        assert doc.checksum is not None

    def test_multiple_document_creation(self):
        """Test creating multiple documents efficiently."""
        import time

        start = time.time()
        docs = []
        for i in range(100):
            doc = BaseDocument.from_bytes(
                content=b"test content",
                filename=f"test{i}.txt",
            )
            docs.append(doc)
        elapsed = time.time() - start

        # Should complete quickly
        assert elapsed < 1.0
        assert len(docs) == 100
        # Each document should have unique ID
        ids = [d.id for d in docs]
        assert len(set(ids)) == 100
