"""
DocMCP 审计日志模块

提供操作日志记录、安全事件记录、日志轮转和日志分析功能。
"""

import os
import json
import gzip
import shutil
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
from collections import deque
import queue
import hashlib


class AuditLevel(Enum):
    """审计日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SECURITY = "SECURITY"


class AuditEventType(Enum):
    """审计事件类型"""
    # 认证事件
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    TOKEN_REFRESH = "token_refresh"

    # 授权事件
    ACCESS_DENIED = "access_denied"
    PERMISSION_GRANTED = "permission_granted"
    ROLE_CHANGED = "role_changed"

    # 数据事件
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    DOWNLOAD = "download"
    UPLOAD = "upload"

    # 执行事件
    EXECUTE = "execute"
    EXECUTE_SANDBOX = "execute_sandbox"

    # 系统事件
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    CONFIG_CHANGE = "config_change"
    BACKUP = "backup"
    RESTORE = "restore"

    # 安全事件
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    THREAT_DETECTED = "threat_detected"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"


@dataclass
class AuditEvent:
    """审计事件"""
    event_type: AuditEventType
    timestamp: datetime
    level: AuditLevel
    user_id: Optional[str] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    action: Optional[str] = None
    status: str = "success"  # success, failure, pending
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'user_id': self.user_id,
            'username': self.username,
            'ip_address': self.ip_address,
            'resource_id': self.resource_id,
            'resource_type': self.resource_type,
            'action': self.action,
            'status': self.status,
            'message': self.message,
            'details': self.details,
            'session_id': self.session_id,
            'request_id': self.request_id,
            'user_agent': self.user_agent,
        }

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        """从字典创建事件"""
        return cls(
            event_type=AuditEventType(data.get('event_type', 'read')),
            timestamp=datetime.fromisoformat(data['timestamp']),
            level=AuditLevel(data.get('level', 'INFO')),
            user_id=data.get('user_id'),
            username=data.get('username'),
            ip_address=data.get('ip_address'),
            resource_id=data.get('resource_id'),
            resource_type=data.get('resource_type'),
            action=data.get('action'),
            status=data.get('status', 'success'),
            message=data.get('message', ''),
            details=data.get('details', {}),
            session_id=data.get('session_id'),
            request_id=data.get('request_id'),
            user_agent=data.get('user_agent'),
        )


@dataclass
class AuditConfig:
    """审计配置"""
    log_dir: str = "/var/log/docmcp"
    log_file: str = "audit.log"
    log_level: AuditLevel = AuditLevel.INFO

    # 日志轮转
    max_file_size_mb: int = 100
    max_backup_count: int = 10
    rotation_interval: str = "midnight"  # size, time, midnight

    # 保留策略
    retention_days: int = 90
    archive_enabled: bool = True
    archive_dir: str = "/var/log/docmcp/archive"
    compress_archives: bool = True

    # 事件过滤
    log_all_events: bool = False
    logged_event_types: List[AuditEventType] = field(default_factory=lambda: [
        AuditEventType.LOGIN,
        AuditEventType.LOGOUT,
        AuditEventType.LOGIN_FAILED,
        AuditEventType.ACCESS_DENIED,
        AuditEventType.CREATE,
        AuditEventType.UPDATE,
        AuditEventType.DELETE,
        AuditEventType.EXECUTE,
        AuditEventType.DOWNLOAD,
        AuditEventType.UPLOAD,
        AuditEventType.THREAT_DETECTED,
        AuditEventType.SUSPICIOUS_ACTIVITY,
    ])

    # 异步日志
    async_logging: bool = True
    queue_size: int = 10000
    batch_size: int = 100
    flush_interval: float = 5.0

    # 输出格式
    output_format: str = "json"  # json, text
    include_stack_trace: bool = False


class LogRotator:
    """日志轮转器"""

    def __init__(
        self,
        log_file: str,
        max_size_mb: int = 100,
        max_backup_count: int = 10,
        compress: bool = True
    ):
        """初始化日志轮转器

        Args:
            log_file: 日志文件路径
            max_size_mb: 最大文件大小(MB)
            max_backup_count: 最大备份数量
            compress: 是否压缩备份
        """
        self.log_file = Path(log_file)
        self.max_size = max_size_mb * 1024 * 1024
        self.max_backup_count = max_backup_count
        self.compress = compress

    def should_rotate(self) -> bool:
        """检查是否需要轮转"""
        if not self.log_file.exists():
            return False
        return self.log_file.stat().st_size >= self.max_size

    def rotate(self) -> bool:
        """执行日志轮转

        Returns:
            bool: 是否成功
        """
        if not self.should_rotate():
            return True

        try:
            # 删除最旧的备份
            oldest_backup = self.log_file.parent / f"{self.log_file.name}.{self.max_backup_count}"
            if self.compress:
                oldest_backup = oldest_backup.with_suffix('.gz')
            if oldest_backup.exists():
                oldest_backup.unlink()

            # 移动现有备份
            for i in range(self.max_backup_count - 1, 0, -1):
                src = self.log_file.parent / f"{self.log_file.name}.{i}"
                if self.compress:
                    src = src.with_suffix('.gz')
                dst = self.log_file.parent / f"{self.log_file.name}.{i + 1}"
                if self.compress:
                    dst = dst.with_suffix('.gz')

                if src.exists():
                    src.rename(dst)

            # 移动当前日志文件
            backup = self.log_file.parent / f"{self.log_file.name}.1"
            self.log_file.rename(backup)

            # 压缩备份
            if self.compress:
                compressed = backup.with_suffix('.gz')
                with open(backup, 'rb') as f_in:
                    with gzip.open(compressed, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup.unlink()

            return True

        except Exception as e:
            logging.error(f"Log rotation failed: {e}")
            return False


class AuditLogger:
    """审计日志记录器"""

    def __init__(self, config: Optional[AuditConfig] = None):
        """初始化审计日志记录器

        Args:
            config: 审计配置
        """
        self.config = config or AuditConfig()
        self._lock = threading.RLock()

        # 创建日志目录
        Path(self.config.log_dir).mkdir(parents=True, exist_ok=True)
        if self.config.archive_enabled:
            Path(self.config.archive_dir).mkdir(parents=True, exist_ok=True)

        # 日志文件路径
        self.log_path = Path(self.config.log_dir) / self.config.log_file

        # 日志轮转器
        self.rotator = LogRotator(
            str(self.log_path),
            self.config.max_file_size_mb,
            self.config.max_backup_count,
            self.config.compress_archives
        )

        # 异步日志队列
        if self.config.async_logging:
            self._queue: queue.Queue = queue.Queue(maxsize=self.config.queue_size)
            self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self._worker_thread.start()
            self._flush_event = threading.Event()

        # 内存缓冲区（用于快速查询）
        self._buffer: deque = deque(maxlen=1000)

        # 统计信息
        self._stats = {
            'total_events': 0,
            'events_by_type': {},
            'events_by_level': {},
        }

    def log(
        self,
        event_type: AuditEventType,
        level: AuditLevel = AuditLevel.INFO,
        message: str = "",
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AuditEvent:
        """记录审计事件

        Args:
            event_type: 事件类型
            level: 日志级别
            message: 消息
            user_id: 用户ID
            username: 用户名
            ip_address: IP地址
            resource_id: 资源ID
            resource_type: 资源类型
            action: 操作
            status: 状态
            details: 详细信息

        Returns:
            AuditEvent: 审计事件
        """
        # 检查是否需要记录
        if not self._should_log(event_type, level):
            return None

        # 创建事件
        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            level=level,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            resource_id=resource_id,
            resource_type=resource_type,
            action=action,
            status=status,
            message=message,
            details=details or {},
            **kwargs
        )

        # 异步或同步记录
        if self.config.async_logging:
            try:
                self._queue.put_nowait(event)
            except queue.Full:
                # 队列满时直接写入
                self._write_event(event)
        else:
            self._write_event(event)

        # 更新统计
        self._update_stats(event)

        return event

    def _should_log(self, event_type: AuditEventType, level: AuditLevel) -> bool:
        """检查是否应该记录事件"""
        # 检查级别
        level_order = {
            AuditLevel.DEBUG: 0,
            AuditLevel.INFO: 1,
            AuditLevel.WARNING: 2,
            AuditLevel.ERROR: 3,
            AuditLevel.CRITICAL: 4,
            AuditLevel.SECURITY: 5,
        }

        if level_order[level] < level_order[self.config.log_level]:
            return False

        # 检查事件类型
        if self.config.log_all_events:
            return True

        return event_type in self.config.logged_event_types

    def _write_event(self, event: AuditEvent) -> None:
        """写入事件到日志文件"""
        with self._lock:
            # 检查是否需要轮转
            if self.rotator.should_rotate():
                self.rotator.rotate()

            # 格式化输出
            if self.config.output_format == "json":
                line = event.to_json() + "\n"
            else:
                line = self._format_text(event) + "\n"

            # 写入文件
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(line)

            # 添加到内存缓冲区
            self._buffer.append(event)

    def _format_text(self, event: AuditEvent) -> str:
        """格式化为文本格式"""
        return (
            f"[{event.timestamp.isoformat()}] "
            f"{event.level.value} "
            f"{event.event_type.value} "
            f"user={event.username or 'anonymous'} "
            f"ip={event.ip_address or 'unknown'} "
            f"action={event.action or 'none'} "
            f"status={event.status} "
            f"msg={event.message}"
        )

    def _process_queue(self) -> None:
        """处理异步日志队列"""
        batch: List[AuditEvent] = []
        last_flush = datetime.utcnow()

        while True:
            try:
                # 等待事件或超时
                event = self._queue.get(timeout=self.config.flush_interval)
                batch.append(event)

                # 批量写入
                if len(batch) >= self.config.batch_size:
                    self._write_batch(batch)
                    batch.clear()
                    last_flush = datetime.utcnow()

            except queue.Empty:
                # 超时，刷新剩余事件
                if batch:
                    self._write_batch(batch)
                    batch.clear()
                last_flush = datetime.utcnow()

    def _write_batch(self, events: List[AuditEvent]) -> None:
        """批量写入事件"""
        with self._lock:
            # 检查轮转
            if self.rotator.should_rotate():
                self.rotator.rotate()

            # 批量写入
            with open(self.log_path, 'a', encoding='utf-8') as f:
                for event in events:
                    if self.config.output_format == "json":
                        f.write(event.to_json() + "\n")
                    else:
                        f.write(self._format_text(event) + "\n")

                    self._buffer.append(event)

    def _update_stats(self, event: AuditEvent) -> None:
        """更新统计信息"""
        self._stats['total_events'] += 1

        event_type = event.event_type.value
        self._stats['events_by_type'][event_type] = \
            self._stats['events_by_type'].get(event_type, 0) + 1

        level = event.level.value
        self._stats['events_by_level'][level] = \
            self._stats['events_by_level'].get(level, 0) + 1

    def flush(self) -> None:
        """刷新日志"""
        if self.config.async_logging:
            # 等待队列处理完成
            self._queue.join()

    def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        level: Optional[AuditLevel] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """查询日志

        Args:
            start_time: 开始时间
            end_time: 结束时间
            event_types: 事件类型列表
            user_id: 用户ID
            resource_id: 资源ID
            level: 日志级别
            limit: 返回数量限制

        Returns:
            List[AuditEvent]: 事件列表
        """
        results = []

        # 从内存缓冲区查询
        for event in reversed(self._buffer):
            if self._match_event(event, start_time, end_time, event_types, user_id, resource_id, level):
                results.append(event)
                if len(results) >= limit:
                    return results

        # 从文件查询
        if self.log_path.exists():
            with open(self.log_path, 'r', encoding='utf-8') as f:
                for line in reversed(f.readlines()):
                    try:
                        event = AuditEvent.from_dict(json.loads(line.strip()))
                        if self._match_event(event, start_time, end_time, event_types, user_id, resource_id, level):
                            results.append(event)
                            if len(results) >= limit:
                                return results
                    except (json.JSONDecodeError, KeyError):
                        continue

        return results

    def _match_event(
        self,
        event: AuditEvent,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        event_types: Optional[List[AuditEventType]],
        user_id: Optional[str],
        resource_id: Optional[str],
        level: Optional[AuditLevel]
    ) -> bool:
        """检查事件是否匹配查询条件"""
        if start_time and event.timestamp < start_time:
            return False
        if end_time and event.timestamp > end_time:
            return False
        if event_types and event.event_type not in event_types:
            return False
        if user_id and event.user_id != user_id:
            return False
        if resource_id and event.resource_id != resource_id:
            return False
        if level and event.level != level:
            return False
        return True

    def archive_old_logs(self, days: Optional[int] = None) -> int:
        """归档旧日志

        Args:
            days: 归档天数之前的日志

        Returns:
            int: 归档的文件数
        """
        days = days or self.config.retention_days
        cutoff = datetime.utcnow() - timedelta(days=days)

        archived = 0

        # 归档日志文件
        for log_file in Path(self.config.log_dir).glob("*.log*"):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff:
                    archive_path = Path(self.config.archive_dir) / log_file.name

                    if self.config.compress_archives and not log_file.suffix == '.gz':
                        with open(log_file, 'rb') as f_in:
                            with gzip.open(f"{archive_path}.gz", 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                    else:
                        shutil.move(str(log_file), str(archive_path))

                    archived += 1
            except Exception as e:
                logging.error(f"Failed to archive {log_file}: {e}")

        return archived

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_events': self._stats['total_events'],
            'events_by_type': self._stats['events_by_type'].copy(),
            'events_by_level': self._stats['events_by_level'].copy(),
            'buffer_size': len(self._buffer),
            'queue_size': self._queue.qsize() if self.config.async_logging else 0,
        }

    def close(self) -> None:
        """关闭日志记录器"""
        self.flush()


# 便捷函数
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(config: Optional[AuditConfig] = None) -> AuditLogger:
    """获取全局审计日志记录器"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(config)
    return _audit_logger


def log_event(
    event_type: AuditEventType,
    level: AuditLevel = AuditLevel.INFO,
    message: str = "",
    **kwargs
) -> AuditEvent:
    """记录事件的便捷函数"""
    logger = get_audit_logger()
    return logger.log(event_type, level, message, **kwargs)


def log_login(user_id: str, username: str, ip_address: str, success: bool = True) -> AuditEvent:
    """记录登录事件"""
    event_type = AuditEventType.LOGIN if success else AuditEventType.LOGIN_FAILED
    level = AuditLevel.INFO if success else AuditLevel.WARNING
    return log_event(
        event_type=event_type,
        level=level,
        message=f"Login {'successful' if success else 'failed'} for {username}",
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        status="success" if success else "failure"
    )


def log_access_denied(
    user_id: str,
    resource_id: str,
    action: str,
    ip_address: Optional[str] = None
) -> AuditEvent:
    """记录访问拒绝事件"""
    return log_event(
        event_type=AuditEventType.ACCESS_DENIED,
        level=AuditLevel.WARNING,
        message=f"Access denied to {resource_id} for action {action}",
        user_id=user_id,
        resource_id=resource_id,
        action=action,
        ip_address=ip_address,
        status="failure"
    )
