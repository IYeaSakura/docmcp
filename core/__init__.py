"""
DocMCP 文档处理核心模块

提供统一的文档处理接口，支持多种文档格式的读取、写入、转换和提取。

支持的格式：
- Word: .doc, .docx
- Excel: .xls, .xlsx
- PowerPoint: .ppt, .pptx
- PDF: .pdf

Example:
    >>> from docmcp.core import DocumentEngine
    >>> engine = DocumentEngine()
    >>> text = engine.extract_text("document.docx")
    >>> results = engine.batch_process(["file1.docx", "file2.pdf"], "extract_text")
"""

from .document import (
    DocumentBase,
    DocumentHandler,
    DocumentMetadata,
    DocumentType,
    ExtractedContent,
    ProgressCallback,
    default_progress_callback,
)

from .engine import (
    DocumentEngine,
    get_engine,
    extract_text,
    extract_content,
    extract_metadata,
    convert_document,
    batch_extract_text,
)

from .utils import (
    FileTypeDetector,
    EncodingDetector,
    TempFileManager,
    detect_file_type,
    detect_encoding,
    read_text_with_encoding,
    format_file_size,
    safe_filename,
    temp_file_context,
    temp_dir_context,
)

from .handlers import (
    # 基类
    BaseDocument,
    BaseDocumentHandler,
    BatchProcessor,
    
    # Word
    WordDocument,
    WordHandler,
    extract_text_from_word,
    extract_tables_from_word,
    
    # Excel
    ExcelDocument,
    ExcelHandler,
    read_excel_to_dataframe,
    extract_tables_from_excel,
    
    # PowerPoint
    PowerPointDocument,
    PowerPointHandler,
    extract_text_from_ppt,
    extract_images_from_ppt,
    
    # PDF
    PDFDocument,
    PDFHandler,
    extract_text_from_pdf,
    extract_tables_from_pdf,
    merge_pdf_files,
)

__version__ = "1.0.0"

__all__ = [
    # 版本
    '__version__',
    
    # 文档抽象
    'DocumentBase',
    'DocumentHandler',
    'DocumentMetadata',
    'DocumentType',
    'ExtractedContent',
    'ProgressCallback',
    'default_progress_callback',
    
    # 引擎
    'DocumentEngine',
    'get_engine',
    'extract_text',
    'extract_content',
    'extract_metadata',
    'convert_document',
    'batch_extract_text',
    
    # 工具
    'FileTypeDetector',
    'EncodingDetector',
    'TempFileManager',
    'detect_file_type',
    'detect_encoding',
    'read_text_with_encoding',
    'format_file_size',
    'safe_filename',
    'temp_file_context',
    'temp_dir_context',
    
    # 处理器基类
    'BaseDocument',
    'BaseDocumentHandler',
    'BatchProcessor',
    
    # Word
    'WordDocument',
    'WordHandler',
    'extract_text_from_word',
    'extract_tables_from_word',
    
    # Excel
    'ExcelDocument',
    'ExcelHandler',
    'read_excel_to_dataframe',
    'extract_tables_from_excel',
    
    # PowerPoint
    'PowerPointDocument',
    'PowerPointHandler',
    'extract_text_from_ppt',
    'extract_images_from_ppt',
    
    # PDF
    'PDFDocument',
    'PDFHandler',
    'extract_text_from_pdf',
    'extract_tables_from_pdf',
    'merge_pdf_files',
]
