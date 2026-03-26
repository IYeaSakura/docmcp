"""
Utility module for DocMCP.

This module provides common utilities used throughout the DocMCP system,
including:
    - Logging utilities
    - Configuration management
    - Security helpers
    - Async utilities
    - Validation utilities
"""

from __future__ import annotations

from docmcp.utils.logging_utils import (
    setup_logging,
    get_logger,
    StructuredLogFormatter,
)
from docmcp.utils.config import (
    Config,
    ConfigManager,
    load_config,
)
from docmcp.utils.async_utils import (
    AsyncTaskPool,
    RateLimiter,
    retry,
    timeout,
)
from docmcp.utils.security import (
    hash_content,
    generate_id,
    sanitize_filename,
)
from docmcp.utils.validation import (
    validate_email,
    validate_url,
    validate_file_path,
)

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    "StructuredLogFormatter",
    # Config
    "Config",
    "ConfigManager",
    "load_config",
    # Async utilities
    "AsyncTaskPool",
    "RateLimiter",
    "retry",
    "timeout",
    # Security
    "hash_content",
    "generate_id",
    "sanitize_filename",
    # Validation
    "validate_email",
    "validate_url",
    "validate_file_path",
]
