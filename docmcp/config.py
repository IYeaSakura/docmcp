"""
DocMCP 系统配置模块

提供系统级别的配置管理，包括安全配置和性能配置。
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from enum import Enum


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class SandboxConfig:
    """沙箱配置"""
    # 资源限制
    max_memory_mb: int = 512  # 最大内存限制(MB)
    max_cpu_percent: float = 50.0  # 最大CPU使用率(%)
    max_execution_time: float = 30.0  # 最大执行时间(秒)
    max_processes: int = 5  # 最大进程数
    
    # 文件系统限制
    temp_dir: str = "/tmp/docmcp_sandbox"  # 临时目录
    max_file_size_mb: int = 100  # 最大文件大小(MB)
    allowed_extensions: Set[str] = field(default_factory=lambda: {
        '.txt', '.py', '.js', '.json', '.xml', '.yaml', '.yml', '.md'
    })
    
    # 网络限制
    network_enabled: bool = False  # 是否允许网络访问
    allowed_hosts: List[str] = field(default_factory=list)  # 允许访问的主机
    blocked_ports: Set[int] = field(default_factory=lambda: {22, 23, 25, 135, 445})
    
    # 安全选项
    use_seccomp: bool = True  # 使用seccomp
    use_namespaces: bool = True  # 使用Linux命名空间
    read_only_fs: bool = True  # 只读文件系统
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SandboxConfig':
        """从字典创建配置"""
        return cls(**data)


@dataclass
class AuthConfig:
    """权限控制配置"""
    # JWT配置
    jwt_secret: str = field(default_factory=lambda: os.urandom(32).hex())
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    
    # 密码策略
    min_password_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digits: bool = True
    require_special_chars: bool = True
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30
    
    # 会话管理
    session_timeout_minutes: int = 60
    max_sessions_per_user: int = 5
    
    # RBAC配置
    default_role: str = "user"
    admin_roles: List[str] = field(default_factory=lambda: ["admin", "superadmin"])
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuthConfig':
        """从字典创建配置"""
        return cls(**data)


@dataclass
class ScannerConfig:
    """内容扫描配置"""
    # 恶意代码检测
    enable_virus_scan: bool = True
    virus_scan_timeout: int = 60
    quarantine_dir: str = "/tmp/docmcp_quarantine"
    
    # 文件类型验证
    verify_magic_bytes: bool = True
    max_magic_bytes_size: int = 8192
    
    # 内容过滤
    enable_content_filter: bool = True
    blocked_patterns: List[str] = field(default_factory=lambda: [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'eval\s*\(',
        r'exec\s*\(',
        r'system\s*\(',
        r'subprocess\.call',
        r'os\.system',
    ])
    
    # 敏感信息检测
    detect_secrets: bool = True
    secret_patterns: Dict[str, str] = field(default_factory=lambda: {
        'api_key': r'[a-zA-Z0-9]{32,}',
        'password': r'password\s*=\s*["\'][^"\']+["\']',
        'token': r'token\s*=\s*["\'][^"\']+["\']',
        'private_key': r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
    })
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScannerConfig':
        """从字典创建配置"""
        return cls(**data)


@dataclass
class AuditConfig:
    """审计日志配置"""
    # 日志配置
    log_dir: str = "/var/log/docmcp"
    log_file: str = "audit.log"
    log_level: LogLevel = LogLevel.INFO
    
    # 日志轮转
    max_log_size_mb: int = 100
    max_backup_count: int = 10
    log_rotation: str = "midnight"  # 轮转方式: size, time, midnight
    
    # 保留策略
    retention_days: int = 90
    archive_enabled: bool = True
    archive_dir: str = "/var/log/docmcp/archive"
    
    # 事件过滤
    log_all_operations: bool = False
    logged_operations: List[str] = field(default_factory=lambda: [
        "login", "logout", "create", "update", "delete", 
        "execute", "download", "upload", "access_denied"
    ])
    
    # 异步日志
    async_logging: bool = True
    log_queue_size: int = 10000
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditConfig':
        """从字典创建配置"""
        return cls(**data)


@dataclass
class CacheConfig:
    """缓存配置"""
    # 内存缓存
    memory_cache_enabled: bool = True
    memory_cache_size: int = 10000  # 最大条目数
    memory_cache_ttl: int = 3600  # 默认TTL(秒)
    
    # 磁盘缓存
    disk_cache_enabled: bool = True
    disk_cache_dir: str = "/tmp/docmcp_cache"
    disk_cache_size_mb: int = 1024
    disk_cache_ttl: int = 86400  # 默认TTL(秒)
    
    # 缓存策略
    eviction_policy: str = "lru"  # lru, lfu, fifo
    compression_enabled: bool = True
    compression_level: int = 6
    
    # 预热配置
    warmup_enabled: bool = True
    warmup_keys: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheConfig':
        """从字典创建配置"""
        return cls(**data)


@dataclass
class PoolConfig:
    """连接池配置"""
    # 通用配置
    min_connections: int = 5
    max_connections: int = 50
    connection_timeout: float = 30.0
    idle_timeout: float = 300.0
    max_lifetime: float = 3600.0
    
    # 健康检查
    health_check_interval: float = 30.0
    health_check_query: str = "SELECT 1"
    
    # 重试配置
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    
    # 监控
    enable_metrics: bool = True
    metrics_interval: float = 60.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PoolConfig':
        """从字典创建配置"""
        return cls(**data)


@dataclass
class MonitorConfig:
    """监控配置"""
    # 指标收集
    metrics_enabled: bool = True
    metrics_interval: float = 60.0
    metrics_retention_hours: int = 168  # 7天
    
    # 健康检查
    health_check_enabled: bool = True
    health_check_interval: float = 30.0
    health_check_timeout: float = 5.0
    
    # 告警配置
    alerts_enabled: bool = True
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'cpu_percent': 80.0,
        'memory_percent': 85.0,
        'disk_percent': 90.0,
        'error_rate': 5.0,
        'response_time_ms': 1000.0,
    })
    
    # 告警通道
    alert_webhook_url: Optional[str] = None
    alert_email: Optional[str] = None
    alert_slack_channel: Optional[str] = None
    
    # 性能指标
    track_request_latency: bool = True
    track_throughput: bool = True
    track_error_rate: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MonitorConfig':
        """从字典创建配置"""
        return cls(**data)


@dataclass
class LimiterConfig:
    """限流器配置"""
    # 速率限制
    enabled: bool = True
    default_rate: float = 100.0  # 每秒请求数
    default_burst: int = 10  # 突发请求数
    
    # 并发限制
    max_concurrent: int = 100
    queue_size: int = 1000
    queue_timeout: float = 30.0
    
    # 背压机制
    backpressure_enabled: bool = True
    backpressure_threshold: float = 0.8  # 80%容量时触发
    
    # 限流策略
    strategy: str = "token_bucket"  # token_bucket, leaky_bucket, fixed_window
    key_prefix: str = "rate_limit"
    
    # 白名单/黑名单
    whitelist: List[str] = field(default_factory=list)
    blacklist: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LimiterConfig':
        """从字典创建配置"""
        return cls(**data)


@dataclass
class SystemConfig:
    """系统主配置"""
    # 应用信息
    app_name: str = "DocMCP"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # 子配置
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    pool: PoolConfig = field(default_factory=PoolConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    limiter: LimiterConfig = field(default_factory=LimiterConfig)
    
    # 环境
    env: str = "production"  # development, testing, production
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'app_name': self.app_name,
            'app_version': self.app_version,
            'debug': self.debug,
            'env': self.env,
            'sandbox': self.sandbox.to_dict(),
            'auth': self.auth.to_dict(),
            'scanner': self.scanner.to_dict(),
            'audit': self.audit.to_dict(),
            'cache': self.cache.to_dict(),
            'pool': self.pool.to_dict(),
            'monitor': self.monitor.to_dict(),
            'limiter': self.limiter.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemConfig':
        """从字典创建配置"""
        return cls(
            app_name=data.get('app_name', 'DocMCP'),
            app_version=data.get('app_version', '1.0.0'),
            debug=data.get('debug', False),
            env=data.get('env', 'production'),
            sandbox=SandboxConfig.from_dict(data.get('sandbox', {})),
            auth=AuthConfig.from_dict(data.get('auth', {})),
            scanner=ScannerConfig.from_dict(data.get('scanner', {})),
            audit=AuditConfig.from_dict(data.get('audit', {})),
            cache=CacheConfig.from_dict(data.get('cache', {})),
            pool=PoolConfig.from_dict(data.get('pool', {})),
            monitor=MonitorConfig.from_dict(data.get('monitor', {})),
            limiter=LimiterConfig.from_dict(data.get('limiter', {})),
        )
    
    def save(self, filepath: str) -> None:
        """保存配置到文件"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str) -> 'SystemConfig':
        """从文件加载配置"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    @classmethod
    def from_env(cls) -> 'SystemConfig':
        """从环境变量加载配置"""
        config = cls()
        
        # 基本配置
        config.debug = os.getenv('DOCMCP_DEBUG', 'false').lower() == 'true'
        config.env = os.getenv('DOCMCP_ENV', 'production')
        
        # 沙箱配置
        if os.getenv('DOCMCP_SANDBOX_MAX_MEMORY'):
            config.sandbox.max_memory_mb = int(os.getenv('DOCMCP_SANDBOX_MAX_MEMORY'))
        if os.getenv('DOCMCP_SANDBOX_MAX_TIME'):
            config.sandbox.max_execution_time = float(os.getenv('DOCMCP_SANDBOX_MAX_TIME'))
        if os.getenv('DOCMCP_SANDBOX_NETWORK_ENABLED'):
            config.sandbox.network_enabled = os.getenv('DOCMCP_SANDBOX_NETWORK_ENABLED').lower() == 'true'
        
        # 缓存配置
        if os.getenv('DOCMCP_CACHE_MEMORY_SIZE'):
            config.cache.memory_cache_size = int(os.getenv('DOCMCP_CACHE_MEMORY_SIZE'))
        if os.getenv('DOCMCP_CACHE_DISK_SIZE'):
            config.cache.disk_cache_size_mb = int(os.getenv('DOCMCP_CACHE_DISK_SIZE'))
        
        # 限流配置
        if os.getenv('DOCMCP_LIMITER_RATE'):
            config.limiter.default_rate = float(os.getenv('DOCMCP_LIMITER_RATE'))
        if os.getenv('DOCMCP_LIMITER_ENABLED'):
            config.limiter.enabled = os.getenv('DOCMCP_LIMITER_ENABLED').lower() == 'true'
        
        return config


# 全局配置实例
_config: Optional[SystemConfig] = None


def get_config() -> SystemConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = SystemConfig.from_env()
    return _config


def set_config(config: SystemConfig) -> None:
    """设置全局配置实例"""
    global _config
    _config = config


def init_config(config_path: Optional[str] = None) -> SystemConfig:
    """初始化配置"""
    global _config
    
    if config_path and Path(config_path).exists():
        _config = SystemConfig.load(config_path)
    else:
        _config = SystemConfig.from_env()
    
    return _config
