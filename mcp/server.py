"""
Model Context Protocol (MCP) Server Implementation

This module provides a complete MCP server implementation with:
- Lifecycle management (initialize, initialized, shutdown)
- Resource management (list, read)
- Tool management (list, call)
- Prompt management (list, get)
- Multiple transport support (stdio, sse)

Usage:
    server = MCPServer("my-server", "1.0.0")

    @server.resource("docs://readme")
    async def get_readme() -> ResourceContent:
        return ResourceContent(uri="docs://readme", text="# README")

    @server.tool("echo")
    async def echo_tool(message: str) -> str:
        return message

    @server.prompt("greeting")
    async def greeting_prompt(name: str) -> str:
        return f"Hello, {name}!"

    await server.run_stdio()
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set, Union, Awaitable
from contextlib import asynccontextmanager

from .protocol import (
    # Base types
    JSONRPC_VERSION, MCP_PROTOCOL_VERSION,
    JSONRPCRequest, JSONRPCResponse, JSONRPCError, JSONRPCMessage,
    JSONRPCErrorCode, MCPErrorCode,

    # MCP types
    MCPMethod, ServerCapabilities, ClientCapabilities,
    InitializeRequest, InitializeResult,

    # Resource types
    Resource, ResourceContent, ListResourcesResult, ReadResourceResult,

    # Tool types
    Tool, ToolParameter, ListToolsResult, CallToolResult,
    TextContent, ImageContent, EmbeddedResource,

    # Prompt types
    Prompt, PromptArgument, PromptMessage, ListPromptsResult, GetPromptResult,

    # Exceptions
    MCPError, ProtocolError, MethodNotFoundError, InvalidParamsError,
    ResourceNotFoundError, ToolNotFoundError, ToolExecutionError, PromptNotFoundError,

    # Utilities
    create_response, create_error_response, parse_message, serialize_message,
    RequestHandler, NotificationHandler
)


# =============================================================================
# Transport Layer
# =============================================================================

class Transport(ABC):
    """Abstract base class for MCP transports."""

    @abstractmethod
    async def read_message(self) -> Optional[str]:
        """Read a message from the transport. Returns None on EOF."""
        pass

    @abstractmethod
    async def write_message(self, message: str) -> None:
        """Write a message to the transport."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the transport."""
        pass


class StdioTransport(Transport):
    """Standard input/output transport for MCP."""

    def __init__(self, stdin=None, stdout=None):
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self._closed = False
        self._lock = asyncio.Lock()

    async def read_message(self) -> Optional[str]:
        """Read a line from stdin."""
        if self._closed:
            return None

        try:
            # Use asyncio to read from stdin
            loop = asyncio.get_event_loop()
            line = await loop.run_in_executor(None, self.stdin.readline)
            if not line:
                return None
            return line.strip()
        except Exception:
            return None

    async def write_message(self, message: str) -> None:
        """Write a line to stdout."""
        if self._closed:
            return

        async with self._lock:
            try:
                loop = asyncio.get_event_loop()
                full_message = message + "\n"
                await loop.run_in_executor(None, self.stdout.write, full_message)
                await loop.run_in_executor(None, self.stdout.flush)
            except Exception as e:
                print(f"Error writing message: {e}", file=sys.stderr)

    async def close(self) -> None:
        """Close the transport."""
        self._closed = True


class SSETransport(Transport):
    """Server-Sent Events transport for MCP (server-side)."""

    def __init__(self):
        self._message_queue: asyncio.Queue[str] = asyncio.Queue()
        self._response_queues: Dict[Union[str, int], asyncio.Queue[str]] = {}
        self._closed = False
        self._client_connected = False

    async def read_message(self) -> Optional[str]:
        """Read a message from the client (via POST endpoint)."""
        if self._closed:
            return None
        try:
            return await self._message_queue.get()
        except asyncio.CancelledError:
            return None

    async def write_message(self, message: str) -> None:
        """Write a message to the client (via SSE)."""
        if self._closed:
            return

        # Parse message to get id for routing
        try:
            data = json.loads(message)
            msg_id = data.get("id")

            # If there's a waiting response queue, put it there
            if msg_id is not None and msg_id in self._response_queues:
                await self._response_queues[msg_id].put(message)
            else:
                # Broadcast to all connected clients
                await self._broadcast(message)
        except json.JSONDecodeError:
            pass

    async def _broadcast(self, message: str) -> None:
        """Broadcast message to all connected clients."""
        # This would be implemented with actual SSE connections
        pass

    async def client_send(self, message: str) -> str:
        """Called when client sends a message via POST. Returns response."""
        await self._message_queue.put(message)

        # Wait for response
        try:
            data = json.loads(message)
            msg_id = data.get("id")
            if msg_id is not None:
                response_queue: asyncio.Queue[str] = asyncio.Queue()
                self._response_queues[msg_id] = response_queue
                try:
                    response = await asyncio.wait_for(
                        response_queue.get(),
                        timeout=30.0
                    )
                    return response
                finally:
                    del self._response_queues[msg_id]
        except (json.JSONDecodeError, asyncio.TimeoutError):
            pass

        return json.dumps({"jsonrpc": "2.0", "id": None, "result": {}})

    async def close(self) -> None:
        """Close the transport."""
        self._closed = True


# =============================================================================
# Resource, Tool, and Prompt Registries
# =============================================================================

@dataclass
class RegisteredResource:
    """A registered resource with its handler."""
    resource: Resource
    handler: Callable[[], Awaitable[ResourceContent]]


@dataclass
class RegisteredTool:
    """A registered tool with its handler."""
    tool: Tool
    handler: Callable[[Dict[str, Any]], Awaitable[List[Dict[str, Any]]]]


@dataclass
class RegisteredPrompt:
    """A registered prompt with its handler."""
    prompt: Prompt
    handler: Callable[[Optional[Dict[str, str]]], Awaitable[List[PromptMessage]]]


class ResourceRegistry:
    """Registry for MCP resources."""

    def __init__(self):
        self._resources: Dict[str, RegisteredResource] = {}

    def register(
        self,
        uri: str,
        name: str,
        handler: Callable[[], Awaitable[ResourceContent]],
        description: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> None:
        """Register a resource."""
        resource = Resource(
            uri=uri,
            name=name,
            description=description,
            mimeType=mime_type
        )
        self._resources[uri] = RegisteredResource(resource=resource, handler=handler)

    def unregister(self, uri: str) -> bool:
        """Unregister a resource. Returns True if found."""
        if uri in self._resources:
            del self._resources[uri]
            return True
        return False

    def get(self, uri: str) -> Optional[RegisteredResource]:
        """Get a registered resource."""
        return self._resources.get(uri)

    def list_all(self) -> List[Resource]:
        """List all registered resources."""
        return [r.resource for r in self._resources.values()]

    def clear(self) -> None:
        """Clear all registered resources."""
        self._resources.clear()


class ToolRegistry:
    """Registry for MCP tools."""

    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable[[Dict[str, Any]], Awaitable[List[Dict[str, Any]]]],
        input_schema: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register a tool."""
        if input_schema is None:
            input_schema = {"type": "object", "properties": {}}

        tool = Tool(
            name=name,
            description=description,
            inputSchema=input_schema
        )
        self._tools[name] = RegisteredTool(tool=tool, handler=handler)

    def unregister(self, name: str) -> bool:
        """Unregister a tool. Returns True if found."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[RegisteredTool]:
        """Get a registered tool."""
        return self._tools.get(name)

    def list_all(self) -> List[Tool]:
        """List all registered tools."""
        return [t.tool for t in self._tools.values()]

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()


class PromptRegistry:
    """Registry for MCP prompts."""

    def __init__(self):
        self._prompts: Dict[str, RegisteredPrompt] = {}

    def register(
        self,
        name: str,
        handler: Callable[[Optional[Dict[str, str]]], Awaitable[List[PromptMessage]]],
        description: Optional[str] = None,
        arguments: Optional[List[PromptArgument]] = None
    ) -> None:
        """Register a prompt."""
        prompt = Prompt(
            name=name,
            description=description,
            arguments=arguments
        )
        self._prompts[name] = RegisteredPrompt(prompt=prompt, handler=handler)

    def unregister(self, name: str) -> bool:
        """Unregister a prompt. Returns True if found."""
        if name in self._prompts:
            del self._prompts[name]
            return True
        return False

    def get(self, name: str) -> Optional[RegisteredPrompt]:
        """Get a registered prompt."""
        return self._prompts.get(name)

    def list_all(self) -> List[Prompt]:
        """List all registered prompts."""
        return [p.prompt for p in self._prompts.values()]

    def clear(self) -> None:
        """Clear all registered prompts."""
        self._prompts.clear()


# =============================================================================
# MCP Server
# =============================================================================

class ServerState(Enum):
    """Server lifecycle states."""
    CREATED = auto()
    INITIALIZING = auto()
    INITIALIZED = auto()
    SHUTTING_DOWN = auto()
    SHUTDOWN = auto()


class MCPServer:
    """
    Model Context Protocol Server implementation.

    Supports:
    - Lifecycle management (initialize, initialized, shutdown)
    - Resources (list, read)
    - Tools (list, call)
    - Prompts (list, get)
    - Multiple transports (stdio, sse)

    Example:
        server = MCPServer("my-server", "1.0.0")

        @server.resource("docs://readme", "README")
        async def readme():
            return ResourceContent(uri="docs://readme", text="# README")

        await server.run_stdio()
    """

    def __init__(
        self,
        name: str,
        version: str,
        capabilities: Optional[ServerCapabilities] = None
    ):
        """
        Initialize the MCP server.

        Args:
            name: Server name
            version: Server version
            capabilities: Server capabilities (auto-detected if None)
        """
        self.name = name
        self.version = version
        self._capabilities = capabilities

        # Registries
        self._resources = ResourceRegistry()
        self._tools = ToolRegistry()
        self._prompts = PromptRegistry()

        # State
        self._state = ServerState.CREATED
        self._client_capabilities: Optional[ClientCapabilities] = None
        self._client_info: Optional[Dict[str, str]] = None

        # Transport
        self._transport: Optional[Transport] = None

        # Request handlers
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {
            # Lifecycle
            MCPMethod.INITIALIZE.value: self._handle_initialize,

            # Resources
            MCPMethod.RESOURCES_LIST.value: self._handle_resources_list,
            MCPMethod.RESOURCES_READ.value: self._handle_resources_read,

            # Tools
            MCPMethod.TOOLS_LIST.value: self._handle_tools_list,
            MCPMethod.TOOLS_CALL.value: self._handle_tools_call,

            # Prompts
            MCPMethod.PROMPTS_LIST.value: self._handle_prompts_list,
            MCPMethod.PROMPTS_GET.value: self._handle_prompts_get,
        }

        # Notification handlers
        self._notification_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {
            MCPMethod.INITIALIZED.value: self._handle_initialized_notification,
        }

    # ==========================================================================
    # Properties
    # ==========================================================================

    @property
    def state(self) -> ServerState:
        """Get current server state."""
        return self._state

    @property
    def is_initialized(self) -> bool:
        """Check if server is initialized."""
        return self._state == ServerState.INITIALIZED

    @property
    def resources(self) -> ResourceRegistry:
        """Get the resource registry."""
        return self._resources

    @property
    def tools(self) -> ToolRegistry:
        """Get the tool registry."""
        return self._tools

    @property
    def prompts(self) -> PromptRegistry:
        """Get the prompt registry."""
        return self._prompts

    # ==========================================================================
    # Registration Decorators
    # ==========================================================================

    def resource(
        self,
        uri: str,
        name: str,
        description: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Callable:
        """
        Decorator to register a resource.

        Args:
            uri: Resource URI (e.g., "docs://readme")
            name: Human-readable name
            description: Optional description
            mime_type: Optional MIME type

        Example:
            @server.resource("docs://readme", "README", mime_type="text/markdown")
            async def get_readme():
                return ResourceContent(uri="docs://readme", text="# README")
        """
        def decorator(handler: Callable[[], Awaitable[ResourceContent]]) -> Callable:
            self._resources.register(uri, name, handler, description, mime_type)
            return handler
        return decorator

    def tool(
        self,
        name: str,
        description: str,
        input_schema: Optional[Dict[str, Any]] = None
    ) -> Callable:
        """
        Decorator to register a tool.

        Args:
            name: Tool name
            description: Tool description
            input_schema: JSON Schema for tool parameters

        Example:
            @server.tool("echo", "Echo a message")
            async def echo_tool(args: dict):
                return [{"type": "text", "text": args.get("message", "")}]
        """
        def decorator(
            handler: Callable[[Dict[str, Any]], Awaitable[List[Dict[str, Any]]]]
        ) -> Callable:
            self._tools.register(name, description, handler, input_schema)
            return handler
        return decorator

    def prompt(
        self,
        name: str,
        description: Optional[str] = None,
        arguments: Optional[List[PromptArgument]] = None
    ) -> Callable:
        """
        Decorator to register a prompt.

        Args:
            name: Prompt name
            description: Optional description
            arguments: Optional list of prompt arguments

        Example:
            @server.prompt("greeting", "A greeting prompt")
            async def greeting_prompt(args: dict = None):
                name = (args or {}).get("name", "World")
                return [PromptMessage(role="user", content={"type": "text", "text": f"Hello {name}!"})]
        """
        def decorator(
            handler: Callable[[Optional[Dict[str, str]]], Awaitable[List[PromptMessage]]]
        ) -> Callable:
            self._prompts.register(name, handler, description, arguments)
            return handler
        return decorator

    # ==========================================================================
    # Lifecycle Methods
    # ==========================================================================

    def _get_capabilities(self) -> ServerCapabilities:
        """Get server capabilities based on registered items."""
        if self._capabilities is not None:
            return self._capabilities

        capabilities = ServerCapabilities()

        if self._resources.list_all():
            capabilities.resources = {"subscribe": False}

        if self._tools.list_all():
            capabilities.tools = {}

        if self._prompts.list_all():
            capabilities.prompts = {}

        return capabilities

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        if self._state != ServerState.CREATED:
            raise ProtocolError("Server already initialized")

        self._state = ServerState.INITIALIZING

        try:
            request = InitializeRequest.from_dict(params)
        except (KeyError, TypeError) as e:
            raise InvalidParamsError(f"Invalid initialize params: {e}")

        # Check protocol version compatibility
        if request.protocolVersion != MCP_PROTOCOL_VERSION:
            raise ProtocolError(
                f"Protocol version mismatch: expected {MCP_PROTOCOL_VERSION}, "
                f"got {request.protocolVersion}"
            )

        self._client_capabilities = request.capabilities
        self._client_info = request.clientInfo

        result = InitializeResult(
            protocolVersion=MCP_PROTOCOL_VERSION,
            capabilities=self._get_capabilities(),
            serverInfo={"name": self.name, "version": self.version}
        )

        return result.to_dict()

    async def _handle_initialized_notification(self, params: Dict[str, Any]) -> None:
        """Handle initialized notification."""
        if self._state == ServerState.INITIALIZING:
            self._state = ServerState.INITIALIZED

    async def _handle_shutdown(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle shutdown request."""
        self._state = ServerState.SHUTTING_DOWN
        return {}

    # ==========================================================================
    # Resource Handlers
    # ==========================================================================

    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request."""
        resources = self._resources.list_all()
        result = ListResourcesResult(resources=resources)
        return result.to_dict()

    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")
        if not uri:
            raise InvalidParamsError("Missing 'uri' parameter")

        registered = self._resources.get(uri)
        if registered is None:
            raise ResourceNotFoundError(uri)

        try:
            content = await registered.handler()
            result = ReadResourceResult(contents=[content])
            return result.to_dict()
        except Exception as e:
            raise MCPError(
                MCPErrorCode.RESOURCE_NOT_FOUND.value,
                f"Error reading resource {uri}: {str(e)}"
            )

    # ==========================================================================
    # Tool Handlers
    # ==========================================================================

    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = self._tools.list_all()
        result = ListToolsResult(tools=tools)
        return result.to_dict()

    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        name = params.get("name")
        arguments = params.get("arguments", {})

        if not name:
            raise InvalidParamsError("Missing 'name' parameter")

        registered = self._tools.get(name)
        if registered is None:
            raise ToolNotFoundError(name)

        try:
            content = await registered.handler(arguments)
            result = CallToolResult(content=content, isError=False)
            return result.to_dict()
        except MCPError:
            raise
        except Exception as e:
            raise ToolExecutionError(name, str(e))

    # ==========================================================================
    # Prompt Handlers
    # ==========================================================================

    async def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/list request."""
        prompts = self._prompts.list_all()
        result = ListPromptsResult(prompts=prompts)
        return result.to_dict()

    async def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        name = params.get("name")
        arguments = params.get("arguments")

        if not name:
            raise InvalidParamsError("Missing 'name' parameter")

        registered = self._prompts.get(name)
        if registered is None:
            raise PromptNotFoundError(name)

        try:
            messages = await registered.handler(arguments)
            result = GetPromptResult(messages=messages)
            return result.to_dict()
        except Exception as e:
            raise MCPError(
                MCPErrorCode.PROMPT_RENDER_ERROR.value,
                f"Error rendering prompt {name}: {str(e)}"
            )

    # ==========================================================================
    # Request Processing
    # ==========================================================================

    async def _process_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Process a JSON-RPC request and return a response."""
        method = request.method
        params = request.params or {}
        req_id = request.id

        # Handle notifications (no id)
        if request.is_notification():
            handler = self._notification_handlers.get(method)
            if handler:
                try:
                    await handler(params)
                except Exception as e:
                    # Notifications don't return errors
                    pass
            return None  # No response for notifications

        # Handle requests
        handler = self._handlers.get(method)
        if handler is None:
            error = JSONRPCError(
                code=JSONRPCErrorCode.METHOD_NOT_FOUND.value,
                message=f"Method not found: {method}"
            )
            return create_error_response(req_id, error)

        try:
            result = await handler(params)
            return create_response(req_id, result)
        except MCPError as e:
            return create_error_response(req_id, e.to_jsonrpc_error())
        except Exception as e:
            error = JSONRPCError(
                code=JSONRPCErrorCode.INTERNAL_ERROR.value,
                message=str(e),
                data={"traceback": traceback.format_exc()}
            )
            return create_error_response(req_id, error)

    async def _handle_message(self, message_str: str) -> Optional[str]:
        """Handle a single message and return response string if applicable."""
        try:
            message = parse_message(message_str)
        except Exception as e:
            # Parse error
            error = JSONRPCError(
                code=JSONRPCErrorCode.PARSE_ERROR.value,
                message=str(e)
            )
            response = JSONRPCResponse(id=None, error=error)
            return serialize_message(response)

        if isinstance(message, JSONRPCRequest):
            response = await self._process_request(message)
            if response is not None:
                return serialize_message(response)

        return None

    # ==========================================================================
    # Public API
    # ==========================================================================

    async def run(self, transport: Transport) -> None:
        """
        Run the server with the given transport.

        Args:
            transport: Transport instance to use
        """
        self._transport = transport

        try:
            while self._state not in (ServerState.SHUTDOWN, ServerState.SHUTTING_DOWN):
                message = await transport.read_message()
                if message is None:
                    # EOF
                    break

                if not message.strip():
                    continue

                response = await self._handle_message(message)
                if response is not None:
                    await transport.write_message(response)

        except asyncio.CancelledError:
            pass
        finally:
            await transport.close()
            self._state = ServerState.SHUTDOWN

    async def run_stdio(self) -> None:
        """Run the server with stdio transport."""
        transport = StdioTransport()
        await self.run(transport)

    async def run_sse(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        """
        Run the server with SSE transport.

        Note: This requires a web framework integration (e.g., FastAPI, aiohttp).
        For now, this is a placeholder.
        """
        raise NotImplementedError(
            "SSE transport requires web framework integration. "
            "Use run_stdio() or implement custom SSE transport."
        )

    def register_handler(
        self,
        method: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
    ) -> None:
        """Register a custom request handler."""
        self._handlers[method] = handler

    def register_notification_handler(
        self,
        method: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Register a custom notification handler."""
        self._notification_handlers[method] = handler

    async def shutdown(self) -> None:
        """Shutdown the server gracefully."""
        self._state = ServerState.SHUTTING_DOWN
        if self._transport:
            await self._transport.close()
        self._state = ServerState.SHUTDOWN
