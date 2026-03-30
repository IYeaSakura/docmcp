"""
Document abstraction module for DocMCP.

This module defines the core abstractions for documents in the DocMCP system,
including document types, formats, metadata, and content representations.

The design follows the principles of:
    - Immutability: Document objects are immutable once created
    - Type safety: Full type annotations and validation
    - Extensibility: Easy to add new document formats
    - Performance: Lazy loading and memory-efficient representations
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union


class DocumentFormat(Enum):
    """
    Supported document formats.

    This enum defines all document formats supported by the DocMCP system.
    Each format has associated MIME types and file extensions.

    Attributes:
        DOC: Microsoft Word 97-2003 format
        DOCX: Microsoft Word Open XML format
        PDF: Portable Document Format
        XLS: Microsoft Excel 97-2003 format
        XLSX: Microsoft Excel Open XML format
        PPT: Microsoft PowerPoint 97-2003 format
        PPTX: Microsoft PowerPoint Open XML format
        TXT: Plain text format
        HTML: HyperText Markup Language
        MD: Markdown format
        UNKNOWN: Unknown or unsupported format
    """

    DOC = "doc"
    DOCX = "docx"
    PDF = "pdf"
    XLS = "xls"
    XLSX = "xlsx"
    PPT = "ppt"
    PPTX = "pptx"
    TXT = "txt"
    HTML = "html"
    MD = "md"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, extension: str) -> DocumentFormat:
        """
        Get DocumentFormat from file extension.

        Args:
            extension: File extension (with or without dot)

        Returns:
            DocumentFormat enum value

        Example:
            >>> DocumentFormat.from_extension(".pdf")
            DocumentFormat.PDF
            >>> DocumentFormat.from_extension("docx")
            DocumentFormat.DOCX
        """
        ext = extension.lower().lstrip(".")
        mapping = {
            "doc": cls.DOC,
            "docx": cls.DOCX,
            "pdf": cls.PDF,
            "xls": cls.XLS,
            "xlsx": cls.XLSX,
            "ppt": cls.PPT,
            "pptx": cls.PPTX,
            "txt": cls.TXT,
            "html": cls.HTML,
            "htm": cls.HTML,
            "md": cls.MD,
            "markdown": cls.MD,
        }
        return mapping.get(ext, cls.UNKNOWN)

    @classmethod
    def from_mime_type(cls, mime_type: str) -> DocumentFormat:
        """
        Get DocumentFormat from MIME type.

        Args:
            mime_type: MIME type string

        Returns:
            DocumentFormat enum value
        """
        mime_mapping = {
            "application/msword": cls.DOC,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": cls.DOCX,
            "application/pdf": cls.PDF,
            "application/vnd.ms-excel": cls.XLS,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": cls.XLSX,
            "application/vnd.ms-powerpoint": cls.PPT,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": cls.PPTX,
            "text/plain": cls.TXT,
            "text/html": cls.HTML,
            "text/markdown": cls.MD,
        }
        return mime_mapping.get(mime_type.lower(), cls.UNKNOWN)

    @property
    def mime_type(self) -> str:
        """Get the primary MIME type for this format."""
        mime_types = {
            DocumentFormat.DOC: "application/msword",
            DocumentFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            DocumentFormat.PDF: "application/pdf",
            DocumentFormat.XLS: "application/vnd.ms-excel",
            DocumentFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            DocumentFormat.PPT: "application/vnd.ms-powerpoint",
            DocumentFormat.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            DocumentFormat.TXT: "text/plain",
            DocumentFormat.HTML: "text/html",
            DocumentFormat.MD: "text/markdown",
            DocumentFormat.UNKNOWN: "application/octet-stream",
        }
        return mime_types[self]

    @property
    def extensions(self) -> List[str]:
        """Get all file extensions for this format."""
        extensions_map = {
            DocumentFormat.DOC: [".doc"],
            DocumentFormat.DOCX: [".docx"],
            DocumentFormat.PDF: [".pdf"],
            DocumentFormat.XLS: [".xls"],
            DocumentFormat.XLSX: [".xlsx"],
            DocumentFormat.PPT: [".ppt"],
            DocumentFormat.PPTX: [".pptx"],
            DocumentFormat.TXT: [".txt"],
            DocumentFormat.HTML: [".html", ".htm"],
            DocumentFormat.MD: [".md", ".markdown"],
            DocumentFormat.UNKNOWN: [],
        }
        return extensions_map[self]


class DocumentType(Enum):
    """High-level document type classification."""

    WORD_PROCESSING = auto()  # DOC, DOCX
    SPREADSHEET = auto()      # XLS, XLSX
    PRESENTATION = auto()     # PPT, PPTX
    PDF = auto()              # PDF
    TEXT = auto()             # TXT, MD
    WEB = auto()              # HTML
    UNKNOWN = auto()          # Unknown

    @classmethod
    def from_format(cls, fmt: DocumentFormat) -> DocumentType:
        """Get DocumentType from DocumentFormat."""
        mapping = {
            DocumentFormat.DOC: cls.WORD_PROCESSING,
            DocumentFormat.DOCX: cls.WORD_PROCESSING,
            DocumentFormat.XLS: cls.SPREADSHEET,
            DocumentFormat.XLSX: cls.SPREADSHEET,
            DocumentFormat.PPT: cls.PRESENTATION,
            DocumentFormat.PPTX: cls.PRESENTATION,
            DocumentFormat.PDF: cls.PDF,
            DocumentFormat.TXT: cls.TEXT,
            DocumentFormat.MD: cls.TEXT,
            DocumentFormat.HTML: cls.WEB,
        }
        return mapping.get(fmt, cls.UNKNOWN)


class ContentType(Enum):
    """Content type classification within documents."""

    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    CHART = "chart"
    HYPERLINK = "hyperlink"
    METADATA = "metadata"
    STRUCTURE = "structure"


@dataclass(frozen=True)
class DocumentMetadata:
    """
    Immutable metadata for a document.

    This class stores all metadata associated with a document, including
    file information, creation/modification times, and custom properties.

    Attributes:
        filename: Original filename
        file_size: Size in bytes
        created_at: Creation timestamp
        modified_at: Last modification timestamp
        author: Document author (if available)
        title: Document title (if available)
        description: Document description
        tags: List of tags/keywords
        custom_properties: Additional custom metadata
        source: Source identifier (e.g., upload, import, api)
        encoding: Text encoding (for text-based formats)

    Example:
        >>> metadata = DocumentMetadata(
        ...     filename="report.pdf",
        ...     file_size=1024000,
        ...     author="John Doe",
        ...     tags=["report", "2024"]
        ... )
    """

    filename: str = "unknown"
    file_size: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    modified_at: datetime = field(default_factory=datetime.utcnow)
    author: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    custom_properties: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    encoding: str = "utf-8"

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "filename": self.filename,
            "file_size": self.file_size,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "author": self.author,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "custom_properties": self.custom_properties,
            "source": self.source,
            "encoding": self.encoding,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DocumentMetadata:
        """Create metadata from dictionary."""
        return cls(
            filename=data.get("filename", "unknown"),
            file_size=data.get("file_size", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            modified_at=datetime.fromisoformat(data["modified_at"]) if "modified_at" in data else datetime.utcnow(),
            author=data.get("author"),
            title=data.get("title"),
            description=data.get("description"),
            tags=data.get("tags", []),
            custom_properties=data.get("custom_properties", {}),
            source=data.get("source", "unknown"),
            encoding=data.get("encoding", "utf-8"),
        )


@dataclass(frozen=True)
class DocumentContent:
    """
    Immutable content representation of a document.

    This class represents the extracted content from a document in a
    structured format that is independent of the original file format.

    Attributes:
        text: Extracted plain text content
        structured_content: Hierarchical content structure
        images: List of embedded images
        tables: List of extracted tables
        hyperlinks: List of hyperlinks
        metadata: Extracted document metadata

    Example:
        >>> content = DocumentContent(
        ...     text="Hello World",
        ...     structured_content={"paragraphs": [...]},
        ...     tables=[{"headers": [...], "rows": [...]}]
        ... )
    """

    text: str = ""
    structured_content: Dict[str, Any] = field(default_factory=dict)
    images: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    hyperlinks: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_text_chunks(self, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """
        Split text content into overlapping chunks.

        Args:
            chunk_size: Maximum size of each chunk
            overlap: Number of characters to overlap between chunks

        Returns:
            List of text chunks
        """
        if not self.text:
            return []

        chunks = []
        start = 0
        text_len = len(self.text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(self.text[start:end])
            start = end - overlap if end < text_len else text_len

        return chunks

    def to_dict(self) -> Dict[str, Any]:
        """Convert content to dictionary."""
        return {
            "text": self.text,
            "structured_content": self.structured_content,
            "images": self.images,
            "tables": self.tables,
            "hyperlinks": self.hyperlinks,
            "metadata": self.metadata,
        }


@dataclass
class BaseDocument:
    """
    Base document class representing a document in the DocMCP system.

    This is the core abstraction for all documents. It provides a unified
    interface regardless of the underlying file format.

    Attributes:
        id: Unique document identifier (UUID)
        format: Document format enum
        content: Raw binary content (optional, for lazy loading)
        extracted_content: Extracted and parsed content
        metadata: Document metadata
        checksum: Content checksum for integrity verification

    Example:
        >>> doc = BaseDocument.from_bytes(
        ...     content=b"...",
        ...     filename="example.pdf",
        ...     format=DocumentFormat.PDF
        ... )
        >>> print(doc.id)
        >>> print(doc.format)
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    format: DocumentFormat = DocumentFormat.UNKNOWN
    content: Optional[bytes] = None
    extracted_content: Optional[DocumentContent] = None
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    checksum: Optional[str] = None

    def __post_init__(self) -> None:
        """Post-initialization to compute checksum if content is provided."""
        if self.content is not None and self.checksum is None:
            object.__setattr__(self, "checksum", self._compute_checksum(self.content))

    @staticmethod
    def _compute_checksum(content: bytes) -> str:
        """Compute SHA-256 checksum of content."""
        return hashlib.sha256(content).hexdigest()

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        filename: str,
        format: Optional[DocumentFormat] = None,
        metadata: Optional[DocumentMetadata] = None,
    ) -> BaseDocument:
        """
        Create a document from raw bytes.

        Args:
            content: Raw binary content
            filename: Original filename
            format: Document format (auto-detected from filename if not provided)
            metadata: Optional metadata

        Returns:
            BaseDocument instance
        """
        if format is None:
            ext = Path(filename).suffix
            format = DocumentFormat.from_extension(ext)

        doc_metadata = metadata or DocumentMetadata(
            filename=filename,
            file_size=len(content),
        )

        return cls(
            format=format,
            content=content,
            metadata=doc_metadata,
        )

    @classmethod
    def from_file(
        cls,
        file_path: Union[str, Path],
        format: Optional[DocumentFormat] = None,
        metadata: Optional[DocumentMetadata] = None,
    ) -> BaseDocument:
        """
        Create a document from a file path.

        Args:
            file_path: Path to the file
            format: Document format (auto-detected from extension if not provided)
            metadata: Optional metadata

        Returns:
            BaseDocument instance
        """
        path = Path(file_path)
        content = path.read_bytes()

        if format is None:
            format = DocumentFormat.from_extension(path.suffix)

        doc_metadata = metadata or DocumentMetadata(
            filename=path.name,
            file_size=len(content),
        )

        return cls(
            format=format,
            content=content,
            metadata=doc_metadata,
        )

    @property
    def document_type(self) -> DocumentType:
        """Get the high-level document type."""
        return DocumentType.from_format(self.format)

    @property
    def has_content(self) -> bool:
        """Check if document has raw content loaded."""
        return self.content is not None

    @property
    def has_extracted_content(self) -> bool:
        """Check if document has extracted content."""
        return self.extracted_content is not None

    def verify_checksum(self) -> bool:
        """
        Verify content integrity using checksum.

        Returns:
            True if checksum matches, False otherwise
        """
        if self.content is None or self.checksum is None:
            return False
        return self._compute_checksum(self.content) == self.checksum

    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary (excluding binary content)."""
        return {
            "id": self.id,
            "format": self.format.value,
            "document_type": self.document_type.name,
            "has_content": self.has_content,
            "has_extracted_content": self.has_extracted_content,
            "metadata": self.metadata.to_dict(),
            "checksum": self.checksum,
            "extracted_content": self.extracted_content.to_dict() if self.extracted_content else None,
        }

    def __repr__(self) -> str:
        return (
            f"BaseDocument("
            f"id={self.id[:8]}..., "
            f"format={self.format.value}, "
            f"type={self.document_type.name}, "
            f"size={self.metadata.file_size}"
            f")"
        )
