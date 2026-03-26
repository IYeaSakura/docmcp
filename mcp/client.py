"""
Model Context Protocol (MCP) Client Implementation

This module provides a complete MCP client implementation with:
- Connection management
- Lifecycle handling (initialize, initialized, shutdown)
- Resource operations (list, read)
- Tool operations (list, call)
- Prompt operations (list, get)
- Multiple transport support (stdio, sse)

Usage:
    client = MCPClient("my-client", "1.0.0")
    
    # Connect via stdio to a server process
    await client.connect_stdio(["python", "server.py"])
    
    # List and use resources
    resources = await client.list_resources()
    content = await client.read_resource("docs://readme")
    
    # List and call tools
    tools = await client.list_tools()
    result = await client.call_tool("echo", {"message": "Hello"})
    
    # List and get prompts
    prompts = await client.list_prompts()
    messages = await client.get_prompt("greeting", {"name": "World"})
    
    await client.disconnect()
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import uuid
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union, Callable, AsyncIterator
from abc import ABC, abstractmethod
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
    Tool, ListToolsResult, CallToolResult,
    
    # Prompt types
    Prompt, PromptMessage, ListPromptsResult, GetPromptResult,
    
    # Exceptions
    MCPError, ProtocolError, MethodNotFoundError, InvalidParamsError,
    
    # Utilities
    create_request, create_response, create_error_response,
    parse_message, serialize_message
)


# =============================================================================
# Client Transport Layer
# =============================================================================

class ClientTransport(ABC):
    """Abstract base class for MCP client transports."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to the server."""
        pass
    
    @abstractmethod
    async def send(self, message: str) -> None:
        """Send a message to the server."""
        pass
    
    @abstractmethod
    async def receive(self) -> Optional[str]:
        """Receive a message from the server. Returns None on disconnect."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        pass


class StdioClientTransport(ClientTransport):
    """
    Standard input/output transport for MCP client.
    
    Spawns a subprocess and communicates via stdin/stdout.
    """
    
    def __init__(self, command: List[str], env: Optional[Dict[str, str]] = None):
        """
        Initialize stdio transport.
        
        Args:
            command: Command and arguments to spawn the server
            env: Optional environment variables
        """
        self.command = command
        self.env = env
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Spawn the server process and set up communication."""
        try:
            # Create subprocess
            self._process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**dict(os.environ), **(self.env or {})} if self.env else None
            )
            
            # Create stream reader/writer
            self._reader = asyncio.StreamReader()
            self._writer = asyncio.StreamWriter(
                transport=self._process.stdin,
                protocol=asyncio.StreamReaderProtocol(self._reader),
                reader=self._reader,
                loop=asyncio.get_event_loop()
            )
            
            # Set up stdout reader
            loop = asyncio.get_event_loop()
            protocol = asyncio.StreamReaderProtocol(self._reader)
            await loop.connect_read_pipe(lambda: protocol, self._process.stdout)
            
            self._connected = True
            
        except Exception as e:
            raise ConnectionError(f"Failed to spawn process: {e}")
    
    async def send(self, message: str) -> None:
        """Send a message to the server via stdin."""
        if not self._connected or self._process is None:
            raise ConnectionError("Not connected")
        
        try:
            data = (message + "\n").encode('utf-8')
            self._process.stdin.write(data)
            await asyncio.get_event_loop().run_in_executor(
                None, self._process.stdin.flush
            )
        except Exception as e:
            raise ConnectionError(f"Failed to send message: {e}")
    
    async def receive(self) -> Optional[str]:
        """Receive a message from the server via stdout."""
        if not self._connected or self._process is None:
            return None
        
        try:
            loop = asyncio.get_event_loop()
            line = await loop.run_in_executor(None, self._process.stdout.readline)
            if not line:
                return None
            return line.decode('utf-8').strip()
        except Exception:
            return None
    
    async def close(self) -> None:
        """Close the connection and terminate the process."""
        self._connected = False
        
        if self._process is not None:
            try:
                self._process.terminate()
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, self._process.wait
                    ),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                self._process.kill()
            except Exception:
                pass
            finally:
                self._process = None
    
    @property
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        return self._connected and self._process is not None


class SSEClientTransport(ClientTransport):
    """
    Server-Sent Events transport for MCP client.
    
    Connects to an HTTP endpoint and receives events via SSE.
    """
    
    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None):
        """
        Initialize SSE transport.
        
        Args:
            base_url: Base URL of the MCP server
            headers: Optional HTTP headers
        """
        self.base_url = base_url.rstrip('/')
        self.headers = headers or {}
        self._session: Optional[Any] = None  # aiohttp.ClientSession
        self._event_source: Optional[Any] = None
        self._connected = False
        self._message_queue: asyncio.Queue[str] = asyncio.Queue()
    
    async def connect(self) -> None:
        """Connect to the SSE endpoint."""
        try:
            import aiohttp
            
            self._session = aiohttp.ClientSession(headers=self.headers)
            
            # Connect to SSE endpoint
            response = await self._session.get(
                f"{self.base_url}/sse",
                headers={"Accept": "text/event-stream"}
            )
            response.raise_for_status()
            
            # Start reading events
            asyncio.create_task(self._read_events(response))
            
            self._connected = True
            
        except ImportError:
            raise ImportError("aiohttp is required for SSE transport")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to SSE: {e}")
    
    async def _read_events(self, response: Any) -> None:
        """Read SSE events from the response."""
        try:
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data:'):
                    data = line[5:].strip()
                    await self._message_queue.put(data)
        except Exception:
            pass
        finally:
            self._connected = False
    
    async def send(self, message: str) -> None:
        """Send a message via POST request."""
        if not self._connected or self._session is None:
            raise ConnectionError("Not connected")
        
        try:
            response = await self._session.post(
                f"{self.base_url}/message",
                json=json.loads(message),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"Failed to send message: {e}")
    
    async def receive(self) -> Optional[str]:
        """Receive a message from the queue."""
        if not self._connected:
            return None
        
        try:
            return await asyncio.wait_for(
                self._message_queue.get(),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            return None
    
    async def close(self) -> None:
        """Close the connection."""
        self._connected = False
        
        if self._session is not None:
            await self._session.close()
            self._session = None
    
    @property
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        return self._connected


# =============================================================================
# MCP Client
# =============================================================================

class ClientState(Enum):
    """Client lifecycle states."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    INITIALIZING = auto()
    READY = auto()
    DISCONNECTING = auto()


class MCPClient:
    """
    Model Context Protocol Client implementation.
    
    Supports:
    - Connection management (stdio, sse)
    - Lifecycle handling (initialize, initialized, shutdown)
    - Resource operations (list, read)
    - Tool operations (list, call)
    - Prompt operations (list, get)
    
    Example:
        client = MCPClient("my-client", "1.0.0")
        await client.connect_stdio(["python", "server.py"])
        
        resources = await client.list_resources()
        tools = await client.list_tools()
        
        await client.disconnect()
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        capabilities: Optional[ClientCapabilities] = None
    ):
        """
        Initialize the MCP client.
        
        Args:
            name: Client name
            version: Client version
            capabilities: Client capabilities
        """
        self.name = name
        self.version = version
        self._capabilities = capabilities or ClientCapabilities()
        
        # State
        self._state = ClientState.DISCONNECTED
        self._transport: Optional[ClientTransport] = None
        self._server_capabilities: Optional[ServerCapabilities] = None
        self._server_info: Optional[Dict[str, str]] = None
        
        # Request tracking
        self._request_counter = 0
        self._pending_requests: Dict[Union[str, int], asyncio.Future] = {}
        self._lock = asyncio.Lock()
        
        # Message reading task
        self._read_task: Optional[asyncio.Task] = None
    
    # ==========================================================================
    # Properties
    # ==========================================================================
    
    @property
    def state(self) -> ClientState:
        """Get current client state."""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._state in (ClientState.READY, ClientState.INITIALIZING)
    
    @property
    def is_ready(self) -> bool:
        """Check if client is ready (initialized)."""
        return self._state == ClientState.READY
    
    @property
    def server_capabilities(self) -> Optional[ServerCapabilities]:
        """Get server capabilities (available after initialization)."""
        return self._server_capabilities
    
    @property
    def server_info(self) -> Optional[Dict[str, str]]:
        """Get server info (available after initialization)."""
        return self._server_info
    
    # ==========================================================================
    # Connection Management
    # ==========================================================================
    
    async def connect_stdio(
        self,
        command: List[str],
        env: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Connect to an MCP server via stdio.
        
        Args:
            command: Command and arguments to spawn the server
            env: Optional environment variables
        """
        transport = StdioClientTransport(command, env)
        await self._connect(transport)
    
    async def connect_sse(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Connect to an MCP server via SSE.
        
        Args:
            base_url: Base URL of the MCP server
            headers: Optional HTTP headers
        """
        transport = SSEClientTransport(base_url, headers)
        await self._connect(transport)
    
    async def _connect(self, transport: ClientTransport) -> None:
        """Internal connect method."""
        if self._state != ClientState.DISCONNECTED:
            raise RuntimeError("Client already connected")
        
        self._state = ClientState.CONNECTING
        self._transport = transport
        
        try:
            await transport.connect()
            
            # Start message reading task
            self._read_task = asyncio.create_task(self._read_messages())
            
            # Initialize
            await self._initialize()
            
        except Exception as e:
            await self.disconnect()
            raise ConnectionError(f"Failed to connect: {e}")
    
    async def _initialize(self) -> None:
        """Perform MCP initialization handshake."""
        self._state = ClientState.INITIALIZING
        
        # Send initialize request
        request = InitializeRequest(
            protocolVersion=MCP_PROTOCOL_VERSION,
            capabilities=self._capabilities,
            clientInfo={"name": self.name, "version": self.version}
        )
        
        response = await self._request(
            MCPMethod.INITIALIZE.value,
            request.to_dict()
        )
        
        # Parse response
        result = InitializeResult.from_dict(response)
        self._server_capabilities = result.capabilities
        self._server_info = result.serverInfo
        
        # Send initialized notification
        await self._notify(MCPMethod.INITIALIZED.value, {})
        
        self._state = ClientState.READY
    
    async def disconnect(self) -> None:
        """Disconnect from the server."""
        if self._state == ClientState.DISCONNECTED:
            return
        
        self._state = ClientState.DISCONNECTING
        
        # Cancel read task
        if self._read_task is not None:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None
        
        # Cancel pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
        
        # Close transport
        if self._transport is not None:
            await self._transport.close()
            self._transport = None
        
        self._state = ClientState.DISCONNECTED
        self._server_capabilities = None
        self._server_info = None
    
    async def __aenter__(self) -> MCPClient:
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
    
    # ==========================================================================
    # Message Handling
    # ==========================================================================
    
    def _next_id(self) -> int:
        """Generate next request ID."""
        self._request_counter += 1
        return self._request_counter
    
    async def _read_messages(self) -> None:
        """Background task to read messages from the server."""
        try:
            while self._state in (ClientState.INITIALIZING, ClientState.READY):
                message = await self._transport.receive()
                if message is None:
                    # Server disconnected
                    break
                
                if not message.strip():
                    continue
                
                try:
                    parsed = parse_message(message)
                    if isinstance(parsed, JSONRPCResponse):
                        await self._handle_response(parsed)
                except Exception:
                    # Ignore parse errors for now
                    pass
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            # Connection error
            pass
        finally:
            # Mark as disconnected
            if self._state != ClientState.DISCONNECTED:
                asyncio.create_task(self.disconnect())
    
    async def _handle_response(self, response: JSONRPCResponse) -> None:
        """Handle a response from the server."""
        req_id = response.id
        
        if req_id in self._pending_requests:
            future = self._pending_requests.pop(req_id)
            if not future.done():
                if response.is_error():
                    future.set_exception(
                        MCPError(response.error.code, response.error.message, response.error.data)
                    )
                else:
                    future.set_result(response.result)
    
    async def _request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Send a request and wait for response.
        
        Args:
            method: Method name
            params: Method parameters
            timeout: Request timeout in seconds
        
        Returns:
            Response result
        
        Raises:
            MCPError: If request fails
            asyncio.TimeoutError: If request times out
        """
        if self._transport is None or not self._transport.is_connected:
            raise ConnectionError("Not connected")
        
        req_id = self._next_id()
        request = create_request(method, params, req_id)
        
        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[req_id] = future
        
        try:
            # Send request
            message = serialize_message(request)
            await self._transport.send(message)
            
            # Wait for response
            return await asyncio.wait_for(future, timeout=timeout)
        
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            raise
        except Exception:
            self._pending_requests.pop(req_id, None)
            raise
    
    async def _notify(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send a notification (no response expected).
        
        Args:
            method: Method name
            params: Method parameters
        """
        if self._transport is None or not self._transport.is_connected:
            raise ConnectionError("Not connected")
        
        request = create_request(method, params, None)  # No id = notification
        message = serialize_message(request)
        await self._transport.send(message)
    
    # ==========================================================================
    # Resource Operations
    # ==========================================================================
    
    async def list_resources(self) -> List[Resource]:
        """
        List available resources.
        
        Returns:
            List of resources
        """
        if not self.is_ready:
            raise RuntimeError("Client not ready")
        
        response = await self._request(MCPMethod.RESOURCES_LIST.value)
        result = ListResourcesResult(resources=[])
        
        if "resources" in response:
            result.resources = [
                Resource.from_dict(r) for r in response["resources"]
            ]
        
        return result.resources
    
    async def read_resource(self, uri: str) -> List[ResourceContent]:
        """
        Read a resource by URI.
        
        Args:
            uri: Resource URI
        
        Returns:
            Resource contents
        """
        if not self.is_ready:
            raise RuntimeError("Client not ready")
        
        response = await self._request(
            MCPMethod.RESOURCES_READ.value,
            {"uri": uri}
        )
        
        result = ReadResourceResult(contents=[])
        
        if "contents" in response:
            result.contents = [
                ResourceContent.from_dict(c) for c in response["contents"]
            ]
        
        return result.contents
    
    # ==========================================================================
    # Tool Operations
    # ==========================================================================
    
    async def list_tools(self) -> List[Tool]:
        """
        List available tools.
        
        Returns:
            List of tools
        """
        if not self.is_ready:
            raise RuntimeError("Client not ready")
        
        response = await self._request(MCPMethod.TOOLS_LIST.value)
        result = ListToolsResult(tools=[])
        
        if "tools" in response:
            result.tools = [Tool.from_dict(t) for t in response["tools"]]
        
        return result.tools
    
    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> CallToolResult:
        """
        Call a tool.
        
        Args:
            name: Tool name
            arguments: Tool arguments
        
        Returns:
            Tool result
        """
        if not self.is_ready:
            raise RuntimeError("Client not ready")
        
        params = {"name": name}
        if arguments is not None:
            params["arguments"] = arguments
        
        response = await self._request(MCPMethod.TOOLS_CALL.value, params)
        
        return CallToolResult(
            content=response.get("content", []),
            isError=response.get("isError", False)
        )
    
    # ==========================================================================
    # Prompt Operations
    # ==========================================================================
    
    async def list_prompts(self) -> List[Prompt]:
        """
        List available prompts.
        
        Returns:
            List of prompts
        """
        if not self.is_ready:
            raise RuntimeError("Client not ready")
        
        response = await self._request(MCPMethod.PROMPTS_LIST.value)
        result = ListPromptsResult(prompts=[])
        
        if "prompts" in response:
            result.prompts = [Prompt.from_dict(p) for p in response["prompts"]]
        
        return result.prompts
    
    async def get_prompt(
        self,
        name: str,
        arguments: Optional[Dict[str, str]] = None
    ) -> GetPromptResult:
        """
        Get a prompt.
        
        Args:
            name: Prompt name
            arguments: Prompt arguments
        
        Returns:
            Prompt result
        """
        if not self.is_ready:
            raise RuntimeError("Client not ready")
        
        params = {"name": name}
        if arguments is not None:
            params["arguments"] = arguments
        
        response = await self._request(MCPMethod.PROMPTS_GET.value, params)
        
        messages = []
        if "messages" in response:
            messages = [
                PromptMessage(role=m["role"], content=m["content"])
                for m in response["messages"]
            ]
        
        return GetPromptResult(
            description=response.get("description"),
            messages=messages
        )


# Import os for environment variables
import os
from enum import Enum
