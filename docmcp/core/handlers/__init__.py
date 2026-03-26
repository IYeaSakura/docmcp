"""
文档处理器模块

提供各种文档格式的处理器实现。
"""

from .base import (
    BaseDocumentHandler,
    BatchProcessor,
    ProgressCallback,
    ExtractedContent,
    default_progress_callback,
)

try:
    from .word_handler import WordHandler
except ImportError:
    WordHandler = None

try:
    from .excel_handler import ExcelHandler
except ImportError:
    ExcelHandler = None

try:
    from .ppt_handler import PPTHandler
except ImportError:
    PPTHandler = None

try:
    from .pdf_handler import PDFHandler
except ImportError:
    PDFHandler = None

__all__ = [
    'BaseDocumentHandler',
    'BatchProcessor',
    'ProgressCallback',
    'ExtractedContent',
    'default_progress_callback',
    'WordHandler',
    'ExcelHandler',
    'PPTHandler',
    'PDFHandler',
]
