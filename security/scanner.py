"""
DocMCP 内容扫描模块

提供恶意代码检测、文件类型验证、内容过滤和敏感信息检测功能。
"""

import re
import os
import json
import hashlib
import magic
import tempfile
from typing import Dict, List, Optional, Set, Any, Callable, BinaryIO, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging
import zipfile
import tarfile

logger = logging.getLogger(__name__)


class ScanResultStatus(Enum):
    """扫描结果状态"""
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    ERROR = "error"
    UNKNOWN = "unknown"


class ThreatType(Enum):
    """威胁类型"""
    VIRUS = "virus"
    MALWARE = "malware"
    TROJAN = "trojan"
    RANSOMWARE = "ransomware"
    SPYWARE = "spyware"
    ADWARE = "adware"
    PHISHING = "phishing"
    XSS = "xss"
    SQL_INJECTION = "sql_injection"
    COMMAND_INJECTION = "command_injection"
    SENSITIVE_DATA = "sensitive_data"
    SUSPICIOUS_PATTERN = "suspicious_pattern"


@dataclass
class Threat:
    """威胁信息"""
    type: ThreatType
    name: str
    severity: str  # low, medium, high, critical
    description: str
    location: Optional[str] = None
    line_number: Optional[int] = None
    matched_content: Optional[str] = None
    confidence: float = 0.0  # 0.0 - 1.0


@dataclass
class ScanResult:
    """扫描结果"""
    status: ScanResultStatus
    file_path: str
    file_hash: str
    file_size: int
    mime_type: str
    threats: List[Threat] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    scan_duration: float = 0.0
    error_message: str = ""
    
    @property
    def is_clean(self) -> bool:
        """是否安全"""
        return self.status == ScanResultStatus.CLEAN and len(self.threats) == 0
    
    @property
    def has_threats(self) -> bool:
        """是否有威胁"""
        return len(self.threats) > 0
    
    @property
    def severity(self) -> str:
        """获取最高严重程度"""
        if not self.threats:
            return "none"
        
        severity_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        max_severity = max(
            self.threats,
            key=lambda t: severity_order.get(t.severity, 0)
        )
        return max_severity.severity


@dataclass
class ScannerConfig:
    """扫描器配置"""
    # 文件大小限制
    max_file_size_mb: int = 100
    max_scan_size_mb: int = 500
    
    # 扫描选项
    scan_archives: bool = True
    scan_embedded: bool = True
    deep_scan: bool = False
    
    # 威胁检测
    enable_signature_scan: bool = True
    enable_heuristic_scan: bool = True
    enable_behavior_scan: bool = False
    
    # 敏感信息检测
    detect_secrets: bool = True
    detect_pii: bool = True  # 个人身份信息
    
    # 性能
    max_scan_time: float = 300.0  # 最大扫描时间
    use_cache: bool = True


class FileTypeValidator:
    """文件类型验证器"""
    
    # 文件扩展名到MIME类型的映射
    EXTENSION_MAP: Dict[str, str] = {
        '.txt': 'text/plain',
        '.py': 'text/x-python',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.yaml': 'application/x-yaml',
        '.yml': 'application/x-yaml',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.css': 'text/css',
        '.md': 'text/markdown',
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.zip': 'application/zip',
        '.tar': 'application/x-tar',
        '.gz': 'application/gzip',
    }
    
    # 危险的MIME类型
    DANGEROUS_MIME_TYPES: Set[str] = {
        'application/x-executable',
        'application/x-dosexec',
        'application/x-msdownload',
        'application/x-sh',
        'application/x-csh',
        'application/x-bat',
        'application/x-msdos-program',
    }
    
    # 危险的文件扩展名
    DANGEROUS_EXTENSIONS: Set[str] = {
        '.exe', '.dll', '.bat', '.cmd', '.sh', '.bin',
        '.com', '.scr', '.pif', '.vbs', '.js', '.wsf',
        '.jar', '.class', '.py', '.rb', '.pl', '.php'
    }
    
    def __init__(self):
        """初始化文件类型验证器"""
        try:
            self.magic = magic.Magic(mime=True)
        except Exception as e:
            logger.warning(f"Failed to initialize magic: {e}")
            self.magic = None
    
    def get_mime_type(self, file_path: Union[str, Path, BinaryIO]) -> str:
        """获取文件的MIME类型
        
        Args:
            file_path: 文件路径或文件对象
            
        Returns:
            str: MIME类型
        """
        try:
            if self.magic:
                if isinstance(file_path, (str, Path)):
                    return self.magic.from_file(str(file_path))
                else:
                    content = file_path.read(8192)
                    file_path.seek(0)
                    return self.magic.from_buffer(content)
            else:
                # 回退到扩展名检测
                if isinstance(file_path, (str, Path)):
                    ext = Path(file_path).suffix.lower()
                else:
                    ext = ''
                return self.EXTENSION_MAP.get(ext, 'application/octet-stream')
        except Exception as e:
            logger.error(f"Failed to get MIME type: {e}")
            return 'application/octet-stream'
    
    def validate_file_type(
        self,
        file_path: Union[str, Path],
        allowed_types: Optional[Set[str]] = None,
        blocked_types: Optional[Set[str]] = None
    ) -> tuple[bool, str, str]:
        """验证文件类型
        
        Args:
            file_path: 文件路径
            allowed_types: 允许的MIME类型集合
            blocked_types: 禁止的MIME类型集合
            
        Returns:
            tuple: (是否有效, MIME类型, 错误信息)
        """
        mime_type = self.get_mime_type(file_path)
        ext = Path(file_path).suffix.lower()
        
        # 检查危险扩展名
        if ext in self.DANGEROUS_EXTENSIONS:
            return False, mime_type, f"Dangerous file extension: {ext}"
        
        # 检查危险MIME类型
        if mime_type in self.DANGEROUS_MIME_TYPES:
            return False, mime_type, f"Dangerous file type: {mime_type}"
        
        # 检查禁止的类型
        if blocked_types and mime_type in blocked_types:
            return False, mime_type, f"Blocked file type: {mime_type}"
        
        # 检查允许的类型
        if allowed_types and mime_type not in allowed_types:
            return False, mime_type, f"File type not allowed: {mime_type}"
        
        return True, mime_type, ""
    
    def is_dangerous(self, file_path: Union[str, Path]) -> bool:
        """检查文件是否危险
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否危险
        """
        mime_type = self.get_mime_type(file_path)
        ext = Path(file_path).suffix.lower()
        
        return (
            mime_type in self.DANGEROUS_MIME_TYPES or
            ext in self.DANGEROUS_EXTENSIONS
        )


class ContentScanner:
    """内容扫描器"""
    
    # 恶意代码模式
    MALICIOUS_PATTERNS: Dict[str, Dict[str, Any]] = {
        'eval_code': {
            'pattern': r'\beval\s*\(',
            'severity': 'high',
            'type': ThreatType.COMMAND_INJECTION,
            'description': 'Potentially dangerous eval() usage'
        },
        'exec_code': {
            'pattern': r'\bexec\s*\(',
            'severity': 'high',
            'type': ThreatType.COMMAND_INJECTION,
            'description': 'Potentially dangerous exec() usage'
        },
        'system_call': {
            'pattern': r'\bos\.system\s*\(|subprocess\.call\s*\(',
            'severity': 'high',
            'type': ThreatType.COMMAND_INJECTION,
            'description': 'System command execution detected'
        },
        'xss_script': {
            'pattern': r'<script[^>]*>.*?</script>',
            'severity': 'high',
            'type': ThreatType.XSS,
            'description': 'Potential XSS vulnerability'
        },
        'javascript_protocol': {
            'pattern': r'javascript:',
            'severity': 'medium',
            'type': ThreatType.XSS,
            'description': 'JavaScript protocol detected'
        },
        'sql_injection': {
            'pattern': r'(SELECT|INSERT|UPDATE|DELETE|DROP|UNION).*--',
            'severity': 'critical',
            'type': ThreatType.SQL_INJECTION,
            'description': 'Potential SQL injection'
        },
        'shell_command': {
            'pattern': r'`[^`]*`|\$\([^)]*\)',
            'severity': 'high',
            'type': ThreatType.COMMAND_INJECTION,
            'description': 'Shell command substitution detected'
        },
        'import_module': {
            'pattern': r'__import__\s*\(|importlib',
            'severity': 'medium',
            'type': ThreatType.SUSPICIOUS_PATTERN,
            'description': 'Dynamic module import detected'
        },
        'base64_decode': {
            'pattern': r'base64\.(b64decode|decodestring)',
            'severity': 'low',
            'type': ThreatType.SUSPICIOUS_PATTERN,
            'description': 'Base64 decoding detected'
        },
        'network_socket': {
            'pattern': r'socket\.(socket|create_connection)',
            'severity': 'medium',
            'type': ThreatType.SUSPICIOUS_PATTERN,
            'description': 'Network socket usage detected'
        },
    }
    
    # 敏感信息模式
    SECRET_PATTERNS: Dict[str, Dict[str, Any]] = {
        'api_key': {
            'pattern': r'[a-zA-Z0-9]{32,64}',
            'severity': 'medium',
            'type': ThreatType.SENSITIVE_DATA,
            'description': 'Potential API key detected'
        },
        'password_assignment': {
            'pattern': r'password\s*=\s*["\'][^"\']+["\']',
            'severity': 'high',
            'type': ThreatType.SENSITIVE_DATA,
            'description': 'Password in plaintext detected'
        },
        'secret_key': {
            'pattern': r'secret[_-]?key\s*=\s*["\'][^"\']+["\']',
            'severity': 'high',
            'type': ThreatType.SENSITIVE_DATA,
            'description': 'Secret key detected'
        },
        'private_key': {
            'pattern': r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
            'severity': 'critical',
            'type': ThreatType.SENSITIVE_DATA,
            'description': 'Private key detected'
        },
        'aws_access_key': {
            'pattern': r'AKIA[0-9A-Z]{16}',
            'severity': 'critical',
            'type': ThreatType.SENSITIVE_DATA,
            'description': 'AWS Access Key detected'
        },
        'github_token': {
            'pattern': r'gh[pousr]_[A-Za-z0-9_]{36,}',
            'severity': 'critical',
            'type': ThreatType.SENSITIVE_DATA,
            'description': 'GitHub token detected'
        },
    }
    
    def __init__(self, config: Optional[ScannerConfig] = None):
        """初始化内容扫描器
        
        Args:
            config: 扫描器配置
        """
        self.config = config or ScannerConfig()
        self.file_validator = FileTypeValidator()
        self._scan_cache: Dict[str, ScanResult] = {}
    
    def scan_file(
        self,
        file_path: Union[str, Path],
        content: Optional[bytes] = None
    ) -> ScanResult:
        """扫描文件
        
        Args:
            file_path: 文件路径
            content: 文件内容（可选）
            
        Returns:
            ScanResult: 扫描结果
        """
        import time
        start_time = time.time()
        
        file_path = Path(file_path)
        
        try:
            # 检查文件大小
            if content:
                file_size = len(content)
            else:
                file_size = file_path.stat().st_size
            
            if file_size > self.config.max_file_size_mb * 1024 * 1024:
                return ScanResult(
                    status=ScanResultStatus.ERROR,
                    file_path=str(file_path),
                    file_hash="",
                    file_size=file_size,
                    mime_type="",
                    error_message=f"File too large: {file_size} bytes",
                    scan_duration=time.time() - start_time
                )
            
            # 读取文件内容
            if content is None:
                with open(file_path, 'rb') as f:
                    content = f.read()
            
            # 计算文件哈希
            file_hash = hashlib.sha256(content).hexdigest()
            
            # 检查缓存
            if self.config.use_cache and file_hash in self._scan_cache:
                cached = self._scan_cache[file_hash]
                cached.file_path = str(file_path)
                return cached
            
            # 验证文件类型
            mime_type = self.file_validator.get_mime_type(file_path)
            
            # 初始化结果
            threats: List[Threat] = []
            
            # 扫描文本内容
            try:
                text_content = content.decode('utf-8', errors='ignore')
                threats.extend(self._scan_text_content(text_content))
            except Exception as e:
                logger.warning(f"Failed to decode content: {e}")
            
            # 扫描归档文件
            if self.config.scan_archives:
                threats.extend(self._scan_archive(file_path, content))
            
            # 确定状态
            if any(t.severity == 'critical' for t in threats):
                status = ScanResultStatus.MALICIOUS
            elif any(t.severity == 'high' for t in threats):
                status = ScanResultStatus.MALICIOUS
            elif threats:
                status = ScanResultStatus.SUSPICIOUS
            else:
                status = ScanResultStatus.CLEAN
            
            result = ScanResult(
                status=status,
                file_path=str(file_path),
                file_hash=file_hash,
                file_size=file_size,
                mime_type=mime_type,
                threats=threats,
                scan_duration=time.time() - start_time
            )
            
            # 缓存结果
            if self.config.use_cache:
                self._scan_cache[file_hash] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Scan error for {file_path}: {e}")
            return ScanResult(
                status=ScanResultStatus.ERROR,
                file_path=str(file_path),
                file_hash="",
                file_size=0,
                mime_type="",
                error_message=str(e),
                scan_duration=time.time() - start_time
            )
    
    def scan_text(self, text: str, source: str = "text") -> ScanResult:
        """扫描文本内容
        
        Args:
            text: 文本内容
            source: 来源标识
            
        Returns:
            ScanResult: 扫描结果
        """
        import time
        start_time = time.time()
        
        threats = self._scan_text_content(text)
        
        if any(t.severity == 'critical' for t in threats):
            status = ScanResultStatus.MALICIOUS
        elif any(t.severity == 'high' for t in threats):
            status = ScanResultStatus.MALICIOUS
        elif threats:
            status = ScanResultStatus.SUSPICIOUS
        else:
            status = ScanResultStatus.CLEAN
        
        return ScanResult(
            status=status,
            file_path=source,
            file_hash=hashlib.sha256(text.encode()).hexdigest(),
            file_size=len(text),
            mime_type='text/plain',
            threats=threats,
            scan_duration=time.time() - start_time
        )
    
    def _scan_text_content(self, content: str) -> List[Threat]:
        """扫描文本内容
        
        Args:
            content: 文本内容
            
        Returns:
            List[Threat]: 发现的威胁列表
        """
        threats = []
        lines = content.split('\n')
        
        # 扫描恶意代码模式
        if self.config.enable_signature_scan:
            for name, pattern_info in self.MALICIOUS_PATTERNS.items():
                pattern = pattern_info['pattern']
                
                for line_num, line in enumerate(lines, 1):
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    
                    for match in matches:
                        threat = Threat(
                            type=pattern_info['type'],
                            name=name,
                            severity=pattern_info['severity'],
                            description=pattern_info['description'],
                            location=f"line {line_num}",
                            line_number=line_num,
                            matched_content=match.group()[:100],
                            confidence=0.8
                        )
                        threats.append(threat)
        
        # 扫描敏感信息
        if self.config.detect_secrets:
            for name, pattern_info in self.SECRET_PATTERNS.items():
                pattern = pattern_info['pattern']
                
                for line_num, line in enumerate(lines, 1):
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    
                    for match in matches:
                        threat = Threat(
                            type=pattern_info['type'],
                            name=name,
                            severity=pattern_info['severity'],
                            description=pattern_info['description'],
                            location=f"line {line_num}",
                            line_number=line_num,
                            matched_content=match.group()[:50] + "...",
                            confidence=0.9
                        )
                        threats.append(threat)
        
        return threats
    
    def _scan_archive(
        self,
        file_path: Path,
        content: bytes
    ) -> List[Threat]:
        """扫描归档文件
        
        Args:
            file_path: 文件路径
            content: 文件内容
            
        Returns:
            List[Threat]: 发现的威胁列表
        """
        threats = []
        ext = file_path.suffix.lower()
        
        try:
            if ext == '.zip' or content[:4] == b'PK\x03\x04':
                with zipfile.ZipFile(file_path if file_path.exists() else tempfile.NamedTemporaryFile(delete=False)) as zf:
                    for name in zf.namelist():
                        # 检查文件名
                        if any(dangerous in name.lower() for dangerous in ['..', '//', '::']):
                            threats.append(Threat(
                                type=ThreatType.SUSPICIOUS_PATTERN,
                                name='suspicious_archive_path',
                                severity='high',
                                description=f'Suspicious path in archive: {name}',
                                location=name
                            ))
                        
                        # 检查文件扩展名
                        file_ext = Path(name).suffix.lower()
                        if file_ext in FileTypeValidator.DANGEROUS_EXTENSIONS:
                            threats.append(Threat(
                                type=ThreatType.SUSPICIOUS_PATTERN,
                                name='dangerous_file_in_archive',
                                severity='medium',
                                description=f'Dangerous file in archive: {name}',
                                location=name
                            ))
            
            elif ext in ['.tar', '.gz', '.tgz', '.bz2']:
                # 类似地处理tar文件
                pass
                
        except Exception as e:
            logger.warning(f"Failed to scan archive {file_path}: {e}")
        
        return threats
    
    def clear_cache(self) -> None:
        """清除扫描缓存"""
        self._scan_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        return {
            'cache_size': len(self._scan_cache),
            'cache_entries': list(self._scan_cache.keys())[:10]  # 只显示前10个
        }


class RealtimeScanner:
    """实时扫描器"""
    
    def __init__(self, scanner: Optional[ContentScanner] = None):
        """初始化实时扫描器
        
        Args:
            scanner: 内容扫描器
        """
        self.scanner = scanner or ContentScanner()
        self._watchers: Dict[str, Any] = {}
        self._callbacks: List[Callable[[ScanResult], None]] = []
    
    def add_callback(self, callback: Callable[[ScanResult], None]) -> None:
        """添加扫描回调
        
        Args:
            callback: 回调函数
        """
        self._callbacks.append(callback)
    
    def scan_stream(self, stream: BinaryIO, chunk_size: int = 8192) -> ScanResult:
        """扫描数据流
        
        Args:
            stream: 数据流
            chunk_size: 块大小
            
        Returns:
            ScanResult: 扫描结果
        """
        content = b''
        
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            content += chunk
            
            # 检查大小限制
            if len(content) > self.scanner.config.max_scan_size_mb * 1024 * 1024:
                return ScanResult(
                    status=ScanResultStatus.ERROR,
                    file_path="stream",
                    file_hash="",
                    file_size=len(content),
                    mime_type="",
                    error_message="Stream too large"
                )
        
        # 创建临时文件进行扫描
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            result = self.scanner.scan_file(tmp_path, content)
            
            # 触发回调
            for callback in self._callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            
            return result
            
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# 便捷函数
def quick_scan(file_path: Union[str, Path]) -> ScanResult:
    """快速扫描文件的便捷函数"""
    scanner = ContentScanner()
    return scanner.scan_file(file_path)


def scan_text(text: str) -> ScanResult:
    """扫描文本的便捷函数"""
    scanner = ContentScanner()
    return scanner.scan_text(text)


def is_safe(file_path: Union[str, Path]) -> bool:
    """检查文件是否安全的便捷函数"""
    result = quick_scan(file_path)
    return result.is_clean
