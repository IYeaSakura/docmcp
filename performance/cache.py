"""
DocMCP 缓存系统模块

提供多级缓存（内存缓存、磁盘缓存）、LRU淘汰策略、缓存预热和失效策略。
"""

import os
import json
import pickle
import gzip
import time
import hashlib
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from collections import OrderedDict
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    expires_at: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() > self.expires_at
    
    def touch(self) -> None:
        """更新访问时间"""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    total_entries: int = 0
    total_size_bytes: int = 0
    
    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        """未命中率"""
        total = self.hits + self.misses
        return self.misses / total if total > 0 else 0.0


class LRUCache:
    """LRU内存缓存
    
    基于OrderedDict实现的LRU缓存，支持：
    - 最大条目数限制
    - TTL过期
    - 线程安全
    - 统计信息
    """
    
    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: int = 3600,
        cleanup_interval: int = 60
    ):
        """初始化LRU缓存
        
        Args:
            max_size: 最大条目数
            default_ttl: 默认TTL(秒)
            cleanup_interval: 清理间隔(秒)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._last_cleanup = time.time()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[Any]: 缓存值或None
        """
        with self._lock:
            # 检查是否需要清理
            if time.time() - self._last_cleanup > self.cleanup_interval:
                self._cleanup_expired()
            
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                return None
            
            if entry.is_expired():
                self._cache.pop(key, None)
                self._stats.misses += 1
                self._stats.expirations += 1
                self._stats.total_entries = len(self._cache)
                return None
            
            # 更新访问信息
            entry.touch()
            
            # 移动到末尾（最近使用）
            self._cache.move_to_end(key)
            
            self._stats.hits += 1
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: TTL(秒)，None使用默认值
            
        Returns:
            bool: 是否成功
        """
        ttl = ttl or self.default_ttl
        
        with self._lock:
            # 检查是否需要淘汰
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_oldest()
            
            # 计算大小
            try:
                size = len(pickle.dumps(value))
            except:
                size = 0
            
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                expires_at=time.time() + ttl,
                size_bytes=size
            )
            
            # 更新或添加
            if key in self._cache:
                old_entry = self._cache[key]
                self._stats.total_size_bytes -= old_entry.size_bytes
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            self._stats.total_size_bytes += size
            self._stats.total_entries = len(self._cache)
            
            return True
    
    def delete(self, key: str) -> bool:
        """删除缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            entry = self._cache.pop(key, None)
            if entry:
                self._stats.total_size_bytes -= entry.size_bytes
                self._stats.total_entries = len(self._cache)
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """检查键是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否存在
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                return True
            return False
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._stats = CacheStats()
    
    def keys(self) -> List[str]:
        """获取所有键"""
        with self._lock:
            return list(self._cache.keys())
    
    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                expirations=self._stats.expirations,
                total_entries=self._stats.total_entries,
                total_size_bytes=self._stats.total_size_bytes
            )
    
    def _evict_oldest(self) -> None:
        """淘汰最旧的条目"""
        if self._cache:
            key, entry = self._cache.popitem(last=False)
            self._stats.total_size_bytes -= entry.size_bytes
            self._stats.evictions += 1
    
    def _cleanup_expired(self) -> None:
        """清理过期条目"""
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            entry = self._cache.pop(key, None)
            if entry:
                self._stats.total_size_bytes -= entry.size_bytes
                self._stats.expirations += 1
        
        self._stats.total_entries = len(self._cache)
        self._last_cleanup = now


class DiskCache:
    """磁盘缓存
    
    基于文件系统的持久化缓存，支持：
    - 压缩存储
    - TTL过期
    - 大小限制
    - 自动清理
    """
    
    def __init__(
        self,
        cache_dir: str = "/tmp/docmcp_cache",
        max_size_mb: int = 1024,
        default_ttl: int = 86400,
        compression: bool = True,
        compression_level: int = 6
    ):
        """初始化磁盘缓存
        
        Args:
            cache_dir: 缓存目录
            max_size_mb: 最大大小(MB)
            default_ttl: 默认TTL(秒)
            compression: 是否压缩
            compression_level: 压缩级别
        """
        self.cache_dir = Path(cache_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.compression = compression
        self.compression_level = compression_level
        
        self._lock = threading.RLock()
        self._stats = CacheStats()
        
        # 创建缓存目录
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载元数据
        self._metadata_path = self.cache_dir / ".metadata.json"
        self._metadata: Dict[str, Dict[str, Any]] = self._load_metadata()
    
    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        # 使用哈希避免文件名过长
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        """加载元数据"""
        if self._metadata_path.exists():
            try:
                with open(self._metadata_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache metadata: {e}")
        return {}
    
    def _save_metadata(self) -> None:
        """保存元数据"""
        try:
            with open(self._metadata_path, 'w') as f:
                json.dump(self._metadata, f)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            cache_path = self._get_cache_path(key)
            
            if not cache_path.exists():
                self._stats.misses += 1
                return None
            
            # 检查元数据
            meta = self._metadata.get(key)
            if meta and time.time() > meta.get('expires_at', 0):
                # 过期
                cache_path.unlink(missing_ok=True)
                self._metadata.pop(key, None)
                self._save_metadata()
                self._stats.misses += 1
                self._stats.expirations += 1
                return None
            
            try:
                # 读取缓存
                if self.compression:
                    with gzip.open(cache_path, 'rb') as f:
                        data = f.read()
                else:
                    with open(cache_path, 'rb') as f:
                        data = f.read()
                
                value = pickle.loads(data)
                
                # 更新访问信息
                if meta:
                    meta['access_count'] = meta.get('access_count', 0) + 1
                    meta['last_accessed'] = time.time()
                    self._save_metadata()
                
                self._stats.hits += 1
                return value
                
            except Exception as e:
                logger.warning(f"Failed to read cache for {key}: {e}")
                self._stats.misses += 1
                return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """设置缓存值"""
        ttl = ttl or self.default_ttl
        
        with self._lock:
            # 检查大小限制
            self._check_size_limit()
            
            try:
                # 序列化
                data = pickle.dumps(value)
                
                # 压缩
                if self.compression:
                    data = gzip.compress(data, self.compression_level)
                
                # 写入文件
                cache_path = self._get_cache_path(key)
                with open(cache_path, 'wb') as f:
                    f.write(data)
                
                # 更新元数据
                self._metadata[key] = {
                    'created_at': time.time(),
                    'expires_at': time.time() + ttl,
                    'size': len(data),
                    'access_count': 0,
                    'last_accessed': time.time(),
                }
                self._save_metadata()
                
                self._stats.total_entries = len(self._metadata)
                self._stats.total_size_bytes = sum(
                    m.get('size', 0) for m in self._metadata.values()
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to write cache for {key}: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self._lock:
            cache_path = self._get_cache_path(key)
            
            if cache_path.exists():
                cache_path.unlink()
            
            if key in self._metadata:
                del self._metadata[key]
                self._save_metadata()
                self._stats.total_entries = len(self._metadata)
                return True
            
            return False
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        with self._lock:
            cache_path = self._get_cache_path(key)
            
            if not cache_path.exists():
                return False
            
            meta = self._metadata.get(key)
            if meta and time.time() > meta.get('expires_at', 0):
                return False
            
            return True
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            # 删除所有缓存文件
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
            
            self._metadata.clear()
            self._save_metadata()
            self._stats = CacheStats()
    
    def _check_size_limit(self) -> None:
        """检查大小限制并清理"""
        total_size = sum(m.get('size', 0) for m in self._metadata.values())
        
        if total_size > self.max_size_bytes:
            # 按最后访问时间排序，删除最旧的
            sorted_items = sorted(
                self._metadata.items(),
                key=lambda x: x[1].get('last_accessed', 0)
            )
            
            for key, meta in sorted_items:
                if total_size <= self.max_size_bytes * 0.8:  # 清理到80%
                    break
                
                cache_path = self._get_cache_path(key)
                cache_path.unlink(missing_ok=True)
                total_size -= meta.get('size', 0)
                del self._metadata[key]
                self._stats.evictions += 1
            
            self._save_metadata()
    
    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                expirations=self._stats.expirations,
                total_entries=len(self._metadata),
                total_size_bytes=sum(m.get('size', 0) for m in self._metadata.values())
            )


class MultiLevelCache:
    """多级缓存
    
    组合内存缓存和磁盘缓存，提供：
    - L1: 内存缓存（快速访问）
    - L2: 磁盘缓存（持久化）
    - 缓存预热
    - 一致性保证
    """
    
    def __init__(
        self,
        memory_cache: Optional[LRUCache] = None,
        disk_cache: Optional[DiskCache] = None,
        cache_through: bool = True
    ):
        """初始化多级缓存
        
        Args:
            memory_cache: 内存缓存实例
            disk_cache: 磁盘缓存实例
            cache_through: 是否写穿透
        """
        self.l1 = memory_cache or LRUCache()
        self.l2 = disk_cache or DiskCache()
        self.cache_through = cache_through
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值（L1 -> L2）"""
        # 先查L1
        value = self.l1.get(key)
        if value is not None:
            return value
        
        # 再查L2
        value = self.l2.get(key)
        if value is not None:
            # 回填L1
            self.l1.set(key, value)
            return value
        
        return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        memory_ttl: Optional[int] = None
    ) -> bool:
        """设置缓存值"""
        # 写入L1
        self.l1.set(key, value, memory_ttl)
        
        # 写穿透到L2
        if self.cache_through:
            return self.l2.set(key, value, ttl)
        
        return True
    
    def delete(self, key: str) -> bool:
        """删除缓存值"""
        l1_result = self.l1.delete(key)
        l2_result = self.l2.delete(key)
        return l1_result or l2_result
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return self.l1.exists(key) or self.l2.exists(key)
    
    def clear(self) -> None:
        """清空缓存"""
        self.l1.clear()
        self.l2.clear()
    
    def warmup(self, keys_values: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """缓存预热
        
        Args:
            keys_values: 键值对字典
            ttl: TTL
            
        Returns:
            int: 预热的条目数
        """
        count = 0
        for key, value in keys_values.items():
            if self.set(key, value, ttl):
                count += 1
        return count
    
    def get_stats(self) -> Dict[str, CacheStats]:
        """获取统计信息"""
        return {
            'l1_memory': self.l1.get_stats(),
            'l2_disk': self.l2.get_stats(),
        }


class CacheDecorator:
    """缓存装饰器"""
    
    def __init__(
        self,
        cache: MultiLevelCache,
        key_prefix: str = "",
        ttl: Optional[int] = None
    ):
        """初始化缓存装饰器
        
        Args:
            cache: 缓存实例
            key_prefix: 键前缀
            ttl: TTL
        """
        self.cache = cache
        self.key_prefix = key_prefix
        self.ttl = ttl
    
    def __call__(self, func: Callable) -> Callable:
        """装饰函数"""
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = self._make_key(func, args, kwargs)
            
            # 尝试从缓存获取
            result = self.cache.get(cache_key)
            if result is not None:
                return result
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 缓存结果
            self.cache.set(cache_key, result, self.ttl)
            
            return result
        
        # 添加缓存控制方法
        wrapper.cache_clear = lambda: self.cache.delete(
            self._make_key(func, (), {})
        )
        
        return wrapper
    
    def _make_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        key_parts = [self.key_prefix, func.__module__, func.__name__]
        
        # 添加参数哈希
        if args or kwargs:
            arg_str = str(args) + str(sorted(kwargs.items()))
            arg_hash = hashlib.md5(arg_str.encode()).hexdigest()[:16]
            key_parts.append(arg_hash)
        
        return ":".join(key_parts)


# 便捷函数
_default_cache: Optional[MultiLevelCache] = None


def get_cache() -> MultiLevelCache:
    """获取默认缓存实例"""
    global _default_cache
    if _default_cache is None:
        _default_cache = MultiLevelCache()
    return _default_cache


def cached(
    ttl: Optional[int] = None,
    key_prefix: str = ""
):
    """缓存装饰器便捷函数"""
    def decorator(func: Callable) -> Callable:
        decorator_obj = CacheDecorator(get_cache(), key_prefix, ttl)
        return decorator_obj(func)
    return decorator


def clear_cache() -> None:
    """清空默认缓存"""
    get_cache().clear()
