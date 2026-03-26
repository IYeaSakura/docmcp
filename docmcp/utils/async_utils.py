"""
Async utilities for DocMCP.

Provides common async patterns and utilities.
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any, Callable, Coroutine, List, Optional, TypeVar, Union
from dataclasses import dataclass, field

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


class AsyncTaskPool:
    """
    Pool for managing async tasks.
    
    Provides controlled concurrent execution of async tasks.
    
    Example:
        >>> pool = AsyncTaskPool(max_concurrency=5)
        >>> 
        >>> async def process(item):
        ...     return item * 2
        >>> 
        >>> results = await pool.map(process, [1, 2, 3, 4, 5])
    """
    
    def __init__(self, max_concurrency: int = 10):
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
    
    async def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run a coroutine with concurrency limit."""
        async with self._semaphore:
            return await coro
    
    async def map(
        self,
        func: Callable[[Any], Coroutine[Any, Any, T]],
        items: List[Any],
    ) -> List[T]:
        """
        Map a function over items with concurrency limit.
        
        Args:
            func: Async function to apply
            items: List of items
            
        Returns:
            List of results
        """
        async def wrapped(item):
            async with self._semaphore:
                return await func(item)
        
        tasks = [wrapped(item) for item in items]
        return await asyncio.gather(*tasks)
    
    async def map_ordered(
        self,
        func: Callable[[Any], Coroutine[Any, Any, T]],
        items: List[Any],
    ) -> List[T]:
        """
        Map a function over items preserving order.
        
        Args:
            func: Async function to apply
            items: List of items
            
        Returns:
            List of results in original order
        """
        async def wrapped(index, item):
            async with self._semaphore:
                return index, await func(item)
        
        tasks = [wrapped(i, item) for i, item in enumerate(items)]
        results = await asyncio.gather(*tasks)
        
        # Sort by index and return values
        return [r[1] for r in sorted(results, key=lambda x: x[0])]


class RateLimiter:
    """
    Rate limiter for controlling request rates.
    
    Example:
        >>> limiter = RateLimiter(max_requests=10, time_window=60)
        >>> 
        >>> async def make_request():
        ...     await limiter.acquire()
        ...     # Make request
    """
    
    def __init__(self, max_requests: int, time_window: float):
        self.max_requests = max_requests
        self.time_window = time_window
        self._requests: List[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire permission to proceed."""
        async with self._lock:
            now = time.time()
            
            # Remove old requests outside time window
            cutoff = now - self.time_window
            self._requests = [t for t in self._requests if t > cutoff]
            
            # Check if we can proceed
            if len(self._requests) >= self.max_requests:
                # Wait until oldest request is outside window
                sleep_time = self._requests[0] + self.time_window - now
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    # Recalculate after sleep
                    now = time.time()
                    cutoff = now - self.time_window
                    self._requests = [t for t in self._requests if t > cutoff]
            
            # Record this request
            self._requests.append(now)
    
    @property
    def current_rate(self) -> float:
        """Current request rate (requests per second)."""
        if not self._requests:
            return 0.0
        
        now = time.time()
        cutoff = now - self.time_window
        recent = [t for t in self._requests if t > cutoff]
        
        return len(recent) / self.time_window


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """
    Decorator for retrying async functions.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff: Backoff multiplier
        exceptions: Exceptions to catch and retry
        
    Example:
        >>> @retry(max_attempts=3, delay=1.0)
        >>> async def fetch_data():
        ...     # May fail temporarily
        ...     pass
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        raise
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            # Should never reach here
            raise RuntimeError("Unexpected end of retry loop")
        
        return wrapper  # type: ignore
    
    return decorator


def timeout(seconds: float) -> Callable[[F], F]:
    """
    Decorator for adding timeout to async functions.
    
    Args:
        seconds: Timeout in seconds
        
    Example:
        >>> @timeout(30.0)
        >>> async def slow_operation():
        ...     # Will raise TimeoutError if takes > 30s
        ...     pass
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=seconds,
            )
        
        return wrapper  # type: ignore
    
    return decorator


async def gather_with_concurrency(
    *coros: Coroutine[Any, Any, T],
    limit: int = 10,
) -> List[T]:
    """
    Gather coroutines with concurrency limit.
    
    Args:
        *coros: Coroutines to gather
        limit: Maximum concurrent executions
        
    Returns:
        List of results
    """
    semaphore = asyncio.Semaphore(limit)
    
    async def sem_coro(coro):
        async with semaphore:
            return await coro
    
    return await asyncio.gather(*[sem_coro(c) for c in coros])


class Debouncer:
    """
    Debouncer for rate-limiting function calls.
    
    Example:
        >>> debouncer = Debouncer(delay=0.5)
        >>> 
        >>> async def on_change():
        ...     # Called at most once per 0.5s
        ...     pass
        >>> 
        >>> debouncer(on_change)
    """
    
    def __init__(self, delay: float):
        self.delay = delay
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def __call__(self, func: Callable[..., Coroutine], *args, **kwargs):
        """Call function with debouncing."""
        async with self._lock:
            if self._task:
                self._task.cancel()
            
            async def delayed():
                await asyncio.sleep(self.delay)
                await func(*args, **kwargs)
            
            self._task = asyncio.create_task(delayed())


class Throttler:
    """
    Throttler for limiting function call rate.
    
    Example:
        >>> throttler = Throttler(interval=1.0)
        >>> 
        >>> async def on_event():
        ...     # Called at most once per second
        ...     pass
        >>> 
        >>> await throttler(on_event)
    """
    
    def __init__(self, interval: float):
        self.interval = interval
        self._last_call: float = 0
        self._lock = asyncio.Lock()
    
    async def __call__(self, func: Callable[..., Coroutine], *args, **kwargs):
        """Call function with throttling."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            
            self._last_call = time.time()
            return await func(*args, **kwargs)
