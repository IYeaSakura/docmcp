"""
DocMCP 监控指标模块

提供性能指标收集、健康检查、告警机制和指标导出功能。
"""

import time
import json
import threading
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"      # 累加计数器
    GAUGE = "gauge"          # 瞬时值
    HISTOGRAM = "histogram"  # 直方图
    SUMMARY = "summary"      # 摘要


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'value': self.value,
            'type': self.metric_type.value,
            'timestamp': self.timestamp,
            'labels': self.labels,
        }


@dataclass
class HealthCheck:
    """健康检查"""
    name: str
    check_func: Callable[[], tuple[bool, str]]
    interval: float = 30.0
    timeout: float = 5.0
    enabled: bool = True
    last_check: Optional[datetime] = None
    last_status: HealthStatus = HealthStatus.UNKNOWN
    last_message: str = ""
    consecutive_failures: int = 0


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric_name: str
    condition: str  # >, <, ==, >=, <=
    threshold: float
    duration: float  # 持续时间(秒)
    severity: str  # info, warning, critical
    message: str
    enabled: bool = True
    
    # 状态
    triggered_at: Optional[float] = None
    resolved_at: Optional[float] = None
    is_triggered: bool = False


@dataclass
class Alert:
    """告警"""
    id: str
    rule_name: str
    severity: str
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None


class MetricsCollector:
    """指标收集器
    
    收集和存储各种性能指标，支持：
    - 多种指标类型
    - 标签支持
    - 数据保留
    - 聚合查询
    """
    
    def __init__(
        self,
        max_data_points: int = 10000,
        retention_hours: int = 24
    ):
        """初始化指标收集器
        
        Args:
            max_data_points: 每个指标最大数据点数
            retention_hours: 数据保留时间(小时)
        """
        self.max_data_points = max_data_points
        self.retention_hours = retention_hours
        
        # 指标存储
        self._metrics: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_data_points)
        )
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        
        # 锁
        self._lock = threading.RLock()
        
        # 启动清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def counter(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """增加计数器
        
        Args:
            name: 指标名称
            value: 增加值
            labels: 标签
        """
        with self._lock:
            label_key = self._labels_to_key(labels or {})
            full_name = f"{name}{label_key}"
            
            self._counters[full_name] += value
            
            metric = MetricValue(
                name=name,
                value=self._counters[full_name],
                metric_type=MetricType.COUNTER,
                timestamp=time.time(),
                labels=labels or {}
            )
            
            self._metrics[name].append(metric)
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """设置仪表盘值
        
        Args:
            name: 指标名称
            value: 值
            labels: 标签
        """
        with self._lock:
            label_key = self._labels_to_key(labels or {})
            full_name = f"{name}{label_key}"
            
            self._gauges[full_name] = value
            
            metric = MetricValue(
                name=name,
                value=value,
                metric_type=MetricType.GAUGE,
                timestamp=time.time(),
                labels=labels or {}
            )
            
            self._metrics[name].append(metric)
    
    def histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None
    ) -> None:
        """记录直方图值
        
        Args:
            name: 指标名称
            value: 值
            labels: 标签
            buckets: 分桶边界
        """
        buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        
        with self._lock:
            # 记录原始值
            metric = MetricValue(
                name=name,
                value=value,
                metric_type=MetricType.HISTOGRAM,
                timestamp=time.time(),
                labels=labels or {}
            )
            
            self._metrics[name].append(metric)
            
            # 记录分桶
            for bucket in buckets:
                bucket_name = f"{name}_bucket"
                bucket_labels = dict(labels or {})
                bucket_labels['le'] = str(bucket)
                
                if value <= bucket:
                    self.counter(bucket_name, 1, bucket_labels)
    
    def summary(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """记录摘要值
        
        Args:
            name: 指标名称
            value: 值
            labels: 标签
        """
        with self._lock:
            metric = MetricValue(
                name=name,
                value=value,
                metric_type=MetricType.SUMMARY,
                timestamp=time.time(),
                labels=labels or {}
            )
            
            self._metrics[name].append(metric)
    
    def _labels_to_key(self, labels: Dict[str, str]) -> str:
        """将标签转换为键"""
        if not labels:
            return ""
        return "{" + ",".join(f'{k}="{v}"' for k, v in sorted(labels.items())) + "}"
    
    def get_metric(
        self,
        name: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> List[MetricValue]:
        """获取指标数据
        
        Args:
            name: 指标名称
            start_time: 开始时间
            end_time: 结束时间
            labels: 标签过滤
            
        Returns:
            List[MetricValue]: 指标值列表
        """
        with self._lock:
            metrics = self._metrics.get(name, deque())
            
            result = []
            for metric in metrics:
                if start_time and metric.timestamp < start_time:
                    continue
                if end_time and metric.timestamp > end_time:
                    continue
                if labels and not all(
                    metric.labels.get(k) == v for k, v in labels.items()
                ):
                    continue
                result.append(metric)
            
            return result
    
    def get_latest(self, name: str) -> Optional[MetricValue]:
        """获取最新指标值"""
        with self._lock:
            metrics = self._metrics.get(name)
            if metrics:
                return metrics[-1]
            return None
    
    def get_stats(self, name: str) -> Optional[Dict[str, float]]:
        """获取指标统计信息"""
        with self._lock:
            metrics = self._metrics.get(name, [])
            if not metrics:
                return None
            
            values = [m.value for m in metrics]
            
            return {
                'count': len(values),
                'sum': sum(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'last': values[-1],
            }
    
    def _cleanup_loop(self) -> None:
        """清理循环"""
        while True:
            try:
                self._cleanup_old_data()
                time.sleep(3600)  # 每小时清理一次
            except Exception as e:
                logger.error(f"Metrics cleanup error: {e}")
                time.sleep(60)
    
    def _cleanup_old_data(self) -> None:
        """清理过期数据"""
        cutoff = time.time() - (self.retention_hours * 3600)
        
        with self._lock:
            for name, metrics in list(self._metrics.items()):
                while metrics and metrics[0].timestamp < cutoff:
                    metrics.popleft()
    
    def export_prometheus(self) -> str:
        """导出Prometheus格式"""
        lines = []
        
        with self._lock:
            # 计数器
            for name, value in self._counters.items():
                lines.append(f"# TYPE {name.split('{')[0]} counter")
                lines.append(f"{name} {value}")
            
            # 仪表盘
            for name, value in self._gauges.items():
                lines.append(f"# TYPE {name.split('{')[0]} gauge")
                lines.append(f"{name} {value}")
        
        return "\n".join(lines)
    
    def export_json(self) -> Dict[str, Any]:
        """导出JSON格式"""
        with self._lock:
            return {
                name: [m.to_dict() for m in metrics]
                for name, metrics in self._metrics.items()
            }


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        """初始化健康检查器"""
        self._checks: Dict[str, HealthCheck] = {}
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def register(
        self,
        name: str,
        check_func: Callable[[], tuple[bool, str]],
        interval: float = 30.0,
        timeout: float = 5.0
    ) -> None:
        """注册健康检查
        
        Args:
            name: 检查名称
            check_func: 检查函数，返回(是否健康, 消息)
            interval: 检查间隔
            timeout: 超时时间
        """
        with self._lock:
            self._checks[name] = HealthCheck(
                name=name,
                check_func=check_func,
                interval=interval,
                timeout=timeout
            )
    
    def unregister(self, name: str) -> bool:
        """注销健康检查"""
        with self._lock:
            return self._checks.pop(name, None) is not None
    
    def start(self) -> None:
        """启动健康检查"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        
        logger.info("Health checker started")
    
    def stop(self) -> None:
        """停止健康检查"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("Health checker stopped")
    
    def _check_loop(self) -> None:
        """检查循环"""
        while self._running:
            with self._lock:
                checks = list(self._checks.values())
            
            for check in checks:
                if not check.enabled:
                    continue
                
                if check.last_check:
                    elapsed = (datetime.utcnow() - check.last_check).total_seconds()
                    if elapsed < check.interval:
                        continue
                
                self._run_check(check)
            
            time.sleep(1)
    
    def _run_check(self, check: HealthCheck) -> None:
        """执行单个检查"""
        try:
            healthy, message = check.check_func()
            
            check.last_check = datetime.utcnow()
            check.last_message = message
            
            if healthy:
                check.last_status = HealthStatus.HEALTHY
                check.consecutive_failures = 0
            else:
                check.consecutive_failures += 1
                if check.consecutive_failures >= 3:
                    check.last_status = HealthStatus.UNHEALTHY
                else:
                    check.last_status = HealthStatus.DEGRADED
                    
        except Exception as e:
            check.last_check = datetime.utcnow()
            check.last_status = HealthStatus.UNHEALTHY
            check.last_message = str(e)
            check.consecutive_failures += 1
            
            logger.error(f"Health check {check.name} failed: {e}")
    
    def get_status(self, name: Optional[str] = None) -> Dict[str, Any]:
        """获取健康状态
        
        Args:
            name: 检查名称，None返回所有
            
        Returns:
            Dict: 健康状态
        """
        with self._lock:
            if name:
                check = self._checks.get(name)
                if check:
                    return {
                        'name': check.name,
                        'status': check.last_status.value,
                        'message': check.last_message,
                        'last_check': check.last_check.isoformat() if check.last_check else None,
                        'consecutive_failures': check.consecutive_failures,
                    }
                return {}
            
            # 返回所有检查状态
            checks_status = {}
            overall_status = HealthStatus.HEALTHY
            
            for check in self._checks.values():
                checks_status[check.name] = {
                    'status': check.last_status.value,
                    'message': check.last_message,
                    'last_check': check.last_check.isoformat() if check.last_check else None,
                }
                
                # 更新整体状态
                if check.last_status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif check.last_status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
            
            return {
                'overall': overall_status.value,
                'checks': checks_status,
            }


class AlertManager:
    """告警管理器"""
    
    def __init__(
        self,
        metrics_collector: MetricsCollector,
        check_interval: float = 30.0
    ):
        """初始化告警管理器
        
        Args:
            metrics_collector: 指标收集器
            check_interval: 检查间隔
        """
        self.metrics = metrics_collector
        self.check_interval = check_interval
        
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._handlers: List[Callable[[Alert], None]] = []
        
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则"""
        with self._lock:
            self._rules[rule.name] = rule
    
    def remove_rule(self, name: str) -> bool:
        """移除告警规则"""
        with self._lock:
            return self._rules.pop(name, None) is not None
    
    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """添加告警处理器"""
        with self._lock:
            self._handlers.append(handler)
    
    def start(self) -> None:
        """启动告警管理器"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        
        logger.info("Alert manager started")
    
    def stop(self) -> None:
        """停止告警管理器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("Alert manager stopped")
    
    def _check_loop(self) -> None:
        """检查循环"""
        while self._running:
            try:
                self._evaluate_rules()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Alert check error: {e}")
                time.sleep(5)
    
    def _evaluate_rules(self) -> None:
        """评估告警规则"""
        now = time.time()
        
        with self._lock:
            for rule in self._rules.values():
                if not rule.enabled:
                    continue
                
                # 获取指标值
                latest = self.metrics.get_latest(rule.metric_name)
                if latest is None:
                    continue
                
                value = latest.value
                triggered = self._evaluate_condition(value, rule.condition, rule.threshold)
                
                if triggered:
                    if not rule.is_triggered:
                        # 首次触发
                        rule.triggered_at = now
                        rule.is_triggered = True
                    
                    # 检查持续时间
                    if now - rule.triggered_at >= rule.duration:
                        self._trigger_alert(rule, value)
                else:
                    if rule.is_triggered:
                        # 告警恢复
                        rule.resolved_at = now
                        rule.is_triggered = False
                        self._resolve_alert(rule)
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """评估条件"""
        if condition == '>':
            return value > threshold
        elif condition == '<':
            return value < threshold
        elif condition == '>=':
            return value >= threshold
        elif condition == '<=':
            return value <= threshold
        elif condition == '==':
            return value == threshold
        return False
    
    def _trigger_alert(self, rule: AlertRule, value: float) -> None:
        """触发告警"""
        import uuid
        
        alert_id = str(uuid.uuid4())
        alert = Alert(
            id=alert_id,
            rule_name=rule.name,
            severity=rule.severity,
            message=rule.message,
            metric_name=rule.metric_name,
            metric_value=value,
            threshold=rule.threshold,
            triggered_at=datetime.utcnow()
        )
        
        self._alerts[alert_id] = alert
        
        # 通知处理器
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")
        
        logger.warning(f"Alert triggered: {rule.name} - {rule.message}")
    
    def _resolve_alert(self, rule: AlertRule) -> None:
        """解决告警"""
        # 找到对应的告警并标记为已解决
        for alert in self._alerts.values():
            if alert.rule_name == rule.name and alert.resolved_at is None:
                alert.resolved_at = datetime.utcnow()
                logger.info(f"Alert resolved: {rule.name}")
                break
    
    def get_alerts(
        self,
        active_only: bool = True,
        severity: Optional[str] = None
    ) -> List[Alert]:
        """获取告警列表"""
        with self._lock:
            alerts = list(self._alerts.values())
            
            if active_only:
                alerts = [a for a in alerts if a.resolved_at is None]
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            
            return sorted(alerts, key=lambda a: a.triggered_at, reverse=True)
    
    def acknowledge_alert(self, alert_id: str, user: str) -> bool:
        """确认告警"""
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert:
                alert.acknowledged = True
                alert.acknowledged_by = user
                return True
            return False


class SystemMonitor:
    """系统监控器"""
    
    def __init__(
        self,
        metrics: Optional[MetricsCollector] = None,
        health_checker: Optional[HealthChecker] = None,
        alert_manager: Optional[AlertManager] = None
    ):
        """初始化系统监控器"""
        self.metrics = metrics or MetricsCollector()
        self.health = health_checker or HealthChecker()
        self.alerts = alert_manager or AlertManager(self.metrics)
        
        self._running = False
        self._collect_thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """启动监控"""
        if self._running:
            return
        
        self._running = True
        
        # 启动健康检查
        self.health.start()
        
        # 启动告警管理
        self.alerts.start()
        
        # 启动系统指标收集
        self._collect_thread = threading.Thread(
            target=self._collect_system_metrics,
            daemon=True
        )
        self._collect_thread.start()
        
        logger.info("System monitor started")
    
    def stop(self) -> None:
        """停止监控"""
        self._running = False
        
        self.health.stop()
        self.alerts.stop()
        
        if self._collect_thread:
            self._collect_thread.join(timeout=5)
        
        logger.info("System monitor stopped")
    
    def _collect_system_metrics(self) -> None:
        """收集系统指标"""
        import psutil
        
        while self._running:
            try:
                # CPU使用率
                cpu_percent = psutil.cpu_percent(interval=1)
                self.metrics.gauge('system_cpu_percent', cpu_percent)
                
                # 内存使用
                memory = psutil.virtual_memory()
                self.metrics.gauge('system_memory_percent', memory.percent)
                self.metrics.gauge('system_memory_used_bytes', memory.used)
                self.metrics.gauge('system_memory_available_bytes', memory.available)
                
                # 磁盘使用
                disk = psutil.disk_usage('/')
                self.metrics.gauge('system_disk_percent', disk.percent)
                self.metrics.gauge('system_disk_used_bytes', disk.used)
                self.metrics.gauge('system_disk_free_bytes', disk.free)
                
                # 网络IO
                net_io = psutil.net_io_counters()
                self.metrics.counter('system_network_bytes_sent', net_io.bytes_sent)
                self.metrics.counter('system_network_bytes_recv', net_io.bytes_recv)
                
                # 进程数
                self.metrics.gauge('system_process_count', len(psutil.pids()))
                
            except Exception as e:
                logger.error(f"System metrics collection error: {e}")
            
            time.sleep(30)  # 每30秒收集一次
    
    def get_overview(self) -> Dict[str, Any]:
        """获取监控概览"""
        return {
            'health': self.health.get_status(),
            'alerts': {
                'active': len(self.alerts.get_alerts(active_only=True)),
                'total': len(self.alerts.get_alerts(active_only=False)),
            },
            'metrics': {
                'cpu': self.metrics.get_latest('system_cpu_percent'),
                'memory': self.metrics.get_latest('system_memory_percent'),
                'disk': self.metrics.get_latest('system_disk_percent'),
            }
        }


# 便捷函数
_default_monitor: Optional[SystemMonitor] = None


def get_monitor() -> SystemMonitor:
    """获取默认监控器"""
    global _default_monitor
    if _default_monitor is None:
        _default_monitor = SystemMonitor()
    return _default_monitor


def record_metric(
    name: str,
    value: float,
    metric_type: MetricType = MetricType.GAUGE,
    labels: Optional[Dict[str, str]] = None
) -> None:
    """记录指标的便捷函数"""
    monitor = get_monitor()
    
    if metric_type == MetricType.COUNTER:
        monitor.metrics.counter(name, value, labels)
    elif metric_type == MetricType.GAUGE:
        monitor.metrics.gauge(name, value, labels)
    elif metric_type == MetricType.HISTOGRAM:
        monitor.metrics.histogram(name, value, labels)
    elif metric_type == MetricType.SUMMARY:
        monitor.metrics.summary(name, value, labels)


def register_health_check(
    name: str,
    check_func: Callable[[], tuple[bool, str]],
    interval: float = 30.0
) -> None:
    """注册健康检查的便捷函数"""
    get_monitor().health.register(name, check_func, interval)


def add_alert_rule(rule: AlertRule) -> None:
    """添加告警规则的便捷函数"""
    get_monitor().alerts.add_rule(rule)
