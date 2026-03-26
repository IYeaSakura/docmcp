"""
DocMCP - Enterprise Document Processing System with MCP Protocol Support.

A high-availability, high-security, high-reliability, high-scalability, 
and high-performance document processing framework.

Features:
    - Multi-format document support (doc/docx/pdf/xlsx/xls/ppt/pptx)
    - MCP (Model Context Protocol) protocol support
    - Skills plugin system with dynamic loading
    - Async processing for high concurrency
    - Security sandbox for isolated execution
    - Unified interface for all document types

Example:
    >>> from docmcp import ProcessingEngine
    >>> engine = ProcessingEngine()
    >>> result = await engine.process(document)

Version: 0.1.0
Author: DocMCP Team
License: MIT
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "DocMCP Team"
__license__ = "MIT"

# Core exports
from docmcp.core.document import (
    BaseDocument,
    DocumentMetadata,
    DocumentContent,
    DocumentFormat,
)
from docmcp.core.engine import (
    ProcessingEngine,
    ProcessingContext,
    ProcessingResult,
    ProcessingStatus,
)

# Skills exports
from docmcp.skills.base import BaseSkill, SkillContext, SkillResult
from docmcp.skills.registry import SkillRegistry

# MCP exports
from docmcp.mcp.server import MCPServer
from docmcp.mcp.protocol import MCPMessage, MCPResponse

# Optional exports (may not be available if dependencies missing)
try:
    from docmcp.security import SandboxExecutor
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

try:
    from docmcp.performance import Cache
    PERFORMANCE_AVAILABLE = True
except ImportError:
    PERFORMANCE_AVAILABLE = False

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # Core classes
    "BaseDocument",
    "DocumentMetadata",
    "DocumentContent",
    "DocumentFormat",
    "ProcessingEngine",
    "ProcessingContext",
    "ProcessingResult",
    "ProcessingStatus",
    # Skills classes
    "BaseSkill",
    "SkillContext",
    "SkillResult",
    "SkillRegistry",
    # MCP classes
    "MCPServer",
    "MCPMessage",
    "MCPResponse",
]


def get_version() -> str:
    """Return the version of DocMCP."""
    return __version__


def get_info() -> dict[str, str]:
    """Return information about DocMCP."""
    return {
        "version": __version__,
        "author": __author__,
        "license": __license__,
    }
