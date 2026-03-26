"""
DocMCP - Document Management & Control Platform

文档管理与控制平台的安全和性能模块。

主要功能：
- 安全沙箱执行
- 基于角色的权限控制(RBAC)
- 内容安全扫描
- 审计日志
- 多级缓存系统
- 连接池管理
- 监控指标
- 速率限制
"""

__version__ = "1.0.0"
__author__ = "DocMCP Team"

from typing import Optional

# 配置
from .config import (
    SystemConfig,
    SandboxConfig,
    AuthConfig,
    ScannerConfig,
    AuditConfig,
    CacheConfig,
    PoolConfig,
    MonitorConfig,
    LimiterConfig,
    get_config,
    set_config,
    init_config,
)

# 安全模块
from .security import (
    # 沙箱
    SandboxExecutor,
    AsyncSandboxExecutor,
    SandboxResult,
    SandboxStatus,
    ResourceLimits,
    sandbox_context,
    safe_execute,
    
    # 认证
    AuthManager,
    TokenManager,
    PasswordManager,
    PermissionChecker,
    User,
    Resource,
    Permission,
    Role,
    
    # 扫描
    ContentScanner,
    RealtimeScanner,
    ScanResult,
    ScanResultStatus,
    Threat,
    ThreatType,
    FileTypeValidator,
    quick_scan,
    scan_text,
    is_safe,
    
    # 审计
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditLevel,
    AuditConfig,
    log_event,
    log_login,
    log_access_denied,
)

# 性能模块
from .performance import (
    # 缓存
    LRUCache,
    DiskCache,
    MultiLevelCache,
    CacheEntry,
    CacheStats,
    get_cache,
    cached,
    clear_cache,
    
    # 连接池
    ConnectionPool,
    ConnectionFactory,
    ConnectionInfo,
    ConnectionState,
    PoolConfig,
    create_pool,
    get_pool,
    shutdown_all_pools,
    
    # 监控
    MetricsCollector,
    HealthChecker,
    AlertManager,
    SystemMonitor,
    MetricValue,
    MetricType,
    HealthStatus,
    HealthCheck,
    AlertRule,
    Alert,
    get_monitor,
    record_metric,
    register_health_check,
    add_alert_rule,
    
    # 限流
    RateLimiter,
    ConcurrencyLimiter,
    BackpressureController,
    TokenBucket,
    LeakyBucket,
    FixedWindow,
    SlidingWindow,
    RateLimitConfig,
    RateLimitStrategy,
    RateLimitInfo,
    RateLimitExceeded,
    rate_limit,
    check_rate_limit,
    get_rate_limit_info,
    get_rate_limiter,
    get_concurrency_limiter,
    get_backpressure_controller,
)

__all__ = [
    # 版本
    '__version__',
    '__author__',
    
    # 配置
    'SystemConfig',
    'SandboxConfig',
    'AuthConfig',
    'ScannerConfig',
    'AuditConfig',
    'CacheConfig',
    'PoolConfig',
    'MonitorConfig',
    'LimiterConfig',
    'get_config',
    'set_config',
    'init_config',
    
    # 安全 - 沙箱
    'SandboxExecutor',
    'AsyncSandboxExecutor',
    'SandboxResult',
    'SandboxStatus',
    'ResourceLimits',
    'sandbox_context',
    'safe_execute',
    
    # 安全 - 认证
    'AuthManager',
    'TokenManager',
    'PasswordManager',
    'PermissionChecker',
    'User',
    'Resource',
    'Permission',
    'Role',
    
    # 安全 - 扫描
    'ContentScanner',
    'RealtimeScanner',
    'ScanResult',
    'ScanResultStatus',
    'Threat',
    'ThreatType',
    'FileTypeValidator',
    'quick_scan',
    'scan_text',
    'is_safe',
    
    # 安全 - 审计
    'AuditLogger',
    'AuditEvent',
    'AuditEventType',
    'AuditLevel',
    'log_event',
    'log_login',
    'log_access_denied',
    
    # 性能 - 缓存
    'LRUCache',
    'DiskCache',
    'MultiLevelCache',
    'CacheEntry',
    'CacheStats',
    'get_cache',
    'cached',
    'clear_cache',
    
    # 性能 - 连接池
    'ConnectionPool',
    'ConnectionFactory',
    'ConnectionInfo',
    'ConnectionState',
    'PoolConfig',
    'create_pool',
    'get_pool',
    'shutdown_all_pools',
    
    # 性能 - 监控
    'MetricsCollector',
    'HealthChecker',
    'AlertManager',
    'SystemMonitor',
    'MetricValue',
    'MetricType',
    'HealthStatus',
    'HealthCheck',
    'AlertRule',
    'Alert',
    'get_monitor',
    'record_metric',
    'register_health_check',
    'add_alert_rule',
    
    # 性能 - 限流
    'RateLimiter',
    'ConcurrencyLimiter',
    'BackpressureController',
    'TokenBucket',
    'LeakyBucket',
    'FixedWindow',
    'SlidingWindow',
    'RateLimitConfig',
    'RateLimitStrategy',
    'RateLimitInfo',
    'RateLimitExceeded',
    'rate_limit',
    'check_rate_limit',
    'get_rate_limit_info',
    'get_rate_limiter',
    'get_concurrency_limiter',
    'get_backpressure_controller',
]


def initialize(config_path: Optional[str] = None) -> SystemConfig:
    """初始化DocMCP系统
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        SystemConfig: 系统配置
    """
    from .config import init_config
    return init_config(config_path)


def shutdown() -> None:
    """关闭DocMCP系统"""
    from .performance import shutdown_all_pools
    shutdown_all_pools()
