"""
文档处理核心模块单元测试
"""

import unittest
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from docmcp.core.document import (
    DocumentMetadata,
    DocumentType,
    DocumentContent as ExtractedContent,
)


class TestDocumentType(unittest.TestCase):
    """测试文档类型枚举"""

    def test_from_extension(self):
        """测试从扩展名获取文档类型"""
        self.assertEqual(DocumentType.from_extension('.docx'), DocumentType.DOCX)
        self.assertEqual(DocumentType.from_extension('docx'), DocumentType.DOCX)
        self.assertEqual(DocumentType.from_extension('.xlsx'), DocumentType.XLSX)
        self.assertEqual(DocumentType.from_extension('.pdf'), DocumentType.PDF)
        self.assertEqual(DocumentType.from_extension('.unknown'), DocumentType.UNKNOWN)


class TestDocumentMetadata(unittest.TestCase):
    """测试文档元数据类"""

    def test_creation(self):
        """测试创建元数据对象"""
        metadata = DocumentMetadata(
            title="Test Document",
            author="Test Author",
            file_size=1024
        )

        self.assertEqual(metadata.title, "Test Document")
        self.assertEqual(metadata.author, "Test Author")
        self.assertEqual(metadata.file_size, 1024)

    def test_to_dict(self):
        """测试转换为字典"""
        now = datetime.now()
        metadata = DocumentMetadata(
            title="Test",
            created=now,
            file_size=1024
        )

        data = metadata.to_dict()
        self.assertEqual(data['title'], "Test")
        self.assertEqual(data['file_size'], 1024)
        self.assertIsInstance(data['created'], str)

    def test_from_dict(self):
        """测试从字典创建"""
        now = datetime.now().isoformat()
        data = {
            'title': 'Test',
            'created': now,
            'file_size': 1024,
            'custom_properties': {'key': 'value'}
        }

        metadata = DocumentMetadata.from_dict(data)
        self.assertEqual(metadata.title, 'Test')
        self.assertEqual(metadata.file_size, 1024)
        self.assertIsInstance(metadata.created, datetime)


class TestExtractedContent(unittest.TestCase):
    """测试提取内容类"""

    def test_creation(self):
        """测试创建内容对象"""
        content = ExtractedContent(
            text="Test text",
            paragraphs=["Para 1", "Para 2"],
            tables=[[["A", "B"], ["C", "D"]]]
        )

        self.assertEqual(content.text, "Test text")
        self.assertEqual(len(content.paragraphs), 2)
        self.assertEqual(len(content.tables), 1)

    def test_to_dict(self):
        """测试转换为字典"""
        content = ExtractedContent(
            text="Test",
            paragraphs=["Para 1"],
            tables=[[["A", "B"]]]
        )

        data = content.to_dict()
        self.assertEqual(data['text'], "Test")
        self.assertEqual(data['paragraphs'], ["Para 1"])
        self.assertEqual(data['tables'], [[["A", "B"]]])


if __name__ == '__main__':
    unittest.main()
