"""
内置Skills模块

提供文档处理相关的内置Skills。
"""

from .extract_text import ExtractTextSkill
from .convert_format import ConvertFormatSkill
from .analyze_document import AnalyzeDocumentSkill
from .merge_documents import MergeDocumentsSkill

__all__ = [
    "ExtractTextSkill",
    "ConvertFormatSkill",
    "AnalyzeDocumentSkill",
    "MergeDocumentsSkill",
]
