"""
Model Context Protocol (MCP) Protocol Definitions

This module defines the core types, messages, and constants for the MCP protocol,
which is based on JSON-RPC 2.0.

MCP Protocol Specification:
- https://modelcontextprotocol.io/

Key Concepts:
- Resources: Readable data resources that can be exposed to clients
- Tools: Executable functions that can be called by clients
- Prompts: Reusable prompt templates
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union, Callable, Awaitable
from abc import ABC, abstractmethod


# =============================================================================
# JSON-RPC Base Types
# =============================================================================

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"


class JSONRPCErrorCode(Enum):
    """JSON-RPC 2.0 standard error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000


class MCPErrorCode(Enum):
    """MCP-specific error codes."""
    # Connection errors
    CONNECTION_CLOSED = -1
    TIMEOUT = -2
    
    # Protocol errors
    PROTOCOL_VERSION_MISMATCH = -10001
    CAPABILITY_NOT_SUPPORTED = -10002
    
    # Resource errors
    RESOURCE_NOT_FOUND = -20001
    RESOURCE_ACCESS_DENIED = -20002
    
    # Tool errors
    TOOL_NOT_FOUND = -30001
    TOOL_EXECUTION_ERROR = -30002
    INVALID_TOOL_ARGUMENTS = -30003
    
    # Prompt errors
    PROMPT_NOT_FOUND = -40001
    PROMPT_RENDER_ERROR = -40002


@dataclass
class JSONRPCError:
    """JSON-RPC error object."""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCError":
        return cls(
            code=data["code"],
            message=data["message"],
            data=data.get("data")
        )


@dataclass
class JSONRPCRequest:
    """JSON-RPC request object."""
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None
    jsonrpc: str = JSONRPC_VERSION
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.params is not None:
            result["params"] = self.params
        if self.id is not None:
            result["id"] = self.id
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCRequest":
        return cls(
            jsonrpc=data.get("jsonrpc", JSONRPC_VERSION),
            method=data["method"],
            params=data.get("params"),
            id=data.get("id")
        )
    
    def is_notification(self) -> bool:
        """Check if this is a notification (no id)."""
        return self.id is None


@dataclass
class JSONRPCResponse:
    """JSON-RPC response object."""
    id: Union[str, int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[JSONRPCError] = None
    jsonrpc: str = JSONRPC_VERSION
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            result["error"] = self.error.to_dict()
        elif self.result is not None:
            result["result"] = self.result
        else:
            result["result"] = {}
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCResponse":
        error = None
        if "error" in data:
            error = JSONRPCError.from_dict(data["error"])
        return cls(
            jsonrpc=data.get("jsonrpc", JSONRPC_VERSION),
            id=data["id"],
            result=data.get("result"),
            error=error
        )
    
    def is_error(self) -> bool:
        """Check if this is an error response."""
        return self.error is not None


# Type alias for JSON-RPC messages
JSONRPCMessage = Union[JSONRPCRequest, JSONRPCResponse]


# =============================================================================
# MCP Method Names
# =============================================================================

class MCPMethod(Enum):
    """MCP protocol method names."""
    # Lifecycle
    INITIALIZE = "initialize"
    INITIALIZED = "notifications/initialized"
    SHUTDOWN = "shutdown"
    EXIT = "exit"
    
    # Resources
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_SUBSCRIBE = "resources/subscribe"
    RESOURCES_UNSUBSCRIBE = "resources/unsubscribe"
    RESOURCES_LIST_CHANGED = "notifications/resources/list_changed"
    
    # Tools
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    TOOLS_LIST_CHANGED = "notifications/tools/list_changed"
    
    # Prompts
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    PROMPTS_LIST_CHANGED = "notifications/prompts/list_changed"
    
    # Roots (client to server)
    ROOTS_LIST = "roots/list"
    ROOTS_LIST_CHANGED = "notifications/roots/list_changed"
    
    # Sampling (server to client)
    SAMPLING_CREATE_MESSAGE = "sampling/createMessage"


# =============================================================================
# MCP Capability Types
# =============================================================================

@dataclass
class ServerCapabilities:
    """Server capability declaration."""
    resources: Optional[Dict[str, Any]] = None
    tools: Optional[Dict[str, Any]] = None
    prompts: Optional[Dict[str, Any]] = None
    logging: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.resources is not None:
            result["resources"] = self.resources
        if self.tools is not None:
            result["tools"] = self.tools
        if self.prompts is not None:
            result["prompts"] = self.prompts
        if self.logging is not None:
            result["logging"] = self.logging
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServerCapabilities":
        return cls(
            resources=data.get("resources"),
            tools=data.get("tools"),
            prompts=data.get("prompts"),
            logging=data.get("logging")
        )


@dataclass
class ClientCapabilities:
    """Client capability declaration."""
    roots: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.roots is not None:
            result["roots"] = self.roots
        if self.sampling is not None:
            result["sampling"] = self.sampling
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClientCapabilities":
        return cls(
            roots=data.get("roots"),
            sampling=data.get("sampling")
        )


# =============================================================================
# MCP Lifecycle Types
# =============================================================================

@dataclass
class InitializeRequest:
    """Initialize request parameters."""
    protocolVersion: str
    capabilities: ClientCapabilities
    clientInfo: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocolVersion": self.protocolVersion,
            "capabilities": self.capabilities.to_dict(),
            "clientInfo": self.clientInfo
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InitializeRequest":
        return cls(
            protocolVersion=data["protocolVersion"],
            capabilities=ClientCapabilities.from_dict(data.get("capabilities", {})),
            clientInfo=data["clientInfo"]
        )


@dataclass
class InitializeResult:
    """Initialize response result."""
    protocolVersion: str
    capabilities: ServerCapabilities
    serverInfo: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocolVersion": self.protocolVersion,
            "capabilities": self.capabilities.to_dict(),
            "serverInfo": self.serverInfo
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InitializeResult":
        return cls(
            protocolVersion=data["protocolVersion"],
            capabilities=ServerCapabilities.from_dict(data.get("capabilities", {})),
            serverInfo=data["serverInfo"]
        )


# =============================================================================
# MCP Resource Types
# =============================================================================

@dataclass
class Resource:
    """A resource definition."""
    uri: str
    name: str
    description: Optional[str] = None
    mimeType: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"uri": self.uri, "name": self.name}
        if self.description is not None:
            result["description"] = self.description
        if self.mimeType is not None:
            result["mimeType"] = self.mimeType
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Resource":
        return cls(
            uri=data["uri"],
            name=data["name"],
            description=data.get("description"),
            mimeType=data.get("mimeType")
        )


@dataclass
class ResourceContent:
    """Resource content data."""
    uri: str
    mimeType: Optional[str] = None
    text: Optional[str] = None
    blob: Optional[str] = None  # base64 encoded binary data
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"uri": self.uri}
        if self.mimeType is not None:
            result["mimeType"] = self.mimeType
        if self.text is not None:
            result["text"] = self.text
        if self.blob is not None:
            result["blob"] = self.blob
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceContent":
        return cls(
            uri=data["uri"],
            mimeType=data.get("mimeType"),
            text=data.get("text"),
            blob=data.get("blob")
        )


@dataclass
class ListResourcesResult:
    """Result of resources/list request."""
    resources: List[Resource]
    nextCursor: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"resources": [r.to_dict() for r in self.resources]}
        if self.nextCursor is not None:
            result["nextCursor"] = self.nextCursor
        return result


@dataclass
class ReadResourceResult:
    """Result of resources/read request."""
    contents: List[ResourceContent]
    
    def to_dict(self) -> Dict[str, Any]:
        return {"contents": [c.to_dict() for c in self.contents]}


# =============================================================================
# MCP Tool Types
# =============================================================================

@dataclass
class ToolParameter:
    """Tool parameter definition (JSON Schema)."""
    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None
    properties: Optional[Dict[str, Any]] = None
    required: Optional[List[str]] = None
    items: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"type": self.type}
        if self.description is not None:
            result["description"] = self.description
        if self.enum is not None:
            result["enum"] = self.enum
        if self.properties is not None:
            result["properties"] = self.properties
        if self.required is not None:
            result["required"] = self.required
        if self.items is not None:
            result["items"] = self.items
        return result


@dataclass
class Tool:
    """A tool definition."""
    name: str
    description: str
    inputSchema: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tool":
        return cls(
            name=data["name"],
            description=data["description"],
            inputSchema=data["inputSchema"]
        )


@dataclass
class TextContent:
    """Text content in tool result."""
    type: str = "text"
    text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "text": self.text}


@dataclass
class ImageContent:
    """Image content in tool result."""
    type: str = "image"
    data: str = ""  # base64 encoded
    mimeType: str = "image/png"
    
    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "data": self.data, "mimeType": self.mimeType}


@dataclass
class EmbeddedResource:
    """Embedded resource in tool result."""
    type: str = "resource"
    resource: ResourceContent = field(default_factory=lambda: ResourceContent(uri=""))
    
    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "resource": self.resource.to_dict()}


ToolContent = Union[TextContent, ImageContent, EmbeddedResource]


@dataclass
class ListToolsResult:
    """Result of tools/list request."""
    tools: List[Tool]
    nextCursor: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"tools": [t.to_dict() for t in self.tools]}
        if self.nextCursor is not None:
            result["nextCursor"] = self.nextCursor
        return result


@dataclass
class CallToolResult:
    """Result of tools/call request."""
    content: List[Dict[str, Any]]
    isError: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {"content": self.content, "isError": self.isError}


# =============================================================================
# MCP Prompt Types
# =============================================================================

@dataclass
class PromptArgument:
    """Prompt argument definition."""
    name: str
    description: Optional[str] = None
    required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"name": self.name, "required": self.required}
        if self.description is not None:
            result["description"] = self.description
        return result


@dataclass
class Prompt:
    """A prompt template definition."""
    name: str
    description: Optional[str] = None
    arguments: Optional[List[PromptArgument]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"name": self.name}
        if self.description is not None:
            result["description"] = self.description
        if self.arguments is not None:
            result["arguments"] = [a.to_dict() for a in self.arguments]
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Prompt":
        args = None
        if "arguments" in data:
            args = [PromptArgument(**a) for a in data["arguments"]]
        return cls(
            name=data["name"],
            description=data.get("description"),
            arguments=args
        )


@dataclass
class PromptMessage:
    """A message in a prompt."""
    role: str  # "user" or "assistant"
    content: Dict[str, Any]  # TextContent or ImageContent
    
    def to_dict(self) -> Dict[str, Any]:
        return {"role": self.role, "content": self.content}


@dataclass
class GetPromptResult:
    """Result of prompts/get request."""
    description: Optional[str] = None
    messages: List[PromptMessage] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"messages": [m.to_dict() for m in self.messages]}
        if self.description is not None:
            result["description"] = self.description
        return result


@dataclass
class ListPromptsResult:
    """Result of prompts/list request."""
    prompts: List[Prompt]
    nextCursor: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"prompts": [p.to_dict() for p in self.prompts]}
        if self.nextCursor is not None:
            result["nextCursor"] = self.nextCursor
        return result


# =============================================================================
# MCP Exceptions
# =============================================================================

class MCPError(Exception):
    """Base MCP error."""
    
    def __init__(self, code: int, message: str, data: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)
    
    def to_jsonrpc_error(self) -> JSONRPCError:
        return JSONRPCError(code=self.code, message=self.message, data=self.data)


class ProtocolError(MCPError):
    """Protocol-level error."""
    
    def __init__(self, message: str, data: Optional[Dict[str, Any]] = None):
        super().__init__(JSONRPCErrorCode.INVALID_REQUEST.value, message, data)


class MethodNotFoundError(MCPError):
    """Method not found error."""
    
    def __init__(self, method: str):
        super().__init__(
            JSONRPCErrorCode.METHOD_NOT_FOUND.value,
            f"Method not found: {method}"
        )


class InvalidParamsError(MCPError):
    """Invalid parameters error."""
    
    def __init__(self, message: str = "Invalid parameters"):
        super().__init__(JSONRPCErrorCode.INVALID_PARAMS.value, message)


class ResourceNotFoundError(MCPError):
    """Resource not found error."""
    
    def __init__(self, uri: str):
        super().__init__(
            MCPErrorCode.RESOURCE_NOT_FOUND.value,
            f"Resource not found: {uri}"
        )


class ToolNotFoundError(MCPError):
    """Tool not found error."""
    
    def __init__(self, name: str):
        super().__init__(
            MCPErrorCode.TOOL_NOT_FOUND.value,
            f"Tool not found: {name}"
        )


class ToolExecutionError(MCPError):
    """Tool execution error."""
    
    def __init__(self, name: str, message: str):
        super().__init__(
            MCPErrorCode.TOOL_EXECUTION_ERROR.value,
            f"Tool '{name}' execution error: {message}"
        )


class PromptNotFoundError(MCPError):
    """Prompt not found error."""
    
    def __init__(self, name: str):
        super().__init__(
            MCPErrorCode.PROMPT_NOT_FOUND.value,
            f"Prompt not found: {name}"
        )


# =============================================================================
# Utility Functions
# =============================================================================

def create_request(method: str, params: Optional[Dict[str, Any]] = None, 
                   req_id: Optional[Union[str, int]] = None) -> JSONRPCRequest:
    """Create a JSON-RPC request."""
    return JSONRPCRequest(method=method, params=params, id=req_id)


def create_response(req_id: Union[str, int], 
                    result: Optional[Dict[str, Any]] = None) -> JSONRPCResponse:
    """Create a JSON-RPC success response."""
    return JSONRPCResponse(id=req_id, result=result)


def create_error_response(req_id: Union[str, int], 
                          error: JSONRPCError) -> JSONRPCResponse:
    """Create a JSON-RPC error response."""
    return JSONRPCResponse(id=req_id, error=error)


def parse_message(data: Union[str, Dict[str, Any]]) -> JSONRPCMessage:
    """Parse a JSON-RPC message from string or dict."""
    if isinstance(data, str):
        data = json.loads(data)
    
    if not isinstance(data, dict):
        raise ProtocolError("Invalid JSON-RPC message: must be an object")
    
    if "jsonrpc" not in data or data["jsonrpc"] != JSONRPC_VERSION:
        raise ProtocolError("Invalid or missing jsonrpc version")
    
    # Check if it's a response (has 'result' or 'error')
    if "result" in data or "error" in data:
        if "id" not in data:
            raise ProtocolError("Response must have an id")
        return JSONRPCResponse.from_dict(data)
    
    # It's a request
    if "method" not in data:
        raise ProtocolError("Request must have a method")
    
    return JSONRPCRequest.from_dict(data)


def serialize_message(message: JSONRPCMessage) -> str:
    """Serialize a JSON-RPC message to string."""
    return json.dumps(message.to_dict(), ensure_ascii=False)


# =============================================================================
# Type Aliases for Handlers
# =============================================================================

RequestHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
NotificationHandler = Callable[[Dict[str, Any]], Awaitable[None]]
