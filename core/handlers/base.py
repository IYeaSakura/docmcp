"""
文档处理器基类模块

提供所有文档处理器的通用功能和接口定义。
"""

import logging
import os
import tempfile
from abc import abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple, Union, Generator

from ..document import (
    DocumentBase,
    DocumentHandler,
    DocumentMetadata,
    DocumentType,
    ExtractedContent,
    ProgressCallback,
    default_progress_callback,
)

# 配置日志
logger = logging.getLogger(__name__)


class BaseDocumentHandler(DocumentHandler):
    """
    文档处理器基类
    
    提供所有文档处理器的通用功能实现。
    """
    
    def __init__(self):
        """初始化处理器"""
        self._logger = logging.getLogger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def supported_types(self) -> List[DocumentType]:
        """返回支持的文档类型列表"""
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
            是否能处理该文件
        """
        path = Path(file_path)
        if not path.exists():
            return False
        return path.suffix.lower() in self.supported_extensions
    
    def validate_file(self, file_path: Union[str, Path]) -> None:
        """
        验证文件是否有效
        
        Args:
            file_path: 文件路径
            
        Raises:
            FileNotFoundError: 文件不存在
            PermissionError: 没有读取权限
            ValueError: 文件扩展名不支持
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        
        if not path.is_file():
            raise ValueError(f"路径不是文件: {path}")
        
        if not os.access(path, os.R_OK):
            raise PermissionError(f"没有读取权限: {path}")
        
        if path.suffix.lower() not in self.supported_extensions:
            raise ValueError(
                f"不支持的文件扩展名: {path.suffix}. "
                f"支持的扩展名: {', '.join(self.supported_extensions)}"
            )
    
    @abstractmethod
    def create_document(
        self,
        file_path: Optional[Union[str, Path]] = None,
        file_stream: Optional[BinaryIO] = None
    ) -> DocumentBase:
        """
        创建文档对象
        
        Args:
            file_path: 文件路径
            file_stream: 文件流
            
        Returns:
            文档对象
        """
        pass


class BaseDocument(DocumentBase):
    """
    文档对象基类
    
    提供所有文档对象的通用功能实现。
    """
    
    # 大文件阈值 (100MB)
    LARGE_FILE_THRESHOLD = 100 * 1024 * 1024
    
    def __init__(
        self,
        file_path: Optional[Union[str, Path]] = None,
        file_stream: Optional[BinaryIO] = None,
        document_type: Optional[DocumentType] = None
    ):
        """
        初始化文档对象
        
        Args:
            file_path: 文档文件路径
            file_stream: 文档文件流
            document_type: 文档类型
        """
        super().__init__(file_path, file_stream, document_type)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._internal_doc: Any = None
    
    def is_large_file(self) -> bool:
        """
        检查是否为大文件
        
        Returns:
            是否为大文件
        """
        return self.get_file_size() > self.LARGE_FILE_THRESHOLD
    
    def _get_file_stream(self) -> BinaryIO:
        """
        获取文件流
        
        Returns:
            文件流对象
            
        Raises:
            ValueError: 没有可用的文件源
        """
        if self._file_stream:
            self._file_stream.seek(0)
            return self._file_stream
        
        if self._file_path and self._file_path.exists():
            return open(self._file_path, 'rb')
        
        raise ValueError("没有可用的文件源")
    
    @contextmanager
    def _open_file(self) -> Generator[BinaryIO, None, None]:
        """
        上下文管理器：打开文件
        
        Yields:
            文件流对象
        """
        if self._file_stream:
            self._file_stream.seek(0)
            yield self._file_stream
        elif self._file_path and self._file_path.exists():
            with open(self._file_path, 'rb') as f:
                yield f
        else:
            raise ValueError("没有可用的文件源")
    
    def _safe_extract(
        self,
        extract_func,
        default_value: Any = None,
        error_message: str = "提取失败"
    ) -> Any:
        """
        安全地执行提取操作
        
        Args:
            extract_func: 提取函数
            default_value: 失败时的默认值
            error_message: 错误消息
            
        Returns:
            提取结果或默认值
        """
        try:
            return extract_func()
        except Exception as e:
            self._logger.warning(f"{error_message}: {e}")
            return default_value
    
    def _update_metadata_from_file(self) -> None:
        """从文件系统更新元数据"""
        if self._file_path and self._file_path.exists():
            stat = self._file_path.stat()
            self._metadata.file_size = stat.st_size
            self._metadata.file_path = self._file_path
            self._metadata.file_name = self._file_path.name
            self._metadata.file_extension = self._file_path.suffix
            
            # 尝试获取创建和修改时间
            try:
                import datetime
                self._metadata.created = datetime.datetime.fromtimestamp(
                    stat.st_ctime
                )
                self._metadata.modified = datetime.datetime.fromtimestamp(
                    stat.st_mtime
                )
            except Exception:
                pass
    
    @abstractmethod
    def load(self, **kwargs) -> "BaseDocument":
        """加载文档"""
        pass
    
    @abstractmethod
    def extract_text(self, **kwargs) -> str:
        """提取纯文本内容"""
        pass
    
    @abstractmethod
    def extract_content(self, **kwargs) -> ExtractedContent:
        """提取完整内容"""
        pass
    
    @abstractmethod
    def extract_metadata(self, **kwargs) -> DocumentMetadata:
        """提取文档元数据"""
        pass
    
    @abstractmethod
    def save(self, output_path: Union[str, Path], **kwargs) -> "BaseDocument":
        """保存文档"""
        pass
    
    @abstractmethod
    def convert_to(
        self,
        target_type: DocumentType,
        output_path: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> Union[str, Path, bytes]:
        """转换文档格式"""
        pass
    
    def close(self) -> None:
        """关闭文档，释放资源"""
        if self._file_stream:
            try:
                self._file_stream.close()
            except Exception as e:
                self._logger.warning(f"关闭文件流失败: {e}")
            self._file_stream = None
        
        self._internal_doc = None
        self._is_loaded = False
    
    def __del__(self):
        """析构函数"""
        try:
            self.close()
        except Exception:
            pass


class BatchProcessor:
    """
    批处理器
    
    用于批量处理文档的辅助类。
    """
    
    def __init__(
        self,
        handler: BaseDocumentHandler,
        progress_callback: Optional[ProgressCallback] = None
    ):
        """
        初始化批处理器
        
        Args:
            handler: 文档处理器
            progress_callback: 进度回调函数
        """
        self._handler = handler
        self._progress_callback = progress_callback or default_progress_callback
        self._logger = logging.getLogger(self.__class__.__name__)
    
    def process_files(
        self,
        file_paths: List[Union[str, Path]],
        operation: str = "extract_text",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        批量处理文件
        
        Args:
            file_paths: 文件路径列表
            operation: 操作类型 (extract_text, extract_content, extract_metadata)
            **kwargs: 操作参数
            
        Returns:
            处理结果列表
        """
        results = []
        total = len(file_paths)
        
        for i, file_path in enumerate(file_paths):
            path = Path(file_path)
            self._progress_callback(i, total, f"处理: {path.name}")
            
            result = {
                'file_path': str(path),
                'file_name': path.name,
                'success': False,
                'data': None,
                'error': None
            }
            
            try:
                if not self._handler.can_handle(path):
                    result['error'] = "不支持的文件类型"
                    results.append(result)
                    continue
                
                doc = self._handler.create_document(file_path=path)
                
                with doc:
                    if operation == "extract_text":
                        result['data'] = doc.extract_text(**kwargs)
                    elif operation == "extract_content":
                        result['data'] = doc.extract_content(**kwargs).to_dict()
                    elif operation == "extract_metadata":
                        result['data'] = doc.extract_metadata(**kwargs).to_dict()
                    else:
                        result['error'] = f"未知的操作类型: {operation}"
                        results.append(result)
                        continue
                    
                    result['success'] = True
                    
            except Exception as e:
                self._logger.error(f"处理文件失败 {path}: {e}")
                result['error'] = str(e)
            
            results.append(result)
        
        self._progress_callback(total, total, "完成")
        return results
    
    def process_directory(
        self,
        directory: Union[str, Path],
        recursive: bool = False,
        operation: str = "extract_text",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        批量处理目录中的文件
        
        Args:
            directory: 目录路径
            recursive: 是否递归处理子目录
            operation: 操作类型
            **kwargs: 操作参数
            
        Returns:
            处理结果列表
        """
        dir_path = Path(directory)
        
        if not dir_path.exists():
            raise FileNotFoundError(f"目录不存在: {dir_path}")
        
        if not dir_path.is_dir():
            raise ValueError(f"路径不是目录: {dir_path}")
        
        # 收集文件
        file_paths = []
        pattern = "**/*" if recursive else "*"
        
        for path in dir_path.glob(pattern):
            if path.is_file() and self._handler.can_handle(path):
                file_paths.append(path)
        
        return self.process_files(file_paths, operation, **kwargs)


def create_temp_file(
    suffix: str = "",
    prefix: str = "docmcp_",
    delete: bool = False
) -> Path:
    """
    创建临时文件
    
    Args:
        suffix: 文件后缀
        prefix: 文件前缀
        delete: 是否在关闭时删除
        
    Returns:
        临时文件路径
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    
    if delete:
        # 注册删除回调
        import atexit
        atexit.register(lambda: os.path.exists(path) and os.remove(path))
    
    return Path(path)


def create_temp_directory(
    suffix: str = "",
    prefix: str = "docmcp_",
    delete: bool = False
) -> Path:
    """
    创建临时目录
    
    Args:
        suffix: 目录后缀
        prefix: 目录前缀
        delete: 是否在退出时删除
        
    Returns:
        临时目录路径
    """
    path = tempfile.mkdtemp(suffix=suffix, prefix=prefix)
    
    if delete:
        import atexit
        import shutil
        atexit.register(lambda: os.path.exists(path) and shutil.rmtree(path))
    
    return Path(path)
