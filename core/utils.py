"""
工具函数模块

提供文档处理所需的通用工具函数，包括文件类型检测、编码检测、临时文件管理等。
"""

import io
import logging
import mimetypes
import os
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple, Union, Generator

import chardet

# 配置日志
logger = logging.getLogger(__name__)

# 文件签名魔数
FILE_SIGNATURES = {
    # Microsoft Office 文档 (复合文档格式)
    b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': 'ole2',  # DOC, XLS, PPT
    
    # ZIP-based Office 文档
    b'PK\x03\x04': 'zip',  # DOCX, XLSX, PPTX
    
    # PDF
    b'%PDF': 'pdf',
    
    # XML
    b'<?xml': 'xml',
    
    # RTF
    b'{\\rtf': 'rtf',
    
    # Plain text (无特定签名)
    b'': 'txt',
}

# Office 文档子类型检测
OFFICE_SUBTYPES = {
    'word/document.xml': DocumentType.DOCX,
    'xl/workbook.xml': DocumentType.XLSX,
    'ppt/presentation.xml': DocumentType.PPTX,
}


# 导入DocumentType（延迟导入避免循环依赖）
def _get_document_type():
    from .document import DocumentType
    return DocumentType


class FileTypeDetector:
    """
    文件类型检测器
    
    通过文件签名和内容分析检测文件类型。
    """
    
    # 读取的前N个字节用于检测
    DETECTION_BYTES = 8192
    
    @classmethod
    def detect_by_signature(cls, file_path: Union[str, Path, BinaryIO]) -> Optional[str]:
        """
        通过文件签名检测文件类型
        
        Args:
            file_path: 文件路径或文件流
            
        Returns:
            检测到的文件类型，或None
        """
        try:
            if isinstance(file_path, (str, Path)):
                with open(file_path, 'rb') as f:
                    header = f.read(cls.DETECTION_BYTES)
            else:
                file_path.seek(0)
                header = file_path.read(cls.DETECTION_BYTES)
                file_path.seek(0)
            
            # 检查签名
            for signature, file_type in FILE_SIGNATURES.items():
                if header.startswith(signature):
                    return file_type
            
            # 检查是否是纯文本
            if cls._is_text_content(header):
                return 'txt'
            
            return None
            
        except Exception as e:
            logger.warning(f"文件签名检测失败: {e}")
            return None
    
    @classmethod
    def detect_office_subtype(
        cls,
        file_path: Union[str, Path, BinaryIO]
    ) -> "DocumentType":
        """
        检测Office文档子类型
        
        Args:
            file_path: 文件路径或文件流
            
        Returns:
            文档类型枚举
        """
        DocumentType = _get_document_type()
        
        try:
            if isinstance(file_path, (str, Path)):
                file_obj = open(file_path, 'rb')
                should_close = True
            else:
                file_obj = file_path
                should_close = False
            
            file_obj.seek(0)
            
            # 检查是否是ZIP格式
            if not zipfile.is_zipfile(file_obj):
                if should_close:
                    file_obj.close()
                return DocumentType.UNKNOWN
            
            file_obj.seek(0)
            
            # 检查ZIP内容
            with zipfile.ZipFile(file_obj, 'r') as zf:
                namelist = zf.namelist()
                
                for indicator, doc_type in OFFICE_SUBTYPES.items():
                    if indicator in namelist:
                        if should_close:
                            file_obj.close()
                        return doc_type
            
            if should_close:
                file_obj.close()
            
            return DocumentType.UNKNOWN
            
        except Exception as e:
            logger.warning(f"Office子类型检测失败: {e}")
            return DocumentType.UNKNOWN
    
    @classmethod
    def detect_by_extension(cls, file_path: Union[str, Path]) -> "DocumentType":
        """
        通过文件扩展名检测文档类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            文档类型枚举
        """
        DocumentType = _get_document_type()
        path = Path(file_path)
        ext = path.suffix.lower()
        return DocumentType.from_extension(ext)
    
    @classmethod
    def detect(
        cls,
        file_path: Union[str, Path, BinaryIO]
    ) -> "DocumentType":
        """
        综合检测文件类型
        
        Args:
            file_path: 文件路径或文件流
            
        Returns:
            文档类型枚举
        """
        DocumentType = _get_document_type()
        
        # 首先尝试扩展名检测
        if isinstance(file_path, (str, Path)):
            ext_type = cls.detect_by_extension(file_path)
            if ext_type != DocumentType.UNKNOWN:
                return ext_type
        
        # 通过签名检测
        sig_type = cls.detect_by_signature(file_path)
        
        if sig_type == 'zip':
            # ZIP格式可能是Office文档
            return cls.detect_office_subtype(file_path)
        elif sig_type == 'ole2':
            # OLE2格式（旧版Office）
            if isinstance(file_path, (str, Path)):
                ext = Path(file_path).suffix.lower()
                if ext == '.doc':
                    return DocumentType.DOC
                elif ext == '.xls':
                    return DocumentType.XLS
                elif ext == '.ppt':
                    return DocumentType.PPT
            return DocumentType.UNKNOWN
        elif sig_type == 'pdf':
            return DocumentType.PDF
        elif sig_type == 'xml':
            return DocumentType.XML
        elif sig_type == 'rtf':
            return DocumentType.RTF
        elif sig_type == 'txt':
            return DocumentType.TXT
        
        return DocumentType.UNKNOWN
    
    @staticmethod
    def _is_text_content(data: bytes, sample_size: int = 8192) -> bool:
        """
        检查数据是否为文本内容
        
        Args:
            data: 字节数据
            sample_size: 采样大小
            
        Returns:
            是否为文本内容
        """
        sample = data[:sample_size]
        
        # 检查空字节
        if b'\x00' in sample:
            return False
        
        # 检查可打印字符比例
        try:
            text = sample.decode('utf-8', errors='ignore')
            printable_ratio = sum(1 for c in text if c.isprintable() or c.isspace()) / len(text) if text else 0
            return printable_ratio > 0.95
        except Exception:
            return False


class EncodingDetector:
    """
    编码检测器
    
    检测文本文件的编码格式。
    """
    
    # 常见编码列表
    COMMON_ENCODINGS = [
        'utf-8',
        'utf-8-sig',
        'gbk',
        'gb2312',
        'gb18030',
        'big5',
        'shift_jis',
        'euc-jp',
        'euc-kr',
        'iso-8859-1',
        'windows-1252',
        'ascii',
    ]
    
    @classmethod
    def detect(
        cls,
        file_path: Union[str, Path, BinaryIO, bytes],
        confidence_threshold: float = 0.7
    ) -> Tuple[str, float]:
        """
        检测文件编码
        
        Args:
            file_path: 文件路径、文件流或字节数据
            confidence_threshold: 置信度阈值
            
        Returns:
            (编码名称, 置信度) 元组
        """
        try:
            # 获取字节数据
            if isinstance(file_path, bytes):
                data = file_path
            elif isinstance(file_path, (str, Path)):
                with open(file_path, 'rb') as f:
                    data = f.read()
            else:
                file_path.seek(0)
                data = file_path.read()
                file_path.seek(0)
            
            # 使用chardet检测
            result = chardet.detect(data)
            encoding = result.get('encoding', 'utf-8')
            confidence = result.get('confidence', 0.0)
            
            # 标准化编码名称
            if encoding:
                encoding = encoding.lower().replace('-', '_')
                encoding = encoding.replace('_', '-')
            
            # 如果置信度低，尝试其他方法
            if confidence < confidence_threshold:
                encoding = cls._fallback_detection(data) or encoding
            
            return encoding or 'utf-8', confidence or 0.0
            
        except Exception as e:
            logger.warning(f"编码检测失败: {e}")
            return 'utf-8', 0.0
    
    @classmethod
    def _fallback_detection(cls, data: bytes) -> Optional[str]:
        """
        备用编码检测方法
        
        Args:
            data: 字节数据
            
        Returns:
            检测到的编码，或None
        """
        # 检查BOM
        if data.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        elif data.startswith(b'\xff\xfe'):
            return 'utf-16-le'
        elif data.startswith(b'\xfe\xff'):
            return 'utf-16-be'
        
        # 尝试常见编码
        for encoding in cls.COMMON_ENCODINGS:
            try:
                data.decode(encoding)
                return encoding
            except (UnicodeDecodeError, LookupError):
                continue
        
        return None
    
    @classmethod
    def read_text_file(
        cls,
        file_path: Union[str, Path],
        encoding: Optional[str] = None,
        errors: str = 'replace'
    ) -> str:
        """
        读取文本文件（自动检测编码）
        
        Args:
            file_path: 文件路径
            encoding: 指定编码（可选，自动检测）
            errors: 错误处理策略
            
        Returns:
            文件内容字符串
        """
        if encoding is None:
            encoding, _ = cls.detect(file_path)
        
        with open(file_path, 'r', encoding=encoding, errors=errors) as f:
            return f.read()


class TempFileManager:
    """
    临时文件管理器
    
    管理临时文件和目录的创建和清理。
    """
    
    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        """
        初始化临时文件管理器
        
        Args:
            base_dir: 基础目录（可选）
        """
        self._base_dir = Path(base_dir) if base_dir else Path(tempfile.gettempdir())
        self._temp_files: List[Path] = []
        self._temp_dirs: List[Path] = []
        self._logger = logging.getLogger(self.__class__.__name__)
    
    def create_temp_file(
        self,
        suffix: str = "",
        prefix: str = "docmcp_",
        content: Optional[bytes] = None
    ) -> Path:
        """
        创建临时文件
        
        Args:
            suffix: 文件后缀
            prefix: 文件前缀
            content: 文件内容（可选）
            
        Returns:
            临时文件路径
        """
        fd, path = tempfile.mkstemp(
            suffix=suffix,
            prefix=prefix,
            dir=self._base_dir
        )
        os.close(fd)
        
        path_obj = Path(path)
        self._temp_files.append(path_obj)
        
        if content:
            path_obj.write_bytes(content)
        
        self._logger.debug(f"创建临时文件: {path_obj}")
        return path_obj
    
    def create_temp_dir(
        self,
        suffix: str = "",
        prefix: str = "docmcp_"
    ) -> Path:
        """
        创建临时目录
        
        Args:
            suffix: 目录后缀
            prefix: 目录前缀
            
        Returns:
            临时目录路径
        """
        path = tempfile.mkdtemp(
            suffix=suffix,
            prefix=prefix,
            dir=self._base_dir
        )
        
        path_obj = Path(path)
        self._temp_dirs.append(path_obj)
        
        self._logger.debug(f"创建临时目录: {path_obj}")
        return path_obj
    
    def cleanup(self) -> None:
        """清理所有临时文件和目录"""
        # 清理文件
        for file_path in self._temp_files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    self._logger.debug(f"删除临时文件: {file_path}")
            except Exception as e:
                self._logger.warning(f"删除临时文件失败 {file_path}: {e}")
        
        self._temp_files.clear()
        
        # 清理目录
        for dir_path in self._temp_dirs:
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
                    self._logger.debug(f"删除临时目录: {dir_path}")
            except Exception as e:
                self._logger.warning(f"删除临时目录失败 {dir_path}: {e}")
        
        self._temp_dirs.clear()
    
    def __enter__(self) -> "TempFileManager":
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        self.cleanup()
    
    def __del__(self):
        """析构函数"""
        try:
            self.cleanup()
        except Exception:
            pass


@contextmanager
def temp_file_context(
    suffix: str = "",
    prefix: str = "docmcp_",
    content: Optional[bytes] = None
) -> Generator[Path, None, None]:
    """
    临时文件上下文管理器
    
    Args:
        suffix: 文件后缀
        prefix: 文件前缀
        content: 文件内容
        
    Yields:
        临时文件路径
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    path_obj = Path(path)
    
    try:
        if content:
            path_obj.write_bytes(content)
        yield path_obj
    finally:
        if path_obj.exists():
            path_obj.unlink()


@contextmanager
def temp_dir_context(
    suffix: str = "",
    prefix: str = "docmcp_"
) -> Generator[Path, None, None]:
    """
    临时目录上下文管理器
    
    Args:
        suffix: 目录后缀
        prefix: 目录前缀
        
    Yields:
        临时目录路径
    """
    path = tempfile.mkdtemp(suffix=suffix, prefix=prefix)
    path_obj = Path(path)
    
    try:
        yield path_obj
    finally:
        if path_obj.exists():
            shutil.rmtree(path_obj)


def get_file_mime_type(file_path: Union[str, Path]) -> Optional[str]:
    """
    获取文件MIME类型
    
    Args:
        file_path: 文件路径
        
    Returns:
        MIME类型字符串
    """
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        格式化后的字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def safe_filename(filename: str, replacement: str = '_') -> str:
    """
    生成安全的文件名
    
    Args:
        filename: 原始文件名
        replacement: 替换字符
        
    Returns:
        安全的文件名
    """
    # 非法字符
    illegal_chars = '<>:"/\\|?*'
    
    result = filename
    for char in illegal_chars:
        result = result.replace(char, replacement)
    
    # 移除控制字符
    result = ''.join(c for c in result if ord(c) >= 32)
    
    # 限制长度
    if len(result) > 255:
        name, ext = os.path.splitext(result)
        result = name[:255 - len(ext)] + ext
    
    return result or 'unnamed'


def chunk_file_reader(
    file_path: Union[str, Path],
    chunk_size: int = 8192
) -> Generator[bytes, None, None]:
    """
    分块读取文件
    
    Args:
        file_path: 文件路径
        chunk_size: 块大小
        
    Yields:
        文件块数据
    """
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def copy_file_stream(
    source: BinaryIO,
    destination: BinaryIO,
    chunk_size: int = 8192,
    callback: Optional[callable] = None
) -> int:
    """
    复制文件流
    
    Args:
        source: 源文件流
        destination: 目标文件流
        chunk_size: 块大小
        callback: 进度回调函数(current, total)
        
    Returns:
        复制的字节数
    """
    total = 0
    source.seek(0, 2)  # 移动到末尾
    file_size = source.tell()
    source.seek(0)
    
    while True:
        chunk = source.read(chunk_size)
        if not chunk:
            break
        destination.write(chunk)
        total += len(chunk)
        
        if callback:
            callback(total, file_size)
    
    return total


# 便捷函数
detect_file_type = FileTypeDetector.detect
detect_encoding = EncodingDetector.detect
read_text_with_encoding = EncodingDetector.read_text_file
