"""
文档处理引擎模块

提供统一的文档处理接口，支持多种文档格式的读取、写入、转换和批量处理。
"""

import asyncio
import concurrent.futures
import logging
from pathlib import Path
from typing import (
    Any, BinaryIO, Callable, Dict, List, Optional, 
    Tuple, Type, Union, AsyncIterator, Iterator
)

from .document import (
    DocumentBase,
    DocumentHandler,
    DocumentMetadata,
    DocumentType,
    ExtractedContent,
    ProgressCallback,
    default_progress_callback,
)
from .utils import (
    FileTypeDetector,
    TempFileManager,
    detect_file_type,
    format_file_size,
)

# 配置日志
logger = logging.getLogger(__name__)

# 导入所有处理器
from .handlers.word_handler import WordHandler, WordDocument
from .handlers.excel_handler import ExcelHandler, ExcelDocument
from .handlers.ppt_handler import PowerPointHandler, PowerPointDocument
from .handlers.pdf_handler import PDFHandler, PDFDocument


class DocumentEngine:
    """
    文档处理引擎
    
    统一的文档处理接口，支持多种文档格式的处理。
    
    Example:
        >>> engine = DocumentEngine()
        >>> text = engine.extract_text("document.docx")
        >>> results = engine.batch_process(["file1.docx", "file2.pdf"], "extract_text")
    """
    
    def __init__(self):
        """初始化文档处理引擎"""
        self._handlers: Dict[DocumentType, DocumentHandler] = {}
        self._temp_manager = TempFileManager()
        self._logger = logging.getLogger(self.__class__.__name__)
        
        # 注册默认处理器
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """注册默认的文档处理器"""
        # Word处理器
        try:
            self.register_handler(WordHandler())
            self._logger.debug("注册Word处理器")
        except Exception as e:
            self._logger.warning(f"注册Word处理器失败: {e}")
        
        # Excel处理器
        try:
            self.register_handler(ExcelHandler())
            self._logger.debug("注册Excel处理器")
        except Exception as e:
            self._logger.warning(f"注册Excel处理器失败: {e}")
        
        # PowerPoint处理器
        try:
            self.register_handler(PowerPointHandler())
            self._logger.debug("注册PowerPoint处理器")
        except Exception as e:
            self._logger.warning(f"注册PowerPoint处理器失败: {e}")
        
        # PDF处理器
        try:
            self.register_handler(PDFHandler())
            self._logger.debug("注册PDF处理器")
        except Exception as e:
            self._logger.warning(f"注册PDF处理器失败: {e}")
    
    def register_handler(self, handler: DocumentHandler) -> "DocumentEngine":
        """
        注册文档处理器
        
        Args:
            handler: 文档处理器实例
            
        Returns:
            self: 支持链式调用
        """
        for doc_type in handler.supported_types:
            self._handlers[doc_type] = handler
            self._logger.debug(f"注册处理器 {handler.__class__.__name__} 用于类型 {doc_type}")
        return self
    
    def unregister_handler(self, doc_type: DocumentType) -> "DocumentEngine":
        """
        注销文档处理器
        
        Args:
            doc_type: 文档类型
            
        Returns:
            self: 支持链式调用
        """
        if doc_type in self._handlers:
            del self._handlers[doc_type]
        return self
    
    def get_handler(self, file_path: Union[str, Path]) -> Optional[DocumentHandler]:
        """
        获取适合处理指定文件的处理器
        
        Args:
            file_path: 文件路径
            
        Returns:
            文档处理器，如果没有找到则返回None
        """
        doc_type = detect_file_type(file_path)
        return self._handlers.get(doc_type)
    
    def get_handler_by_type(self, doc_type: DocumentType) -> Optional[DocumentHandler]:
        """
        根据文档类型获取处理器
        
        Args:
            doc_type: 文档类型
            
        Returns:
            文档处理器，如果没有找到则返回None
        """
        return self._handlers.get(doc_type)
    
    def can_handle(self, file_path: Union[str, Path]) -> bool:
        """
        检查是否能处理指定文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否能处理该文件
        """
        return self.get_handler(file_path) is not None
    
    def open(
        self,
        file_path: Union[str, Path],
        **kwargs
    ) -> DocumentBase:
        """
        打开文档
        
        Args:
            file_path: 文件路径
            **kwargs: 传递给load方法的参数
            
        Returns:
            文档对象
            
        Raises:
            ValueError: 不支持的文件类型
            FileNotFoundError: 文件不存在
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        handler = self.get_handler(file_path)
        
        if not handler:
            doc_type = detect_file_type(file_path)
            raise ValueError(f"不支持的文件类型: {doc_type} ({file_path.suffix})")
        
        doc = handler.create_document(file_path=file_path)
        doc.load(**kwargs)
        
        return doc
    
    def extract_text(
        self,
        file_path: Union[str, Path],
        **kwargs
    ) -> str:
        """
        提取文档文本
        
        Args:
            file_path: 文件路径
            **kwargs: 提取参数
            
        Returns:
            文档文本内容
        """
        with self.open(file_path) as doc:
            return doc.extract_text(**kwargs)
    
    def extract_content(
        self,
        file_path: Union[str, Path],
        **kwargs
    ) -> ExtractedContent:
        """
        提取文档完整内容
        
        Args:
            file_path: 文件路径
            **kwargs: 提取参数
            
        Returns:
            文档完整内容
        """
        with self.open(file_path) as doc:
            return doc.extract_content(**kwargs)
    
    def extract_metadata(
        self,
        file_path: Union[str, Path],
        **kwargs
    ) -> DocumentMetadata:
        """
        提取文档元数据
        
        Args:
            file_path: 文件路径
            **kwargs: 提取参数
            
        Returns:
            文档元数据
        """
        with self.open(file_path) as doc:
            return doc.extract_metadata(**kwargs)
    
    def convert(
        self,
        file_path: Union[str, Path],
        target_type: Union[DocumentType, str],
        output_path: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> Union[str, Path, bytes]:
        """
        转换文档格式
        
        Args:
            file_path: 源文件路径
            target_type: 目标格式（DocumentType或扩展名字符串）
            output_path: 输出路径（可选）
            **kwargs: 转换参数
            
        Returns:
            转换后的文件路径或字节数据
        """
        # 解析目标类型
        if isinstance(target_type, str):
            target_type = DocumentType.from_extension(target_type)
        
        with self.open(file_path) as doc:
            return doc.convert_to(target_type, output_path, **kwargs)
    
    def batch_process(
        self,
        file_paths: List[Union[str, Path]],
        operation: str = "extract_text",
        progress_callback: Optional[ProgressCallback] = None,
        max_workers: int = 4,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        批量处理文档
        
        Args:
            file_paths: 文件路径列表
            operation: 操作类型 (extract_text, extract_content, extract_metadata)
            progress_callback: 进度回调函数
            max_workers: 最大并发工作线程数
            **kwargs: 操作参数
            
        Returns:
            处理结果列表
        """
        if progress_callback is None:
            progress_callback = default_progress_callback
        
        results = []
        total = len(file_paths)
        
        def process_single(file_path: Path) -> Dict[str, Any]:
            """处理单个文件"""
            result = {
                'file_path': str(file_path),
                'file_name': file_path.name,
                'success': False,
                'data': None,
                'error': None
            }
            
            try:
                if not self.can_handle(file_path):
                    result['error'] = f"不支持的文件类型: {file_path.suffix}"
                    return result
                
                with self.open(file_path) as doc:
                    if operation == "extract_text":
                        result['data'] = doc.extract_text(**kwargs)
                    elif operation == "extract_content":
                        result['data'] = doc.extract_content(**kwargs).to_dict()
                    elif operation == "extract_metadata":
                        result['data'] = doc.extract_metadata(**kwargs).to_dict()
                    else:
                        result['error'] = f"未知的操作类型: {operation}"
                        return result
                    
                    result['success'] = True
                    
            except Exception as e:
                self._logger.error(f"处理文件失败 {file_path}: {e}")
                result['error'] = str(e)
            
            return result
        
        # 使用线程池并发处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_single, Path(fp)): idx 
                for idx, fp in enumerate(file_paths)
            }
            
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    results.append((idx, result))
                    progress_callback(len(results), total, f"处理: {result['file_name']}")
                except Exception as e:
                    self._logger.error(f"处理失败: {e}")
                    results.append((idx, {
                        'file_path': str(file_paths[idx]),
                        'success': False,
                        'error': str(e)
                    }))
        
        # 按原始顺序排序
        results.sort(key=lambda x: x[0])
        results = [r[1] for r in results]
        
        progress_callback(total, total, "完成")
        return results
    
    def batch_process_directory(
        self,
        directory: Union[str, Path],
        recursive: bool = False,
        operation: str = "extract_text",
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        批量处理目录中的文档
        
        Args:
            directory: 目录路径
            recursive: 是否递归处理子目录
            operation: 操作类型
            progress_callback: 进度回调函数
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
            if path.is_file() and self.can_handle(path):
                file_paths.append(path)
        
        self._logger.info(f"在 {dir_path} 中找到 {len(file_paths)} 个可处理文件")
        
        return self.batch_process(
            file_paths,
            operation=operation,
            progress_callback=progress_callback,
            **kwargs
        )
    
    async def batch_process_async(
        self,
        file_paths: List[Union[str, Path]],
        operation: str = "extract_text",
        progress_callback: Optional[ProgressCallback] = None,
        max_workers: int = 4,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        异步批量处理文档
        
        Args:
            file_paths: 文件路径列表
            operation: 操作类型
            progress_callback: 进度回调函数
            max_workers: 最大并发工作线程数
            **kwargs: 操作参数
            
        Returns:
            处理结果列表
        """
        if progress_callback is None:
            progress_callback = default_progress_callback
        
        loop = asyncio.get_event_loop()
        
        # 在线程池中执行同步操作
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            tasks = []
            
            for file_path in file_paths:
                task = loop.run_in_executor(
                    executor,
                    self._process_single_sync,
                    Path(file_path),
                    operation,
                    kwargs
                )
                tasks.append(task)
            
            results = []
            total = len(tasks)
            
            for i, coro in enumerate(asyncio.as_completed(tasks)):
                result = await coro
                results.append(result)
                progress_callback(i + 1, total, f"处理: {result['file_name']}")
            
            return results
    
    def _process_single_sync(
        self,
        file_path: Path,
        operation: str,
        kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """同步处理单个文件（用于异步包装）"""
        result = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'success': False,
            'data': None,
            'error': None
        }
        
        try:
            if not self.can_handle(file_path):
                result['error'] = f"不支持的文件类型: {file_path.suffix}"
                return result
            
            with self.open(file_path) as doc:
                if operation == "extract_text":
                    result['data'] = doc.extract_text(**kwargs)
                elif operation == "extract_content":
                    result['data'] = doc.extract_content(**kwargs).to_dict()
                elif operation == "extract_metadata":
                    result['data'] = doc.extract_metadata(**kwargs).to_dict()
                else:
                    result['error'] = f"未知的操作类型: {operation}"
                    return result
                
                result['success'] = True
                
        except Exception as e:
            self._logger.error(f"处理文件失败 {file_path}: {e}")
            result['error'] = str(e)
        
        return result
    
    def get_supported_types(self) -> List[DocumentType]:
        """
        获取支持的文档类型列表
        
        Returns:
            支持的文档类型列表
        """
        return list(self._handlers.keys())
    
    def get_supported_extensions(self) -> List[str]:
        """
        获取支持的文件扩展名列表
        
        Returns:
            支持的文件扩展名列表
        """
        extensions = set()
        for handler in self._handlers.values():
            extensions.update(handler.supported_extensions)
        return sorted(list(extensions))
    
    def get_document_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        获取文档信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文档信息字典
        """
        file_path = Path(file_path)
        
        info = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_extension': file_path.suffix,
            'file_size': format_file_size(file_path.stat().st_size) if file_path.exists() else None,
            'can_handle': self.can_handle(file_path),
            'document_type': None,
            'metadata': None
        }
        
        if info['can_handle']:
            doc_type = detect_file_type(file_path)
            info['document_type'] = doc_type.name
            
            try:
                metadata = self.extract_metadata(file_path)
                info['metadata'] = metadata.to_dict()
            except Exception as e:
                self._logger.warning(f"获取元数据失败: {e}")
        
        return info
    
    def close(self) -> None:
        """关闭引擎，释放资源"""
        self._temp_manager.cleanup()
    
    def __enter__(self) -> "DocumentEngine":
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        self.close()


# 全局引擎实例（单例模式）
_engine_instance: Optional[DocumentEngine] = None


def get_engine() -> DocumentEngine:
    """
    获取全局文档处理引擎实例
    
    Returns:
        文档处理引擎实例
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = DocumentEngine()
    return _engine_instance


def reset_engine() -> None:
    """重置全局引擎实例"""
    global _engine_instance
    _engine_instance = None


# 便捷函数
def extract_text(file_path: Union[str, Path], **kwargs) -> str:
    """
    提取文档文本（使用全局引擎）
    
    Args:
        file_path: 文件路径
        **kwargs: 提取参数
        
    Returns:
        文档文本内容
    """
    return get_engine().extract_text(file_path, **kwargs)


def extract_content(file_path: Union[str, Path], **kwargs) -> ExtractedContent:
    """
    提取文档完整内容（使用全局引擎）
    
    Args:
        file_path: 文件路径
        **kwargs: 提取参数
        
    Returns:
        文档完整内容
    """
    return get_engine().extract_content(file_path, **kwargs)


def extract_metadata(file_path: Union[str, Path], **kwargs) -> DocumentMetadata:
    """
    提取文档元数据（使用全局引擎）
    
    Args:
        file_path: 文件路径
        **kwargs: 提取参数
        
    Returns:
        文档元数据
    """
    return get_engine().extract_metadata(file_path, **kwargs)


def convert_document(
    file_path: Union[str, Path],
    target_type: Union[DocumentType, str],
    output_path: Optional[Union[str, Path]] = None,
    **kwargs
) -> Union[str, Path, bytes]:
    """
    转换文档格式（使用全局引擎）
    
    Args:
        file_path: 源文件路径
        target_type: 目标格式
        output_path: 输出路径
        **kwargs: 转换参数
        
    Returns:
        转换后的文件路径或字节数据
    """
    return get_engine().convert(file_path, target_type, output_path, **kwargs)


def batch_extract_text(
    file_paths: List[Union[str, Path]],
    progress_callback: Optional[ProgressCallback] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    批量提取文本（使用全局引擎）
    
    Args:
        file_paths: 文件路径列表
        progress_callback: 进度回调函数
        **kwargs: 提取参数
        
    Returns:
        处理结果列表
    """
    return get_engine().batch_process(
        file_paths,
        operation="extract_text",
        progress_callback=progress_callback,
        **kwargs
    )
