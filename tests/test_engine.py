"""
文档处理引擎单元测试
"""

import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from docmcp.core.engine import ProcessingEngine as DocumentEngine, get_engine, reset_engine
from docmcp.core.document import DocumentType


class TestDocumentEngine(unittest.TestCase):
    """测试文档处理引擎"""

    def setUp(self):
        """测试前准备"""
        reset_engine()
        self.engine = DocumentEngine()

    def test_initialization(self):
        """测试引擎初始化"""
        self.assertIsNotNone(self.engine)
        supported_types = self.engine.get_supported_types()
        self.assertGreater(len(supported_types), 0)

    def test_get_supported_extensions(self):
        """测试获取支持的扩展名"""
        extensions = self.engine.get_supported_extensions()
        self.assertIn('.docx', extensions)
        self.assertIn('.pdf', extensions)
        self.assertIn('.xlsx', extensions)

    def test_can_handle(self):
        """测试文件处理能力检查"""
        # 注意：这些测试需要实际文件才能完全测试
        # 这里只测试接口
        pass

    def test_get_handler(self):
        """测试获取处理器"""
        handler = self.engine.get_handler_by_type(DocumentType.DOCX)
        self.assertIsNotNone(handler)

        handler = self.engine.get_handler_by_type(DocumentType.PDF)
        self.assertIsNotNone(handler)


class TestGlobalEngine(unittest.TestCase):
    """测试全局引擎实例"""

    def test_get_engine(self):
        """测试获取全局引擎"""
        engine1 = get_engine()
        engine2 = get_engine()
        self.assertIs(engine1, engine2)

    def test_reset_engine(self):
        """测试重置引擎"""
        engine1 = get_engine()
        reset_engine()
        engine2 = get_engine()
        self.assertIsNot(engine1, engine2)


if __name__ == '__main__':
    unittest.main()
