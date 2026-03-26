"""
文档处理器模块

提供各种文档格式的处理器实现。
"""

from .base import (
    BaseDocument,
    BaseDocumentHandler,
    BatchProcessor,
    create_temp_file,
    create_temp_directory,
)

from .word_handler import (
    WordDocument,
    WordHandler,
    extract_text_from_word,
    extract_tables_from_word,
)

from .excel_handler import (
    ExcelDocument,
    ExcelHandler,
    read_excel_to_dataframe,
    extract_tables_from_excel,
)

from .ppt_handler import (
    PowerPointDocument,
    PowerPointHandler,
    extract_text_from_ppt,
    extract_images_from_ppt,
)

from .pdf_handler import (
    PDFDocument,
    PDFHandler,
    extract_text_from_pdf,
    extract_tables_from_pdf,
    merge_pdf_files,
)

__all__ = [
    # 基类
    'BaseDocument',
    'BaseDocumentHandler',
    'BatchProcessor',
    'create_temp_file',
    'create_temp_directory',
    
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
