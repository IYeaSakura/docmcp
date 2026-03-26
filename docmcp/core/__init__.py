"""
Core module for DocMCP document processing engine.

This module provides the fundamental abstractions and implementations
for document processing, including:
    - Document abstraction and metadata
    - Processing engine with async support
    - Pipeline architecture for extensible processing
    - Task scheduling and queue management

Example:
    >>> from docmcp.core import ProcessingEngine, DocumentFormat
    >>> engine = ProcessingEngine(max_workers=10)
    >>> doc = BaseDocument(
    ...     format=DocumentFormat.PDF,
    ...     content=b"...",
    ...     metadata=DocumentMetadata(filename="example.pdf")
    ... )
    >>> result = await engine.process(doc)
"""

from __future__ import annotations

from docmcp.core.document import (
    BaseDocument,
    DocumentMetadata,
    DocumentContent,
    DocumentFormat,
    DocumentType,
    ContentType,
)
from docmcp.core.engine import (
    ProcessingEngine,
    ProcessingContext,
    ProcessingResult,
    ProcessingStatus,
    ValidationResult,
    ValidationStatus,
)
from docmcp.core.pipeline import (
    Pipeline,
    PipelineStage,
    PipelineContext,
    PipelineResult,
)

try:
    from docmcp.core.handlers import (
        WordHandler,
        ExcelHandler,
        PPTHandler,
        PDFHandler,
    )
    HANDLERS_AVAILABLE = True
except ImportError:
    HANDLERS_AVAILABLE = False

__all__ = [
    # Document classes
    "BaseDocument",
    "DocumentMetadata",
    "DocumentContent",
    "DocumentFormat",
    "DocumentType",
    "ContentType",
    # Engine classes
    "ProcessingEngine",
    "ProcessingContext",
    "ProcessingResult",
    "ProcessingStatus",
    "ValidationResult",
    "ValidationStatus",
    # Pipeline classes
    "Pipeline",
    "PipelineStage",
    "PipelineContext",
    "PipelineResult",
    # Handlers (optional)
    "WordHandler",
    "ExcelHandler",
    "PPTHandler",
    "PDFHandler",
]
