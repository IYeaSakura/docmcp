"""
文档抽象基类模块

提供文档处理的核心抽象接口，包括文档类型枚举、元数据类和文档基类。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple, Union
import io


class DocumentType(Enum):
    """文档类型枚举"""
    UNKNOWN = auto()
    DOC = auto()      # Word 97-2003
    DOCX = auto()     # Word 2007+
    XLS = auto()      # Excel 97-2003
    XLSX = auto()     # Excel 2007+
    PPT = auto()      # PowerPoint 97-2003
    PPTX = auto()     # PowerPoint 2007+
    PDF = auto()      # PDF文档
    TXT = auto()      # 纯文本
    RTF = auto()      # 富文本格式
    HTML = auto()     # HTML文档
    XML = auto()      # XML文档
    CSV = auto()      # CSV文件
    
    @classmethod
    def from_extension(cls, ext: str) -> "DocumentType":
        """从文件扩展名获取文档类型"""
        ext_map = {
            '.doc': cls.DOC,
            '.docx': cls.DOCX,
            '.xls': cls.XLS,
            '.xlsx': cls.XLSX,
            '.ppt': cls.PPT,
            '.pptx': cls.PPTX,
            '.pdf': cls.PDF,
            '.txt': cls.TXT,
            '.rtf': cls.RTF,
            '.html': cls.HTML,
            '.htm': cls.HTML,
            '.xml': cls.XML,
            '.csv': cls.CSV,
        }
        return ext_map.get(ext.lower().lstrip('.'), cls.UNKNOWN)


@dataclass
class DocumentMetadata:
    """文档元数据类"""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    last_modified_by: Optional[str] = None
    revision: Optional[int] = None
    category: Optional[str] = None
    comments: Optional[str] = None
    company: Optional[str] = None
    
    # 文件系统元数据
    file_size: int = 0
    file_path: Optional[Path] = None
    file_name: Optional[str] = None
    file_extension: Optional[str] = None
    
    # 自定义属性
    custom_properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat() if value else None
            elif isinstance(value, Path):
                result[key] = str(value) if value else None
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentMetadata":
        """从字典创建"""
        # 处理日期字段
        for field_name in ['created', 'modified']:
            if field_name in data and isinstance(data[field_name], str):
                try:
                    data[field_name] = datetime.fromisoformat(data[field_name])
                except (ValueError, TypeError):
                    data[field_name] = None
        
        # 处理Path字段
        if 'file_path' in data and isinstance(data['file_path'], str):
            data['file_path'] = Path(data['file_path'])
        
        # 过滤出有效字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)


@dataclass
class ExtractedContent:
    """提取的内容数据类"""
    text: str = ""
    paragraphs: List[str] = field(default_factory=list)
    tables: List[List[List[str]]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)
    hyperlinks: List[Dict[str, str]] = field(default_factory=list)
    headings: List[Dict[str, Any]] = field(default_factory=list)
    
    # 格式特定数据
    sheets: Dict[str, Any] = field(default_factory=dict)  # Excel工作表
    slides: List[Dict[str, Any]] = field(default_factory=list)  # PPT幻灯片
    pages: List[Dict[str, Any]] = field(default_factory=list)  # PDF页面
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'text': self.text,
            'paragraphs': self.paragraphs,
            'tables': self.tables,
            'images': self.images,
            'hyperlinks': self.hyperlinks,
            'headings': self.headings,
            'sheets': self.sheets,
            'slides': self.slides,
            'pages': self.pages,
        }


class DocumentBase(ABC):
    """
    文档抽象基类
    
    所有文档处理器的基类，定义了统一的文档处理接口。
    
    Attributes:
        file_path: 文档文件路径
        metadata: 文档元数据
        document_type: 文档类型
    """
    
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
            file_stream: 文档文件流（可选，用于内存中的文档）
            document_type: 文档类型（可选，自动检测）
        """
        self._file_path: Optional[Path] = Path(file_path) if file_path else None
        self._file_stream: Optional[BinaryIO] = file_stream
        self._metadata: DocumentMetadata = DocumentMetadata()
        self._document_type: DocumentType = document_type or DocumentType.UNKNOWN
        self._is_loaded: bool = False
        self._content: Optional[ExtractedContent] = None
        
        # 如果提供了文件路径，自动检测类型
        if self._file_path and self._document_type == DocumentType.UNKNOWN:
            self._document_type = DocumentType.from_extension(
                self._file_path.suffix
            )
            self._metadata.file_path = self._file_path
            self._metadata.file_name = self._file_path.name
            self._metadata.file_extension = self._file_path.suffix
    
    @property
    def file_path(self) -> Optional[Path]:
        """获取文件路径"""
        return self._file_path
    
    @property
    def metadata(self) -> DocumentMetadata:
        """获取文档元数据"""
        return self._metadata
    
    @property
    def document_type(self) -> DocumentType:
        """获取文档类型"""
        return self._document_type
    
    @property
    def is_loaded(self) -> bool:
        """检查文档是否已加载"""
        return self._is_loaded
    
    @abstractmethod
    def load(self, **kwargs) -> "DocumentBase":
        """
        加载文档
        
        Returns:
            self: 支持链式调用
            
        Raises:
            FileNotFoundError: 文件不存在
            PermissionError: 没有读取权限
            ValueError: 文件格式错误
        """
        pass
    
    @abstractmethod
    def extract_text(self, **kwargs) -> str:
        """
        提取纯文本内容
        
        Returns:
            文档的纯文本内容
        """
        pass
    
    @abstractmethod
    def extract_content(self, **kwargs) -> ExtractedContent:
        """
        提取完整内容
        
        Returns:
            包含文本、表格、图片等的完整内容
        """
        pass
    
    @abstractmethod
    def extract_metadata(self, **kwargs) -> DocumentMetadata:
        """
        提取文档元数据
        
        Returns:
            文档元数据对象
        """
        pass
    
    @abstractmethod
    def save(self, output_path: Union[str, Path], **kwargs) -> "DocumentBase":
        """
        保存文档
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            self: 支持链式调用
        """
        pass
    
    @abstractmethod
    def convert_to(
        self,
        target_type: DocumentType,
        output_path: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> Union[str, Path, bytes]:
        """
        转换文档格式
        
        Args:
            target_type: 目标文档类型
            output_path: 输出路径（可选）
            
        Returns:
            转换后的文件路径或字节数据
        """
        pass
    
    def get_file_size(self) -> int:
        """
        获取文件大小
        
        Returns:
            文件大小（字节）
        """
        if self._file_path and self._file_path.exists():
            return self._file_path.stat().st_size
        return 0
    
    def __enter__(self) -> "DocumentBase":
        """上下文管理器入口"""
        if not self._is_loaded:
            self.load()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        self.close()
    
    @abstractmethod
    def close(self) -> None:
        """关闭文档，释放资源"""
        pass
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"type={self._document_type.name}, "
            f"path={self._file_path}, "
            f"loaded={self._is_loaded})"
        )


class DocumentHandler(ABC):
    """
    文档处理器抽象基类
    
    用于处理特定格式文档的处理器接口。
    """
    
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
    
    @abstractmethod
    def can_handle(self, file_path: Union[str, Path]) -> bool:
        """
        检查是否能处理指定文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否能处理该文件
        """
        pass
    
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


# 进度回调类型
ProgressCallback = callable


def default_progress_callback(current: int, total: int, message: str = "") -> None:
    """默认进度回调函数"""
    percentage = (current / total * 100) if total > 0 else 0
    print(f"Progress: {percentage:.1f}% ({current}/{total}) {message}")
