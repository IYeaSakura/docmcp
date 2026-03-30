"""
工具函数模块单元测试
"""

import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from docmcp.core.utils import (
    FileTypeDetector,
    EncodingDetector,
    TempFileManager,
    format_file_size,
    safe_filename,
)
from docmcp.core.document import DocumentType


class TestFileTypeDetector(unittest.TestCase):
    """测试文件类型检测器"""

    def test_detect_by_extension(self):
        """测试通过扩展名检测"""
        self.assertEqual(
            FileTypeDetector.detect_by_extension("test.docx"),
            DocumentType.DOCX
        )
        self.assertEqual(
            FileTypeDetector.detect_by_extension("test.pdf"),
            DocumentType.PDF
        )


class TestEncodingDetector(unittest.TestCase):
    """测试编码检测器"""

    def test_detect_utf8(self):
        """测试检测UTF-8编码"""
        text = "Hello, 世界!"
        data = text.encode('utf-8')
        encoding, confidence = EncodingDetector.detect(data)
        self.assertEqual(encoding.lower().replace('-', ''), 'utf8')


class TestTempFileManager(unittest.TestCase):
    """测试临时文件管理器"""

    def test_create_temp_file(self):
        """测试创建临时文件"""
        with TempFileManager() as manager:
            temp_file = manager.create_temp_file(suffix='.txt', content=b'test')
            self.assertTrue(temp_file.exists())
            self.assertEqual(temp_file.read_bytes(), b'test')

    def test_create_temp_dir(self):
        """测试创建临时目录"""
        with TempFileManager() as manager:
            temp_dir = manager.create_temp_dir()
            self.assertTrue(temp_dir.exists())
            self.assertTrue(temp_dir.is_dir())


class TestUtilityFunctions(unittest.TestCase):
    """测试工具函数"""

    def test_format_file_size(self):
        """测试格式化文件大小"""
        self.assertIn("B", format_file_size(100))
        self.assertIn("KB", format_file_size(1024))
        self.assertIn("MB", format_file_size(1024 * 1024))

    def test_safe_filename(self):
        """测试安全文件名"""
        self.assertEqual(safe_filename("test<file>.txt"), "test_file_.txt")
        self.assertEqual(safe_filename("test:file.txt"), "test_file.txt")


if __name__ == '__main__':
    unittest.main()
