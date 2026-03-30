"""
Performance module tests.

This module tests:
- Metrics collection
- Health checking
- Alert management
- System monitoring
- Performance utilities
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from docmcp.performance.monitor import (
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
from docmcp.performance.cache import Cache, cached, LRUCache
from docmcp.performance.limiter import RateLimiter, ConcurrencyLimiter
from docmcp.performance.pool import WorkerPool, TaskPriority


# ============================================================================
# MetricValue Tests
# ============================================================================

class TestMetricValue:
    """Test MetricValue class."""

    def test_metric_value_creation(self):
        """Test metric value creation."""
        metric = MetricValue(
            name="test_metric",
            value=100.0,
            metric_type=MetricType.GAUGE,
            timestamp=time.time(),
            labels={"env": "test"},
        )
        assert metric.name == "test_metric"
        assert metric.value == 100.0
        assert metric.metric_type == MetricType.GAUGE
        assert metric.labels == {"env": "test"}

    def test_metric_to_dict(self):
        """Test metric serialization."""
        metric = MetricValue(
            name="test",
            value=50.0,
            metric_type=MetricType.COUNTER,
            timestamp=1234567890.0,
        )
        data = metric.to_dict()
        assert data["name"] == "test"
        assert data["value"] == 50.0
        assert data["type"] == "counter"


# ============================================================================
# MetricsCollector Tests
# ============================================================================

class TestMetricsCollector:
    """Test MetricsCollector class."""

    def test_collector_creation(self):
        """Test collector creation."""
        collector = MetricsCollector(max_data_points=100, retention_hours=1)
        assert collector.max_data_points == 100
        assert collector.retention_hours == 1

    def test_counter_increment(self):
        """Test counter increment."""
        collector = MetricsCollector()
        collector.counter("requests", 1)
        collector.counter("requests", 1)

        latest = collector.get_latest("requests")
        assert latest.value == 2.0

    def test_counter_with_labels(self):
        """Test counter with labels."""
        collector = MetricsCollector()
        collector.counter("requests", 1, {"method": "GET"})
        collector.counter("requests", 1, {"method": "POST"})

        # Should have separate counters
        metrics = collector.get_metric("requests")
        assert len(metrics) == 2

    def test_gauge_set(self):
        """Test gauge setting."""
        collector = MetricsCollector()
        collector.gauge("temperature", 25.0)
        collector.gauge("temperature", 30.0)

        latest = collector.get_latest("temperature")
        assert latest.value == 30.0

    def test_histogram_record(self):
        """Test histogram recording."""
        collector = MetricsCollector()
        collector.histogram("response_time", 0.1)
        collector.histogram("response_time", 0.2)
        collector.histogram("response_time", 0.3)

        metrics = collector.get_metric("response_time")
        assert len(metrics) == 3

    def test_summary_record(self):
        """Test summary recording."""
        collector = MetricsCollector()
        collector.summary("request_size", 1024.0)

        latest = collector.get_latest("request_size")
        assert latest.value == 1024.0

    def test_get_metric_with_time_range(self):
        """Test getting metrics with time range."""
        collector = MetricsCollector()
        now = time.time()

        collector.counter("test", 1)

        metrics = collector.get_metric("test", start_time=now - 1, end_time=now + 1)
        assert len(metrics) == 1

        metrics = collector.get_metric("test", start_time=now + 10)
        assert len(metrics) == 0

    def test_get_metric_with_labels(self):
        """Test getting metrics with label filter."""
        collector = MetricsCollector()
        collector.counter("requests", 1, {"method": "GET", "status": "200"})
        collector.counter("requests", 1, {"method": "POST", "status": "200"})

        metrics = collector.get_metric("requests", labels={"method": "GET"})
        assert len(metrics) == 1

    def test_get_stats(self):
        """Test getting metric statistics."""
        collector = MetricsCollector()
        collector.gauge("values", 10.0)
        collector.gauge("values", 20.0)
        collector.gauge("values", 30.0)

        stats = collector.get_stats("values")
        assert stats is not None
        assert stats["count"] == 3
        assert stats["min"] == 10.0
        assert stats["max"] == 30.0
        assert stats["avg"] == 20.0

    def test_export_prometheus(self):
        """Test Prometheus format export."""
        collector = MetricsCollector()
        collector.counter("requests_total", 100)
        collector.gauge("active_connections", 5)

        output = collector.export_prometheus()
        assert "requests_total" in output
        assert "active_connections" in output
        assert "# TYPE" in output

    def test_export_json(self):
        """Test JSON format export."""
        collector = MetricsCollector()
        collector.counter("test", 1)

        data = collector.export_json()
        assert "test" in data
        assert len(data["test"]) == 1


# ============================================================================
# HealthChecker Tests
# ============================================================================

class TestHealthChecker:
    """Test HealthChecker class."""

    def test_checker_creation(self):
        """Test checker creation."""
        checker = HealthChecker()
        assert checker._checks == {}

    def test_register_check(self):
        """Test health check registration."""
        checker = HealthChecker()

        def check_func():
            return True, "OK"

        checker.register("test_check", check_func, interval=10.0)

        assert "test_check" in checker._checks
        assert checker._checks["test_check"].interval == 10.0

    def test_unregister_check(self):
        """Test health check unregistration."""
        checker = HealthChecker()
        checker.register("test", lambda: (True, "OK"))

        result = checker.unregister("test")
        assert result is True
        assert "test" not in checker._checks

        result = checker.unregister("nonexistent")
        assert result is False

    def test_get_status_single(self):
        """Test getting single check status."""
        checker = HealthChecker()
        checker.register("test", lambda: (True, "OK"))

        # Manually run check
        checker._run_check(checker._checks["test"])

        status = checker.get_status("test")
        assert status["status"] == "healthy"
        assert status["message"] == "OK"

    def test_get_status_all(self):
        """Test getting all check statuses."""
        checker = HealthChecker()
        checker.register("check1", lambda: (True, "OK"))
        checker.register("check2", lambda: (False, "Error"))

        # Manually run checks
        for check in checker._checks.values():
            checker._run_check(check)

        status = checker.get_status()
        assert status["overall"] == "unhealthy"
        assert "check1" in status["checks"]
        assert "check2" in status["checks"]

    def test_check_failure_counting(self):
        """Test consecutive failure counting."""
        checker = HealthChecker()

        call_count = [0]
        def failing_check():
            call_count[0] += 1
            return False, f"Error {call_count[0]}"

        checker.register("failing", failing_check)

        # Run check multiple times
        for _ in range(5):
            checker._run_check(checker._checks["failing"])

        status = checker.get_status("failing")
        assert status["consecutive_failures"] == 5

    def test_check_degraded_status(self):
        """Test degraded status after some failures."""
        checker = HealthChecker()

        failure_count = [0]
        def sometimes_failing():
            failure_count[0] += 1
            return failure_count[0] > 2, "OK" if failure_count[0] > 2 else "Error"

        checker.register("sometimes", sometimes_failing)

        # First two failures should result in degraded
        checker._run_check(checker._checks["sometimes"])
        checker._run_check(checker._checks["sometimes"])

        status = checker.get_status("sometimes")
        assert status["status"] == "degraded"


# ============================================================================
# AlertManager Tests
# ============================================================================

class TestAlertManager:
    """Test AlertManager class."""

    def test_manager_creation(self):
        """Test manager creation."""
        metrics = MetricsCollector()
        manager = AlertManager(metrics, check_interval=30.0)
        assert manager.metrics == metrics
        assert manager.check_interval == 30.0

    def test_add_rule(self):
        """Test adding alert rule."""
        metrics = MetricsCollector()
        manager = AlertManager(metrics)

        rule = AlertRule(
            name="high_cpu",
            metric_name="cpu_percent",
            condition=">",
            threshold=80.0,
            duration=60.0,
            severity="warning",
            message="CPU usage is high",
        )

        manager.add_rule(rule)
        assert "high_cpu" in manager._rules

    def test_remove_rule(self):
        """Test removing alert rule."""
        metrics = MetricsCollector()
        manager = AlertManager(metrics)

        rule = AlertRule(
            name="test",
            metric_name="test",
            condition=">",
            threshold=1.0,
            duration=1.0,
            severity="info",
            message="Test",
        )
        manager.add_rule(rule)

        result = manager.remove_rule("test")
        assert result is True
        assert "test" not in manager._rules

    def test_evaluate_condition(self):
        """Test condition evaluation."""
        metrics = MetricsCollector()
        manager = AlertManager(metrics)

        assert manager._evaluate_condition(100, ">", 80) is True
        assert manager._evaluate_condition(50, ">", 80) is False
        assert manager._evaluate_condition(50, "<", 80) is True
        assert manager._evaluate_condition(80, ">=", 80) is True
        assert manager._evaluate_condition(80, "<=", 80) is True
        assert manager._evaluate_condition(80, "==", 80) is True

    def test_alert_triggering(self):
        """Test alert triggering."""
        metrics = MetricsCollector()
        manager = AlertManager(metrics, check_interval=0.1)

        rule = AlertRule(
            name="high_value",
            metric_name="value",
            condition=">",
            threshold=100.0,
            duration=0.0,  # Immediate
            severity="warning",
            message="Value is too high",
        )
        manager.add_rule(rule)

        # Set metric above threshold
        metrics.gauge("value", 150.0)

        # Evaluate rules
        manager._evaluate_rules()

        # Check that alert was triggered
        alerts = manager.get_alerts(active_only=True)
        assert len(alerts) == 1
        assert alerts[0].rule_name == "high_value"

    def test_alert_resolution(self):
        """Test alert resolution."""
        metrics = MetricsCollector()
        manager = AlertManager(metrics, check_interval=0.1)

        rule = AlertRule(
            name="test",
            metric_name="value",
            condition=">",
            threshold=100.0,
            duration=0.0,
            severity="warning",
            message="Test",
        )
        manager.add_rule(rule)

        # Trigger alert
        metrics.gauge("value", 150.0)
        manager._evaluate_rules()

        # Resolve by bringing value below threshold
        metrics.gauge("value", 50.0)
        manager._evaluate_rules()

        # Alert should be resolved
        alerts = manager.get_alerts(active_only=True)
        assert len(alerts) == 0

    def test_acknowledge_alert(self):
        """Test alert acknowledgment."""
        metrics = MetricsCollector()
        manager = AlertManager(metrics, check_interval=0.1)

        rule = AlertRule(
            name="test",
            metric_name="value",
            condition=">",
            threshold=100.0,
            duration=0.0,
            severity="warning",
            message="Test",
        )
        manager.add_rule(rule)

        # Trigger alert
        metrics.gauge("value", 150.0)
        manager._evaluate_rules()

        alerts = manager.get_alerts(active_only=True)
        alert_id = alerts[0].id

        # Acknowledge
        result = manager.acknowledge_alert(alert_id, "admin")
        assert result is True

        alert = manager._alerts[alert_id]
        assert alert.acknowledged is True
        assert alert.acknowledged_by == "admin"


# ============================================================================
# SystemMonitor Tests
# ============================================================================

class TestSystemMonitor:
    """Test SystemMonitor class."""

    def test_monitor_creation(self):
        """Test monitor creation."""
        monitor = SystemMonitor()
        assert monitor.metrics is not None
        assert monitor.health is not None
        assert monitor.alerts is not None

    def test_get_overview(self):
        """Test getting monitor overview."""
        monitor = SystemMonitor()

        overview = monitor.get_overview()
        assert "health" in overview
        assert "alerts" in overview
        assert "metrics" in overview


# ============================================================================
# Cache Tests
# ============================================================================

class TestCache:
    """Test Cache class."""

    def test_cache_creation(self):
        """Test cache creation."""
        cache = Cache(max_size=100, ttl=60.0)
        assert cache.max_size == 100
        assert cache.ttl == 60.0

    def test_cache_set_get(self):
        """Test cache set and get."""
        cache = Cache()
        cache.set("key", "value")

        assert cache.get("key") == "value"
        assert cache.get("nonexistent") is None

    def test_cache_delete(self):
        """Test cache delete."""
        cache = Cache()
        cache.set("key", "value")
        cache.delete("key")

        assert cache.get("key") is None

    def test_cache_clear(self):
        """Test cache clear."""
        cache = Cache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache = Cache(ttl=0.01)  # Very short TTL
        cache.set("key", "value")

        assert cache.get("key") == "value"

        time.sleep(0.02)  # Wait for expiration
        assert cache.get("key") is None

    def test_cache_size_limit(self):
        """Test cache size limit."""
        cache = Cache(max_size=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Should evict oldest

        # One of the first two should be evicted
        count = sum(1 for k in ["key1", "key2", "key3"] if cache.get(k) is not None)
        assert count == 2

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = Cache()
        cache.set("key", "value")
        cache.get("key")  # Hit
        cache.get("nonexistent")  # Miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1


# ============================================================================
# LRUCache Tests
# ============================================================================

class TestLRUCache:
    """Test LRUCache class."""

    def test_lru_cache_creation(self):
        """Test LRU cache creation."""
        cache = LRUCache(capacity=100)
        assert cache.capacity == 100

    def test_lru_cache_get_set(self):
        """Test LRU cache get and set."""
        cache = LRUCache(capacity=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"

    def test_lru_eviction(self):
        """Test LRU eviction policy."""
        cache = LRUCache(capacity=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.get("key1")  # Make key1 most recently used
        cache.set("key3", "value3")  # Should evict key2

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"


# ============================================================================
# Cached Decorator Tests
# ============================================================================

class TestCachedDecorator:
    """Test cached decorator."""

    def test_cached_function(self):
        """Test cached function."""
        call_count = [0]

        @cached(ttl=60.0)
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count[0] == 1  # Function called only once


# ============================================================================
# RateLimiter Tests
# ============================================================================

class TestRateLimiter:
    """Test RateLimiter class."""

    def test_limiter_creation(self):
        """Test limiter creation."""
        limiter = RateLimiter(max_requests=10, window_seconds=60.0)
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 60.0

    def test_allow_within_limit(self):
        """Test allowing requests within limit."""
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)

        for _ in range(5):
            assert limiter.allow("user1") is True

    def test_deny_over_limit(self):
        """Test denying requests over limit."""
        limiter = RateLimiter(max_requests=2, window_seconds=60.0)

        limiter.allow("user1")
        limiter.allow("user1")
        assert limiter.allow("user1") is False

    def test_separate_limits_per_key(self):
        """Test separate rate limits per key."""
        limiter = RateLimiter(max_requests=2, window_seconds=60.0)

        # User 1 uses their limit
        limiter.allow("user1")
        limiter.allow("user1")
        assert limiter.allow("user1") is False

        # User 2 still has their limit
        assert limiter.allow("user2") is True
        assert limiter.allow("user2") is True
        assert limiter.allow("user2") is False

    def test_window_reset(self):
        """Test rate limit window reset."""
        limiter = RateLimiter(max_requests=1, window_seconds=0.01)

        assert limiter.allow("user1") is True
        assert limiter.allow("user1") is False

        time.sleep(0.02)  # Wait for window to reset
        assert limiter.allow("user1") is True


# ============================================================================
# ConcurrencyLimiter Tests
# ============================================================================

class TestConcurrencyLimiter:
    """Test ConcurrencyLimiter class."""

    def test_limiter_creation(self):
        """Test limiter creation."""
        limiter = ConcurrencyLimiter(max_concurrent=5)
        assert limiter.max_concurrent == 5

    def test_acquire_release(self):
        """Test acquiring and releasing slots."""
        limiter = ConcurrencyLimiter(max_concurrent=2)

        assert limiter.acquire("task1") is True
        assert limiter.acquire("task2") is True
        assert limiter.acquire("task3") is False  # Over limit

        limiter.release("task1")
        assert limiter.acquire("task3") is True

    def test_context_manager(self):
        """Test context manager usage."""
        limiter = ConcurrencyLimiter(max_concurrent=1)

        with limiter.acquire_context("task1") as acquired:
            assert acquired is True
            # While holding the slot, another acquire should fail
            assert limiter.acquire("task2") is False

        # After release, should be able to acquire again
        assert limiter.acquire("task2") is True


# ============================================================================
# WorkerPool Tests
# ============================================================================

class TestWorkerPool:
    """Test WorkerPool class."""

    @pytest.mark.asyncio
    async def test_pool_creation(self):
        """Test pool creation."""
        pool = WorkerPool(num_workers=2)
        assert pool.num_workers == 2

    @pytest.mark.asyncio
    async def test_submit_task(self):
        """Test submitting task to pool."""
        pool = WorkerPool(num_workers=1)
        await pool.start()

        async def task():
            return "result"

        result = await pool.submit(task, priority=TaskPriority.NORMAL)
        assert result == "result"

        await pool.stop()

    @pytest.mark.asyncio
    async def test_submit_multiple_tasks(self):
        """Test submitting multiple tasks."""
        pool = WorkerPool(num_workers=2)
        await pool.start()

        results = []
        for i in range(5):
            async def task(i=i):
                return i
            result = await pool.submit(task)
            results.append(result)

        assert sorted(results) == [0, 1, 2, 3, 4]

        await pool.stop()

    @pytest.mark.asyncio
    async def test_task_priority(self):
        """Test task priority ordering."""
        pool = WorkerPool(num_workers=1)
        await pool.start()

        execution_order = []

        async def low_priority_task():
            execution_order.append("low")
            return "low"

        async def high_priority_task():
            execution_order.append("high")
            return "high"

        # Submit low priority first
        await pool.submit(low_priority_task, priority=TaskPriority.LOW)
        # Then high priority
        await pool.submit(high_priority_task, priority=TaskPriority.HIGH)

        # Give some time for processing
        await asyncio.sleep(0.1)

        await pool.stop()

    @pytest.mark.asyncio
    async def test_pool_metrics(self):
        """Test pool metrics."""
        pool = WorkerPool(num_workers=2)
        await pool.start()

        async def task():
            await asyncio.sleep(0.01)
            return "done"

        await pool.submit(task)

        metrics = pool.get_metrics()
        assert "tasks_submitted" in metrics
        assert "tasks_completed" in metrics

        await pool.stop()


# ============================================================================
# Integration Tests
# ============================================================================

class TestPerformanceIntegration:
    """Integration tests for performance module."""

    def test_full_monitoring_setup(self):
        """Test full monitoring setup."""
        monitor = SystemMonitor()

        # Register a health check
        monitor.health.register("test", lambda: (True, "OK"))

        # Record some metrics
        monitor.metrics.counter("requests", 100)
        monitor.metrics.gauge("active_users", 50)

        # Get overview
        overview = monitor.get_overview()
        assert "health" in overview
        assert "alerts" in overview
        assert "metrics" in overview

    def test_metrics_to_alerts_integration(self):
        """Test metrics and alerts integration."""
        metrics = MetricsCollector()
        alerts = AlertManager(metrics, check_interval=0.1)

        # Add alert rule
        rule = AlertRule(
            name="high_requests",
            metric_name="requests",
            condition=">",
            threshold=100.0,
            duration=0.0,
            severity="warning",
            message="Too many requests",
        )
        alerts.add_rule(rule)

        # Trigger alert
        metrics.counter("requests", 150)
        alerts._evaluate_rules()

        active_alerts = alerts.get_alerts(active_only=True)
        assert len(active_alerts) == 1

    def test_cache_with_rate_limiter(self):
        """Test cache with rate limiter integration."""
        cache = Cache()
        limiter = RateLimiter(max_requests=10, window_seconds=60.0)

        def get_data(key):
            # Check rate limit
            if not limiter.allow("user1"):
                raise Exception("Rate limit exceeded")

            # Check cache
            value = cache.get(key)
            if value is not None:
                return value

            # Compute and cache
            value = f"data_for_{key}"
            cache.set(key, value)
            return value

        # First call should work
        assert get_data("key1") == "data_for_key1"

        # Second call should use cache
        assert get_data("key1") == "data_for_key1"


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_record_metric(self):
        """Test record_metric function."""
        record_metric("test_metric", 100.0, MetricType.GAUGE)

        monitor = get_monitor()
        latest = monitor.metrics.get_latest("test_metric")
        assert latest is not None
        assert latest.value == 100.0

    def test_register_health_check(self):
        """Test register_health_check function."""
        register_health_check("test_check", lambda: (True, "OK"), interval=30.0)

        monitor = get_monitor()
        assert "test_check" in monitor.health._checks

    def test_add_alert_rule(self):
        """Test add_alert_rule function."""
        rule = AlertRule(
            name="test_alert",
            metric_name="test",
            condition=">",
            threshold=1.0,
            duration=1.0,
            severity="info",
            message="Test alert",
        )
        add_alert_rule(rule)

        monitor = get_monitor()
        assert "test_alert" in monitor.alerts._rules
