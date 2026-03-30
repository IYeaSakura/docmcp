"""
Model Context Protocol (MCP) Implementation

This package provides a complete implementation of the Model Context Protocol:
- protocol: Core types, messages, and constants
- server: MCP server implementation
- client: MCP client implementation
- doc_server: Document processing MCP server

Usage:
    # Create a server
    from docmcp.mcp.server import MCPServer

    server = MCPServer("my-server", "1.0.0")

    @server.resource("docs://readme", "README")
    async def get_readme():
        return ResourceContent(uri="docs://readme", text="# README")

    @server.tool("echo", "Echo a message")
    async def echo_tool(args):
        return [{"type": "text", "text": args.get("message", "")}]

    await server.run_stdio()

    # Create a client
    from docmcp.mcp.client import MCPClient

    client = MCPClient("my-client", "1.0.0")
    await client.connect_stdio(["python", "server.py"])

    resources = await client.list_resources()
    tools = await client.list_tools()

    await client.disconnect()
"""

from .protocol import (
    # Version constants
    JSONRPC_VERSION,
    MCP_PROTOCOL_VERSION,

    # JSON-RPC types
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    JSONRPCMessage,
    JSONRPCErrorCode,
    MCPErrorCode,

    # MCP method names
    MCPMethod,

    # Capabilities
    ServerCapabilities,
    ClientCapabilities,

    # Lifecycle types
    InitializeRequest,
    InitializeResult,

    # Resource types
    Resource,
    ResourceContent,
    ListResourcesResult,
    ReadResourceResult,

    # Tool types
    Tool,
    ToolParameter,
    ListToolsResult,
    CallToolResult,
    TextContent,
    ImageContent,
    EmbeddedResource,

    # Prompt types
    Prompt,
    PromptArgument,
    PromptMessage,
    ListPromptsResult,
    GetPromptResult,

    # Exceptions
    MCPError,
    ProtocolError,
    MethodNotFoundError,
    InvalidParamsError,
    ResourceNotFoundError,
    ToolNotFoundError,
    ToolExecutionError,
    PromptNotFoundError,

    # Utilities
    create_request,
    create_response,
    create_error_response,
    parse_message,
    serialize_message,
    RequestHandler,
    NotificationHandler,
)

from .server import (
    MCPServer,
    ServerState,
    Transport,
    StdioTransport,
    SSETransport,
    ResourceRegistry,
    ToolRegistry,
    PromptRegistry,
)

from .client import (
    MCPClient,
    ClientState,
    ClientTransport,
    StdioClientTransport,
    SSEClientTransport,
)

from .doc_server import (
    DocumentMCPServer,
    Document,
    DocumentStore,
    DocumentProcessor,
)

__version__ = "1.0.0"
__all__ = [
    # Version
    "JSONRPC_VERSION",
    "MCP_PROTOCOL_VERSION",

    # Protocol types
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "JSONRPCMessage",
    "JSONRPCErrorCode",
    "MCPErrorCode",
    "MCPMethod",

    # Capabilities
    "ServerCapabilities",
    "ClientCapabilities",

    # Lifecycle
    "InitializeRequest",
    "InitializeResult",

    # Resources
    "Resource",
    "ResourceContent",
    "ListResourcesResult",
    "ReadResourceResult",

    # Tools
    "Tool",
    "ToolParameter",
    "ListToolsResult",
    "CallToolResult",
    "TextContent",
    "ImageContent",
    "EmbeddedResource",

    # Prompts
    "Prompt",
    "PromptArgument",
    "PromptMessage",
    "ListPromptsResult",
    "GetPromptResult",

    # Exceptions
    "MCPError",
    "ProtocolError",
    "MethodNotFoundError",
    "InvalidParamsError",
    "ResourceNotFoundError",
    "ToolNotFoundError",
    "ToolExecutionError",
    "PromptNotFoundError",

    # Utilities
    "create_request",
    "create_response",
    "create_error_response",
    "parse_message",
    "serialize_message",
    "RequestHandler",
    "NotificationHandler",

    # Server
    "MCPServer",
    "ServerState",
    "Transport",
    "StdioTransport",
    "SSETransport",
    "ResourceRegistry",
    "ToolRegistry",
    "PromptRegistry",

    # Client
    "MCPClient",
    "ClientState",
    "ClientTransport",
    "StdioClientTransport",
    "SSEClientTransport",

    # Document Server
    "DocumentMCPServer",
    "Document",
    "DocumentStore",
    "DocumentProcessor",
]
