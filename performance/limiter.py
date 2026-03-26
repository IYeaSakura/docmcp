"""
DocMCP 限流器模块

提供速率限制、并发控制、背压机制和多种限流策略。
"""

import time
import threading
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """限流策略"""
    TOKEN_BUCKET = "token_bucket"      # 令牌桶
    LEAKY_BUCKET = "leaky_bucket"      # 漏桶
    FIXED_WINDOW = "fixed_window"      # 固定窗口
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口


@dataclass
class RateLimitConfig:
    """限流配置"""
    rate: float = 100.0  # 每秒请求数
    burst: int = 10      # 突发容量
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    key_prefix: str = "rate_limit"


@dataclass
class RateLimitInfo:
    """限流信息"""
    allowed: bool
    limit: float
    remaining: int
    reset_time: float
    retry_after: float


class TokenBucket:
    """令牌桶算法
    
    实现令牌桶限流算法：
    - 以固定速率生成令牌
    - 请求消耗令牌
    - 桶容量限制突发流量
    """
    
    def __init__(
        self,
        rate: float = 100.0,
        capacity: int = 10
    ):
        """初始化令牌桶
        
        Args:
            rate: 令牌生成速率（每秒）
            capacity: 桶容量
        """
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_update = time.time()
        self._lock = threading.Lock()
    
    def allow(self, tokens: int = 1) -> bool:
        """检查是否允许请求
        
        Args:
            tokens: 需要的令牌数
            
        Returns:
            bool: 是否允许
        """
        with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            
            # 添加新令牌
            self._tokens = min(
                self.capacity,
                self._tokens + elapsed * self.rate
            )
            self._last_update = now
            
            # 检查令牌
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            
            return False
    
    def get_info(self) -> RateLimitInfo:
        """获取限流信息"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(
                self.capacity,
                self._tokens + elapsed * self.rate
            )
            self._last_update = now
            
            remaining = int(self._tokens)
            
            # 计算重置时间
            if remaining < self.capacity:
                reset_time = now + (self.capacity - remaining) / self.rate
            else:
                reset_time = now
            
            # 计算重试时间
            if remaining <= 0:
                retry_after = (1 - self._tokens) / self.rate
            else:
                retry_after = 0
            
            return RateLimitInfo(
                allowed=remaining > 0,
                limit=self.rate,
                remaining=max(0, remaining),
                reset_time=reset_time,
                retry_after=retry_after
            )


class LeakyBucket:
    """漏桶算法
    
    实现漏桶限流算法：
    - 请求进入桶中
    - 以固定速率流出
    - 桶满时拒绝请求
    """
    
    def __init__(
        self,
        rate: float = 100.0,
        capacity: int = 10
    ):
        """初始化漏桶
        
        Args:
            rate: 流出速率（每秒）
            capacity: 桶容量
        """
        self.rate = rate
        self.capacity = capacity
        self._volume = 0.0
        self._last_update = time.time()
        self._lock = threading.Lock()
    
    def allow(self, tokens: int = 1) -> bool:
        """检查是否允许请求"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            
            # 减少水量
            self._volume = max(0, self._volume - elapsed * self.rate)
            self._last_update = now
            
            # 检查是否可以添加
            if self._volume + tokens <= self.capacity:
                self._volume += tokens
                return True
            
            return False
    
    def get_info(self) -> RateLimitInfo:
        """获取限流信息"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._volume = max(0, self._volume - elapsed * self.rate)
            self._last_update = now
            
            remaining = max(0, int(self.capacity - self._volume))
            
            if remaining < self.capacity:
                reset_time = now + self._volume / self.rate
            else:
                reset_time = now
            
            if remaining <= 0:
                retry_after = (self._volume + 1 - self.capacity) / self.rate
            else:
                retry_after = 0
            
            return RateLimitInfo(
                allowed=remaining > 0,
                limit=self.rate,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=retry_after
            )


class FixedWindow:
    """固定窗口算法
    
    实现固定窗口限流算法：
    - 按时间窗口计数
    - 窗口内请求数限制
    - 窗口结束时重置
    """
    
    def __init__(
        self,
        limit: int = 100,
        window_size: float = 1.0
    ):
        """初始化固定窗口
        
        Args:
            limit: 窗口内最大请求数
            window_size: 窗口大小（秒）
        """
        self.limit = limit
        self.window_size = window_size
        self._count = 0
        self._window_start = time.time()
        self._lock = threading.Lock()
    
    def allow(self, tokens: int = 1) -> bool:
        """检查是否允许请求"""
        with self._lock:
            now = time.time()
            
            # 检查是否需要新窗口
            if now - self._window_start >= self.window_size:
                self._count = 0
                self._window_start = now
            
            # 检查限制
            if self._count + tokens <= self.limit:
                self._count += tokens
                return True
            
            return False
    
    def get_info(self) -> RateLimitInfo:
        """获取限流信息"""
        with self._lock:
            now = time.time()
            
            # 检查是否需要新窗口
            if now - self._window_start >= self.window_size:
                self._count = 0
                self._window_start = now
            
            remaining = max(0, self.limit - self._count)
            reset_time = self._window_start + self.window_size
            retry_after = max(0, reset_time - now) if remaining <= 0 else 0
            
            return RateLimitInfo(
                allowed=remaining > 0,
                limit=self.limit / self.window_size,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=retry_after
            )


class SlidingWindow:
    """滑动窗口算法
    
    实现滑动窗口限流算法：
    - 记录每个请求的时间戳
    - 滑动窗口内计数
    - 更平滑的限流
    """
    
    def __init__(
        self,
        limit: int = 100,
        window_size: float = 1.0
    ):
        """初始化滑动窗口
        
        Args:
            limit: 窗口内最大请求数
            window_size: 窗口大小（秒）
        """
        self.limit = limit
        self.window_size = window_size
        self._requests: deque = deque()
        self._lock = threading.Lock()
    
    def allow(self, tokens: int = 1) -> bool:
        """检查是否允许请求"""
        with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            # 移除窗口外的请求
            while self._requests and self._requests[0] < window_start:
                self._requests.popleft()
            
            # 检查限制
            if len(self._requests) + tokens <= self.limit:
                for _ in range(tokens):
                    self._requests.append(now)
                return True
            
            return False
    
    def get_info(self) -> RateLimitInfo:
        """获取限流信息"""
        with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            # 移除窗口外的请求
            while self._requests and self._requests[0] < window_start:
                self._requests.popleft()
            
            remaining = max(0, self.limit - len(self._requests))
            
            # 计算重置时间
            if self._requests:
                reset_time = self._requests[0] + self.window_size
            else:
                reset_time = now
            
            retry_after = max(0, reset_time - now) if remaining <= 0 else 0
            
            return RateLimitInfo(
                allowed=remaining > 0,
                limit=self.limit / self.window_size,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=retry_after
            )


class RateLimiter:
    """速率限制器
    
    提供多种限流策略的统一接口，支持：
    - 多键限流
    - 策略选择
    - 统计信息
    """
    
    def __init__(
        self,
        default_config: Optional[RateLimitConfig] = None
    ):
        """初始化速率限制器
        
        Args:
            default_config: 默认配置
        """
        self.default_config = default_config or RateLimitConfig()
        self._limiters: Dict[str, Any] = {}
        self._configs: Dict[str, RateLimitConfig] = {}
        self._lock = threading.Lock()
        
        # 统计
        self._stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            'allowed': 0,
            'denied': 0,
            'total': 0
        })
    
    def _create_limiter(self, config: RateLimitConfig):
        """创建限流器实例"""
        if config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return TokenBucket(config.rate, config.burst)
        elif config.strategy == RateLimitStrategy.LEAKY_BUCKET:
            return LeakyBucket(config.rate, config.burst)
        elif config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return FixedWindow(int(config.rate), 1.0)
        elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return SlidingWindow(int(config.rate), 1.0)
        else:
            return TokenBucket(config.rate, config.burst)
    
    def allow(
        self,
        key: str,
        tokens: int = 1,
        config: Optional[RateLimitConfig] = None
    ) -> bool:
        """检查是否允许请求
        
        Args:
            key: 限流键
            tokens: 消耗令牌数
            config: 限流配置
            
        Returns:
            bool: 是否允许
        """
        config = config or self.default_config
        
        with self._lock:
            # 获取或创建限流器
            limiter = self._limiters.get(key)
            if limiter is None:
                limiter = self._create_limiter(config)
                self._limiters[key] = limiter
                self._configs[key] = config
            
            # 检查限流
            allowed = limiter.allow(tokens)
            
            # 更新统计
            self._stats[key]['total'] += 1
            if allowed:
                self._stats[key]['allowed'] += 1
            else:
                self._stats[key]['denied'] += 1
            
            return allowed
    
    def get_info(self, key: str) -> Optional[RateLimitInfo]:
        """获取限流信息
        
        Args:
            key: 限流键
            
        Returns:
            Optional[RateLimitInfo]: 限流信息
        """
        with self._lock:
            limiter = self._limiters.get(key)
            if limiter:
                return limiter.get_info()
            return None
    
    def reset(self, key: str) -> bool:
        """重置限流器
        
        Args:
            key: 限流键
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            if key in self._limiters:
                config = self._configs.get(key, self.default_config)
                self._limiters[key] = self._create_limiter(config)
                self._stats[key] = {'allowed': 0, 'denied': 0, 'total': 0}
                return True
            return False
    
    def remove(self, key: str) -> bool:
        """移除限流器
        
        Args:
            key: 限流键
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            self._limiters.pop(key, None)
            self._configs.pop(key, None)
            self._stats.pop(key, None)
            return True
    
    def clear(self) -> None:
        """清空所有限流器"""
        with self._lock:
            self._limiters.clear()
            self._configs.clear()
            self._stats.clear()
    
    def get_stats(self, key: Optional[str] = None) -> Dict[str, Any]:
        """获取统计信息
        
        Args:
            key: 限流键，None返回所有
            
        Returns:
            Dict: 统计信息
        """
        with self._lock:
            if key:
                return {
                    'key': key,
                    **self._stats.get(key, {})
                }
            
            return {
                'total_keys': len(self._limiters),
                'keys': {
                    k: dict(v) for k, v in self._stats.items()
                }
            }


class ConcurrencyLimiter:
    """并发限制器
    
    限制并发请求数量，支持：
    - 最大并发数限制
    - 等待队列
    - 超时控制
    """
    
    def __init__(
        self,
        max_concurrent: int = 100,
        queue_size: int = 1000,
        timeout: float = 30.0
    ):
        """初始化并发限制器
        
        Args:
            max_concurrent: 最大并发数
            queue_size: 等待队列大小
            timeout: 超时时间
        """
        self.max_concurrent = max_concurrent
        self.queue_size = queue_size
        self.timeout = timeout
        
        self._semaphore = threading.Semaphore(max_concurrent)
        self._active = 0
        self._waiting = 0
        self._lock = threading.Lock()
        
        # 统计
        self._stats = {
            'total_acquired': 0,
            'total_released': 0,
            'total_timeout': 0,
            'total_rejected': 0,
        }
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """获取执行许可
        
        Args:
            timeout: 超时时间
            
        Returns:
            bool: 是否获取成功
        """
        timeout = timeout or self.timeout
        
        with self._lock:
            if self._waiting >= self.queue_size:
                self._stats['total_rejected'] += 1
                return False
            self._waiting += 1
        
        try:
            if self._semaphore.acquire(timeout=timeout):
                with self._lock:
                    self._waiting -= 1
                    self._active += 1
                    self._stats['total_acquired'] += 1
                return True
            else:
                with self._lock:
                    self._waiting -= 1
                    self._stats['total_timeout'] += 1
                return False
        except Exception:
            with self._lock:
                self._waiting -= 1
            raise
    
    def release(self) -> None:
        """释放执行许可"""
        with self._lock:
            if self._active > 0:
                self._active -= 1
                self._stats['total_released'] += 1
        
        self._semaphore.release()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                'max_concurrent': self.max_concurrent,
                'active': self._active,
                'waiting': self._waiting,
                'available': self.max_concurrent - self._active,
                **self._stats
            }


class BackpressureController:
    """背压控制器
    
    实现背压机制，当系统负载过高时：
    - 拒绝新请求
    - 降低处理速率
    - 通知上游
    """
    
    def __init__(
        self,
        threshold: float = 0.8,
        recovery_threshold: float = 0.5,
        cooldown_period: float = 10.0
    ):
        """初始化背压控制器
        
        Args:
            threshold: 触发背压的阈值
            recovery_threshold: 恢复阈值
            cooldown_period: 冷却时间
        """
        self.threshold = threshold
        self.recovery_threshold = recovery_threshold
        self.cooldown_period = cooldown_period
        
        self._active = False
        self._last_triggered = 0.0
        self._load_metrics: Dict[str, float] = {}
        self._lock = threading.Lock()
        
        # 回调
        self._on_backpressure: List[Callable[[], None]] = []
        self._on_recovery: List[Callable[[], None]] = []
    
    def update_load(self, metric_name: str, value: float) -> None:
        """更新负载指标
        
        Args:
            metric_name: 指标名称
            value: 指标值（0.0 - 1.0）
        """
        with self._lock:
            self._load_metrics[metric_name] = value
            
            # 计算平均负载
            avg_load = sum(self._load_metrics.values()) / len(self._load_metrics) if self._load_metrics else 0
            
            # 检查背压
            if not self._active:
                if avg_load >= self.threshold:
                    # 触发背压
                    self._active = True
                    self._last_triggered = time.time()
                    
                    for callback in self._on_backpressure:
                        try:
                            callback()
                        except Exception as e:
                            logger.error(f"Backpressure callback error: {e}")
                    
                    logger.warning(f"Backpressure activated: load={avg_load:.2%}")
            else:
                # 检查恢复
                cooldown_elapsed = time.time() - self._last_triggered
                if avg_load <= self.recovery_threshold and cooldown_elapsed >= self.cooldown_period:
                    self._active = False
                    
                    for callback in self._on_recovery:
                        try:
                            callback()
                        except Exception as e:
                            logger.error(f"Recovery callback error: {e}")
                    
                    logger.info(f"Backpressure deactivated: load={avg_load:.2%}")
    
    def is_active(self) -> bool:
        """检查背压是否激活"""
        with self._lock:
            return self._active
    
    def on_backpressure(self, callback: Callable[[], None]) -> None:
        """注册背压回调"""
        with self._lock:
            self._on_backpressure.append(callback)
    
    def on_recovery(self, callback: Callable[[], None]) -> None:
        """注册恢复回调"""
        with self._lock:
            self._on_recovery.append(callback)
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        with self._lock:
            avg_load = sum(self._load_metrics.values()) / len(self._load_metrics) if self._load_metrics else 0
            
            return {
                'active': self._active,
                'average_load': avg_load,
                'metrics': dict(self._load_metrics),
                'last_triggered': self._last_triggered,
            }


class RateLimitDecorator:
    """限流装饰器"""
    
    def __init__(
        self,
        limiter: RateLimiter,
        key_func: Optional[Callable[..., str]] = None,
        config: Optional[RateLimitConfig] = None
    ):
        """初始化限流装饰器
        
        Args:
            limiter: 限流器
            key_func: 键生成函数
            config: 限流配置
        """
        self.limiter = limiter
        self.key_func = key_func
        self.config = config
    
    def __call__(self, func: Callable) -> Callable:
        """装饰函数"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成限流键
            if self.key_func:
                key = self.key_func(*args, **kwargs)
            else:
                key = f"{func.__module__}.{func.__name__}"
            
            # 检查限流
            if not self.limiter.allow(key, config=self.config):
                info = self.limiter.get_info(key)
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {key}",
                    retry_after=info.retry_after if info else None
                )
            
            return func(*args, **kwargs)
        
        return wrapper


class RateLimitExceeded(Exception):
    """限流异常"""
    
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


# 便捷函数
_default_limiter: Optional[RateLimiter] = None
_default_concurrency: Optional[ConcurrencyLimiter] = None
_default_backpressure: Optional[BackpressureController] = None


def get_rate_limiter() -> RateLimiter:
    """获取默认限流器"""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter()
    return _default_limiter


def get_concurrency_limiter() -> ConcurrencyLimiter:
    """获取默认并发限制器"""
    global _default_concurrency
    if _default_concurrency is None:
        _default_concurrency = ConcurrencyLimiter()
    return _default_concurrency


def get_backpressure_controller() -> BackpressureController:
    """获取默认背压控制器"""
    global _default_backpressure
    if _default_backpressure is None:
        _default_backpressure = BackpressureController()
    return _default_backpressure


def rate_limit(
    rate: float = 100.0,
    burst: int = 10,
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET,
    key_func: Optional[Callable[..., str]] = None
):
    """限流装饰器便捷函数"""
    config = RateLimitConfig(rate=rate, burst=burst, strategy=strategy)
    decorator = RateLimitDecorator(get_rate_limiter(), key_func, config)
    
    def wrapper(func: Callable) -> Callable:
        return decorator(func)
    return wrapper


def check_rate_limit(key: str, tokens: int = 1) -> bool:
    """检查限流的便捷函数"""
    return get_rate_limiter().allow(key, tokens)


def get_rate_limit_info(key: str) -> Optional[RateLimitInfo]:
    """获取限流信息的便捷函数"""
    return get_rate_limiter().get_info(key)
