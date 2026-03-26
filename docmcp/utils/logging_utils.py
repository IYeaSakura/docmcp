"""
Logging utilities for DocMCP.

Provides structured logging with support for:
    - JSON formatting
    - Contextual logging
    - Trace ID propagation
    - Log level configuration
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredLogFormatter(logging.Formatter):
    """
    Structured JSON log formatter.
    
    Formats log records as JSON for easy parsing and analysis.
    
    Example output:
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "level": "INFO",
            "logger": "docmcp.core.engine",
            "message": "Processing started",
            "context": {"document_id": "doc-123"}
        }
    """
    
    def __init__(
        self,
        include_extra: bool = True,
        include_stacktrace: bool = True,
    ):
        super().__init__()
        self.include_extra = include_extra
        self.include_stacktrace = include_stacktrace
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add source location
        log_data["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }
        
        # Add extra fields
        if self.include_extra:
            extra = self._extract_extra(record)
            if extra:
                log_data["extra"] = extra
        
        # Add exception info
        if record.exc_info and self.include_stacktrace:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add trace ID if available
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id
        
        return json.dumps(log_data, default=str)
    
    def _extract_extra(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Extract extra fields from log record."""
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "getMessage",
        }
        
        extra = {}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                extra[key] = value
        
        return extra


class ContextualLogger:
    """
    Logger with context support.
    
    Allows adding context fields that will be included in all log messages.
    
    Example:
        >>> logger = ContextualLogger(logging.getLogger("test"))
        >>> logger = logger.bind(request_id="req-123", user_id="user-456")
        >>> logger.info("Processing started")  # Includes request_id and user_id
    """
    
    def __init__(
        self,
        logger: logging.Logger,
        context: Optional[Dict[str, Any]] = None,
    ):
        self._logger = logger
        self._context = context or {}
    
    def bind(self, **kwargs) -> ContextualLogger:
        """Create new logger with additional context."""
        new_context = {**self._context, **kwargs}
        return ContextualLogger(self._logger, new_context)
    
    def _log(
        self,
        level: int,
        msg: str,
        *args,
        **kwargs,
    ) -> None:
        """Internal log method with context."""
        extra = kwargs.pop("extra", {})
        extra.update(self._context)
        kwargs["extra"] = extra
        self._logger.log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message."""
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message."""
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message."""
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log exception message."""
        kwargs["exc_info"] = True
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, msg, *args, **kwargs)


def setup_logging(
    level: str = "INFO",
    format: str = "structured",
    output: str = "stdout",
) -> None:
    """
    Setup logging configuration.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Log format (structured, simple, detailed)
        output: Output destination (stdout, stderr, or file path)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    if format == "structured":
        formatter = StructuredLogFormatter()
    elif format == "simple":
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    elif format == "detailed":
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s"
        )
    else:
        formatter = logging.Formatter(format)
    
    # Create handler
    if output == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    elif output == "stderr":
        handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.FileHandler(output)
    
    handler.setFormatter(formatter)
    handler.setLevel(log_level)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []
    root_logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str, context: Optional[Dict[str, Any]] = None) -> ContextualLogger:
    """
    Get a contextual logger.
    
    Args:
        name: Logger name
        context: Initial context
        
    Returns:
        ContextualLogger instance
    """
    logger = logging.getLogger(name)
    return ContextualLogger(logger, context)


# Global trace ID context
_trace_id: Optional[str] = None


def get_trace_id() -> str:
    """Get current trace ID or generate new one."""
    global _trace_id
    if _trace_id is None:
        _trace_id = str(uuid.uuid4())
    return _trace_id


def set_trace_id(trace_id: str) -> None:
    """Set current trace ID."""
    global _trace_id
    _trace_id = trace_id


def clear_trace_id() -> None:
    """Clear current trace ID."""
    global _trace_id
    _trace_id = None
