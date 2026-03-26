"""
文档处理器基类模块

提供所有文档处理器的通用功能和接口定义。
"""

import logging
import os
import tempfile
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple, Union, Generator, Callable

from ..document import (
    BaseDocument,
    DocumentMetadata,
    DocumentFormat,
    DocumentContent,
)

# 配置日志
logger = logging.getLogger(__name__)

# 类型定义
ProgressCallback = Callable[[int, int, str], None]
ExtractedContent = Dict[str, Any]


def default_progress_callback(current: int, total: int, message: str = "") -> None:
    """默认进度回调函数"""
    pass


class BaseDocumentHandler(ABC):
    """
    文档处理器基类
    
    提供所有文档处理器的通用功能实现。
    """
    
    def __init__(self):
        """初始化处理器"""
        self._logger = logging.getLogger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def supported_formats(self) -> List[DocumentFormat]:
        """返回支持的文档格式列表"""
        pass
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """返回支持的文件扩展名列表"""
        pass
    
    def can_handle(self, file_path: Union[str, Path]) -> bool:
        """
        检查是否能处理指定文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否能处理
        """
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_extensions
    
    @abstractmethod
    async def extract_text(
        self,
        file_path: Union[str, Path],
        **kwargs
    ) -> str:
        """
        提取文档文本内容
        
        Args:
            file_path: 文件路径
            **kwargs: 额外参数
            
        Returns:
            提取的文本内容
        """
        pass
    
    @abstractmethod
    async def extract_metadata(
        self,
        file_path: Union[str, Path],
        **kwargs
    ) -> DocumentMetadata:
        """
        提取文档元数据
        
        Args:
            file_path: 文件路径
            **kwargs: 额外参数
            
        Returns:
            文档元数据
        """
        pass
    
    async def extract_content(
        self,
        file_path: Union[str, Path],
        **kwargs
    ) -> ExtractedContent:
        """
        提取文档完整内容
        
        Args:
            file_path: 文件路径
            **kwargs: 额外参数
            
        Returns:
            提取的内容字典
        """
        return {
            "text": await self.extract_text(file_path, **kwargs),
            "metadata": await self.extract_metadata(file_path, **kwargs),
        }


class BatchProcessor:
    """
    批量处理器
    
    用于批量处理多个文档。
    """
    
    def __init__(
        self,
        handler: BaseDocumentHandler,
        progress_callback: Optional[ProgressCallback] = None
    ):
        """
        初始化批量处理器
        
        Args:
            handler: 文档处理器
            progress_callback: 进度回调函数
        """
        self._handler = handler
        self._progress_callback = progress_callback or default_progress_callback
    
    async def process_batch(
        self,
        file_paths: List[Union[str, Path]],
        operation: str = "extract_text",
        **kwargs
    ) -> List[Any]:
        """
        批量处理文件
        
        Args:
            file_paths: 文件路径列表
            operation: 操作类型
            **kwargs: 额外参数
            
        Returns:
            处理结果列表
        """
        results = []
        total = len(file_paths)
        
        for i, file_path in enumerate(file_paths):
            try:
                self._progress_callback(i, total, f"Processing {file_path}")
                
                if operation == "extract_text":
                    result = await self._handler.extract_text(file_path, **kwargs)
                elif operation == "extract_metadata":
                    result = await self._handler.extract_metadata(file_path, **kwargs)
                elif operation == "extract_content":
                    result = await self._handler.extract_content(file_path, **kwargs)
                else:
                    raise ValueError(f"Unknown operation: {operation}")
                
                results.append(result)
            except Exception as e:
                self._logger.error(f"Error processing {file_path}: {e}")
                results.append(None)
        
        self._progress_callback(total, total, "Batch processing complete")
        return results
