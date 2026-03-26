"""
MCP (Model Context Protocol) server implementation.

This module provides a complete MCP server implementation with support for:
    - Request/response handling
    - Method routing
    - Connection management
    - Capability advertisement
    - Health monitoring
    - Metrics collection

The server can be used standalone or integrated into existing applications.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Generic
from collections import defaultdict

from docmcp.mcp.protocol import (
    MCPMessage,
    MCPResponse,
    MCPRequest,
    MCPError,
    MCPErrorCode,
    MCPMethod,
    MCPCapability,
)

logger = logging.getLogger(__name__)


class MCPHandler(ABC):
    """
    Abstract base class for MCP method handlers.
    
    Handlers process specific MCP methods and return responses.
    
    Example:
        >>> class MyHandler(MCPHandler):
        ...     @property
        ...     def method(self) -> str:
        ...         return "my_method"
        ...     
        ...     async def handle(self, request: MCPRequest) -> MCPResponse:
        ...         # Process request
        ...         return MCPResponse.success(request.id, result)
    """
    
    @property
    @abstractmethod
    def method(self) -> str:
        """Get the method name this handler handles."""
        pass
    
    @abstractmethod
    async def handle(self, request: MCPRequest) -> MCPResponse:
        """
        Handle an MCP request.
        
        Args:
            request: The MCP request to handle
            
        Returns:
            MCPResponse with result or error
        """
        pass
    
    def get_capabilities(self) -> List[MCPCapability]:
        """
        Get capabilities provided by this handler.
        
        Returns:
            List of capabilities
        """
        return []


@dataclass
class ConnectionInfo:
    """Information about an MCP connection."""
    
    id: str
    connected_at: float
    last_activity: float
    client_info: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    request_count: int = 0
    
    @property
    def idle_time(self) -> float:
        """Time since last activity."""
        return time.time() - self.last_activity
    
    @property
    def connection_duration(self) -> float:
        """Total connection duration."""
        return time.time() - self.connected_at


class ConnectionManager:
    """
    Manages MCP client connections.
    
    Provides connection tracking, idle detection, and cleanup.
    """
    
    def __init__(
        self,
        max_connections: int = 1000,
        idle_timeout_seconds: float = 300.0,
    ):
        self.max_connections = max_connections
        self.idle_timeout_seconds = idle_timeout_seconds
        self._connections: Dict[str, ConnectionInfo] = {}
        self._lock = asyncio.Lock()
    
    async def connect(
        self,
        connection_id: str,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> ConnectionInfo:
        """
        Register a new connection.
        
        Args:
            connection_id: Unique connection identifier
            client_info: Optional client information
            
        Returns:
            ConnectionInfo for the new connection
        """
        async with self._lock:
            if len(self._connections) >= self.max_connections:
                raise RuntimeError("Maximum connections reached")
            
            now = time.time()
            conn = ConnectionInfo(
                id=connection_id,
                connected_at=now,
                last_activity=now,
                client_info=client_info or {},
            )
            self._connections[connection_id] = conn
            logger.info(f"New connection: {connection_id}")
            return conn
    
    async def disconnect(self, connection_id: str) -> bool:
        """
        Disconnect a client.
        
        Args:
            connection_id: Connection to disconnect
            
        Returns:
            True if disconnected, False if not found
        """
        async with self._lock:
            if connection_id in self._connections:
                del self._connections[connection_id]
                logger.info(f"Disconnected: {connection_id}")
                return True
            return False
    
    async def update_activity(self, connection_id: str) -> bool:
        """
        Update last activity time for a connection.
        
        Args:
            connection_id: Connection to update
            
        Returns:
            True if updated, False if not found
        """
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].last_activity = time.time()
                self._connections[connection_id].request_count += 1
                return True
            return False
    
    async def get_connection(self, connection_id: str) -> Optional[ConnectionInfo]:
        """Get connection info by ID."""
        async with self._lock:
            return self._connections.get(connection_id)
    
    async def get_all_connections(self) -> List[ConnectionInfo]:
        """Get all active connections."""
        async with self._lock:
            return list(self._connections.values())
    
    async def cleanup_idle_connections(self) -> int:
        """
        Remove idle connections.
        
        Returns:
            Number of connections removed
        """
        now = time.time()
        to_remove = []
        
        async with self._lock:
            for conn_id, conn in self._connections.items():
                if conn.idle_time > self.idle_timeout_seconds:
                    to_remove.append(conn_id)
            
            for conn_id in to_remove:
                del self._connections[conn_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} idle connections")
        
        return len(to_remove)
    
    @property
    def connection_count(self) -> int:
        """Get current connection count."""
        return len(self._connections)


class MCPServer:
    """
    MCP (Model Context Protocol) server.
    
    This server implements the MCP protocol for document processing,
    providing a standardized interface for AI model integration.
    
    Features:
        - Method routing and handler registration
        - Connection management
        - Capability advertisement
        - Health monitoring
        - Metrics collection
        - Request batching
    
    Attributes:
        name: Server name
        version: Server version
        handlers: Registered method handlers
        connection_manager: Connection manager instance
    
    Example:
        >>> server = MCPServer(name="docmcp-server", version="1.0.0")
        >>> server.register_handler(MyHandler())
        >>> await server.start()
        >>> 
        >>> # Handle a message
        >>> response = await server.handle_message(message)
    """
    
    def __init__(
        self,
        name: str = "docmcp-server",
        version: str = "1.0.0",
        max_connections: int = 1000,
        enable_metrics: bool = True,
    ):
        self.name = name
        self.version = version
        self.enable_metrics = enable_metrics
        
        # Handlers
        self._handlers: Dict[str, MCPHandler] = {}
        self._default_handler: Optional[Callable] = None
        
        # Connection management
        self.connection_manager = ConnectionManager(max_connections=max_connections)
        
        # Capabilities
        self._capabilities: List[MCPCapability] = []
        
        # Metrics
        self._metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_error": 0,
            "request_duration_ms": defaultdict(list),
        }
        
        # State
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Register built-in handlers
        self._register_builtin_handlers()
        
        logger.info(f"MCP Server initialized: {name} v{version}")
    
    def _register_builtin_handlers(self) -> None:
        """Register built-in MCP method handlers."""
        # These will be implemented as needed
        pass
    
    async def start(self) -> None:
        """Start the MCP server."""
        if self._running:
            logger.warning("Server is already running")
            return
        
        self._running = True
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(),
            name="mcp-cleanup"
        )
        
        logger.info("MCP Server started")
    
    async def stop(self) -> None:
        """Stop the MCP server."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("MCP Server stopped")
    
    async def _cleanup_loop(self) -> None:
        """Background task for periodic cleanup."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self.connection_manager.cleanup_idle_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    def register_handler(self, handler: MCPHandler) -> None:
        """
        Register an MCP method handler.
        
        Args:
            handler: Handler instance
        """
        self._handlers[handler.method] = handler
        
        # Add handler capabilities
        for cap in handler.get_capabilities():
            self._capabilities.append(cap)
        
        logger.info(f"Registered handler for method: {handler.method}")
    
    def register_handlers(self, *handlers: MCPHandler) -> None:
        """
        Register multiple handlers.
        
        Args:
            *handlers: Handler instances
        """
        for handler in handlers:
            self.register_handler(handler)
    
    def set_default_handler(
        self,
        handler: Callable[[MCPRequest], asyncio.Future[MCPResponse]]
    ) -> None:
        """
        Set a default handler for unregistered methods.
        
        Args:
            handler: Default handler function
        """
        self._default_handler = handler
    
    def add_capability(self, capability: MCPCapability) -> None:
        """
        Add a server capability.
        
        Args:
            capability: Capability to add
        """
        self._capabilities.append(capability)
    
    def get_capabilities(self) -> List[MCPCapability]:
        """Get all server capabilities."""
        return self._capabilities.copy()
    
    async def handle_message(
        self,
        message: MCPMessage,
        connection_id: Optional[str] = None,
    ) -> MCPMessage:
        """
        Handle an incoming MCP message.
        
        Args:
            message: The MCP message to handle
            connection_id: Optional connection identifier
            
        Returns:
            MCP response message
        """
        start_time = time.time()
        
        # Update connection activity
        if connection_id:
            await self.connection_manager.update_activity(connection_id)
        
        # Update metrics
        if self.enable_metrics:
            self._metrics["requests_total"] += 1
        
        try:
            # Handle batch messages
            if isinstance(message, list):
                responses = []
                for msg in message:
                    response = await self._handle_single_message(
                        MCPMessage.from_dict(msg) if isinstance(msg, dict) else msg
                    )
                    responses.append(response.to_dict())
                return responses
            
            # Handle single message
            response = await self._handle_single_message(message)
            
            # Update success metrics
            if self.enable_metrics:
                if response.is_success():
                    self._metrics["requests_success"] += 1
                else:
                    self._metrics["requests_error"] += 1
                
                duration_ms = (time.time() - start_time) * 1000
                method = message.method or "unknown"
                self._metrics["request_duration_ms"][method].append(duration_ms)
            
            return response.to_message()
        
        except Exception as e:
            logger.exception(f"Message handling error: {e}")
            
            if self.enable_metrics:
                self._metrics["requests_error"] += 1
            
            error = MCPError.internal_error(str(e))
            return MCPMessage.error_response(message.id, error)
    
    async def _handle_single_message(self, message: MCPMessage) -> MCPResponse:
        """
        Handle a single MCP message.
        
        Args:
            message: The MCP message
            
        Returns:
            MCPResponse
        """
        # Validate message
        if not message.is_request() and not message.is_notification():
            error = MCPError.invalid_request("Message is not a request")
            return MCPResponse.error(message.id or "", error)
        
        # Handle notifications (no response needed)
        if message.is_notification():
            # Process notification asynchronously
            asyncio.create_task(self._process_notification(message))
            # Return empty success for notifications
            return MCPResponse.success(message.id or "", None)
        
        # Get method handler
        method = message.method
        handler = self._handlers.get(method)
        
        if handler is None and self._default_handler:
            # Use default handler
            request = MCPRequest.from_message(message)
            return await self._default_handler(request)
        
        if handler is None:
            error = MCPError.method_not_found(method or "")
            return MCPResponse.error(message.id or "", error)
        
        # Handle request
        request = MCPRequest.from_message(message)
        
        try:
            return await handler.handle(request)
        except Exception as e:
            logger.exception(f"Handler error for method {method}: {e}")
            error = MCPError.internal_error(str(e))
            return MCPResponse.error(message.id or "", error)
    
    async def _process_notification(self, message: MCPMessage) -> None:
        """Process a notification message (fire and forget)."""
        # Implementation depends on notification type
        logger.debug(f"Processing notification: {message.method}")
    
    async def connect_client(
        self,
        connection_id: str,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> ConnectionInfo:
        """
        Register a new client connection.
        
        Args:
            connection_id: Unique connection identifier
            client_info: Optional client information
            
        Returns:
            ConnectionInfo for the new connection
        """
        return await self.connection_manager.connect(connection_id, client_info)
    
    async def disconnect_client(self, connection_id: str) -> bool:
        """
        Disconnect a client.
        
        Args:
            connection_id: Connection to disconnect
            
        Returns:
            True if disconnected
        """
        return await self.connection_manager.disconnect(connection_id)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get server metrics."""
        metrics = self._metrics.copy()
        
        # Calculate average durations
        avg_durations = {}
        for method, durations in self._metrics["request_duration_ms"].items():
            if durations:
                avg_durations[method] = sum(durations) / len(durations)
        metrics["average_duration_ms"] = avg_durations
        
        # Add connection metrics
        metrics["active_connections"] = self.connection_manager.connection_count
        
        return metrics
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health status dictionary
        """
        return {
            "status": "healthy" if self._running else "unhealthy",
            "server": self.name,
            "version": self.version,
            "running": self._running,
            "connections": self.connection_manager.connection_count,
            "handlers": len(self._handlers),
            "capabilities": len(self._capabilities),
        }


# Built-in handlers

class GetCapabilitiesHandler(MCPHandler):
    """Handler for get_capabilities method."""
    
    def __init__(self, server: MCPServer):
        self._server = server
    
    @property
    def method(self) -> str:
        return MCPMethod.GET_CAPABILITIES.value
    
    async def handle(self, request: MCPRequest) -> MCPResponse:
        """Return server capabilities."""
        capabilities = [
            cap.to_dict() for cap in self._server.get_capabilities()
        ]
        
        result = {
            "server": self._server.name,
            "version": self._server.version,
            "capabilities": capabilities,
            "methods": list(self._server._handlers.keys()),
        }
        
        return MCPResponse.success(request.id, result)


class HealthCheckHandler(MCPHandler):
    """Handler for health_check method."""
    
    def __init__(self, server: MCPServer):
        self._server = server
    
    @property
    def method(self) -> str:
        return MCPMethod.HEALTH_CHECK.value
    
    async def handle(self, request: MCPRequest) -> MCPResponse:
        """Return health status."""
        health = await self._server.health_check()
        return MCPResponse.success(request.id, health)


class GetMetricsHandler(MCPHandler):
    """Handler for get_metrics method."""
    
    def __init__(self, server: MCPServer):
        self._server = server
    
    @property
    def method(self) -> str:
        return MCPMethod.GET_METRICS.value
    
    async def handle(self, request: MCPRequest) -> MCPResponse:
        """Return server metrics."""
        metrics = self._server.get_metrics()
        return MCPResponse.success(request.id, metrics)
