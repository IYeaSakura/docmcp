"""
MCP (Model Context Protocol) module for DocMCP.

This module provides implementation of the Model Context Protocol,
enabling standardized communication between AI models and document
processing capabilities.

The MCP protocol defines:
    - Message formats for requests and responses
    - Capability negotiation
    - Resource management
    - Context sharing

Example:
    >>> from docmcp.mcp import MCPServer, MCPMessage
    >>> server = MCPServer()
    >>> await server.start()
    >>> message = MCPMessage(
    ...     method="process_document",
    ...     params={"document_id": "doc-123"}
    ... )
    >>> response = await server.handle_message(message)
"""

from __future__ import annotations

from docmcp.mcp.protocol import (
    MCPMessage,
    MCPResponse,
    MCPRequest,
    MCPError,
    MCPErrorCode,
    MCPMethod,
    MCPCapability,
)
from docmcp.mcp.server import (
    MCPServer,
    MCPHandler,
    ConnectionManager,
)
from docmcp.mcp.client import (
    MCPClient,
    ConnectionPool,
)

__all__ = [
    # Protocol classes
    "MCPMessage",
    "MCPResponse",
    "MCPRequest",
    "MCPError",
    "MCPErrorCode",
    "MCPMethod",
    "MCPCapability",
    # Server classes
    "MCPServer",
    "MCPHandler",
    "ConnectionManager",
    # Client classes
    "MCPClient",
    "ConnectionPool",
]
