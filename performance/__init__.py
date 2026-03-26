"""
DocMCP 性能模块

提供性能优化相关的功能，包括缓存系统、连接池、监控指标和限流器。
"""

from .cache import (
    LRUCache,
    DiskCache,
    MultiLevelCache,
    CacheEntry,
    CacheStats,
    CacheDecorator,
    get_cache,
    cached,
    clear_cache,
)

from .pool import (
    ConnectionPool,
    ConnectionFactory,
    ConnectionInfo,
    ConnectionState,
    PoolConfig,
    DatabaseConnectionFactory,
    HTTPConnectionFactory,
    create_pool,
    get_pool,
    shutdown_all_pools,
)

from .monitor import (
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
)

from .limiter import (
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
    RateLimitDecorator,
    get_rate_limiter,
    get_concurrency_limiter,
    get_backpressure_controller,
    rate_limit,
    check_rate_limit,
    get_rate_limit_info,
)

__all__ = [
    # 缓存
    'LRUCache',
    'DiskCache',
    'MultiLevelCache',
    'CacheEntry',
    'CacheStats',
    'CacheDecorator',
    'get_cache',
    'cached',
    'clear_cache',
    
    # 连接池
    'ConnectionPool',
    'ConnectionFactory',
    'ConnectionInfo',
    'ConnectionState',
    'PoolConfig',
    'DatabaseConnectionFactory',
    'HTTPConnectionFactory',
    'create_pool',
    'get_pool',
    'shutdown_all_pools',
    
    # 监控
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
    
    # 限流
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
    'RateLimitDecorator',
    'get_rate_limiter',
    'get_concurrency_limiter',
    'get_backpressure_controller',
    'rate_limit',
    'check_rate_limit',
    'get_rate_limit_info',
]
