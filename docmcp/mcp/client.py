"""
MCP (Model Context Protocol) client implementation.

This module provides MCP client functionality with support for:
    - Connection management
    - Request/response handling
    - Connection pooling
    - Automatic reconnection
    - Timeout handling
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic
from collections import deque

from docmcp.mcp.protocol import (
    MCPMessage,
    MCPResponse,
    MCPRequest,
    MCPError,
    MCPErrorCode,
)

logger = logging.getLogger(__name__)


@dataclass
class ConnectionConfig:
    """Configuration for MCP client connections."""

    host: str = "localhost"
    port: int = 8080
    timeout_seconds: float = 30.0
    keepalive_interval: float = 30.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    ssl_enabled: bool = False
    ssl_verify: bool = True
    headers: Dict[str, str] = field(default_factory=dict)


class MCPConnection:
    """
    Single MCP connection.

    Manages a single connection to an MCP server, including
    message sending/receiving and connection state.
    """

    def __init__(self, connection_id: str, config: ConnectionConfig):
        self.id = connection_id
        self.config = config
        self._connected = False
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._last_activity = time.time()
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self._connected and self._writer is not None

    @property
    def idle_time(self) -> float:
        """Time since last activity."""
        return time.time() - self._last_activity

    async def connect(self) -> bool:
        """
        Establish connection to server.

        Returns:
            True if connected successfully
        """
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.host, self.config.port),
                timeout=self.config.timeout_seconds
            )
            self._connected = True
            self._last_activity = time.time()

            # Start message handler
            asyncio.create_task(self._message_handler())

            logger.info(f"Connected to {self.config.host}:{self.config.port}")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Close the connection."""
        self._connected = False

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

        # Cancel pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()

        logger.info(f"Disconnected from {self.config.host}:{self.config.port}")

    async def send_request(
        self,
        request: MCPRequest,
    ) -> MCPResponse:
        """
        Send a request and wait for response.

        Args:
            request: Request to send

        Returns:
            Response from server
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to server")

        message = request.to_message()
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        async with self._lock:
            self._pending_requests[request.id] = future

        try:
            # Send message
            await self._send_message(message)

            # Wait for response
            response = await asyncio.wait_for(
                future,
                timeout=self.config.timeout_seconds
            )

            self._last_activity = time.time()
            return response

        except asyncio.TimeoutError:
            error = MCPError.timeout(request.method, self.config.timeout_seconds)
            return MCPResponse.error(request.id, error)

        finally:
            async with self._lock:
                self._pending_requests.pop(request.id, None)

    async def _send_message(self, message: MCPMessage) -> None:
        """Send a message to the server."""
        if not self._writer:
            raise ConnectionError("Not connected")

        data = message.to_json().encode() + b"\n"
        self._writer.write(data)
        await self._writer.drain()

    async def _message_handler(self) -> None:
        """Handle incoming messages from server."""
        while self._connected and self._reader:
            try:
                line = await self._reader.readline()
                if not line:
                    break

                message = MCPMessage.from_json(line.decode().strip())
                self._last_activity = time.time()

                # Handle response
                if message.id and message.id in self._pending_requests:
                    future = self._pending_requests.get(message.id)
                    if future and not future.done():
                        response = MCPResponse.from_message(message)
                        future.set_result(response)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Message handler error: {e}")


class ConnectionPool:
    """
    Pool of MCP connections.

    Manages a pool of reusable connections for efficient
    communication with MCP servers.

    Attributes:
        config: Connection configuration
        min_connections: Minimum number of connections to maintain
        max_connections: Maximum number of connections allowed

    Example:
        >>> config = ConnectionConfig(host="localhost", port=8080)
        >>> pool = ConnectionPool(config, min_connections=2, max_connections=10)
        >>> await pool.initialize()
        >>>
        >>> # Get connection and send request
        >>> conn = await pool.acquire()
        >>> response = await conn.send_request(request)
        >>> await pool.release(conn)
    """

    def __init__(
        self,
        config: ConnectionConfig,
        min_connections: int = 2,
        max_connections: int = 10,
    ):
        self.config = config
        self.min_connections = min_connections
        self.max_connections = max_connections

        self._pool: deque[MCPConnection] = deque()
        self._in_use: Dict[str, MCPConnection] = {}
        self._connection_count = 0
        self._semaphore = asyncio.Semaphore(max_connections)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        if self._initialized:
            return

        # Create minimum connections
        for _ in range(self.min_connections):
            conn = await self._create_connection()
            if conn:
                self._pool.append(conn)

        self._initialized = True
        logger.info(f"Connection pool initialized with {len(self._pool)} connections")

    async def close(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            # Close pooled connections
            while self._pool:
                conn = self._pool.popleft()
                await conn.disconnect()

            # Close in-use connections
            for conn in list(self._in_use.values()):
                await conn.disconnect()
            self._in_use.clear()

        self._initialized = False
        logger.info("Connection pool closed")

    async def _create_connection(self) -> Optional[MCPConnection]:
        """Create a new connection."""
        if self._connection_count >= self.max_connections:
            return None

        conn = MCPConnection(
            connection_id=f"conn-{self._connection_count}",
            config=self.config
        )

        if await conn.connect():
            self._connection_count += 1
            return conn

        return None

    async def acquire(self, timeout: float = 30.0) -> MCPConnection:
        """
        Acquire a connection from the pool.

        Args:
            timeout: Maximum time to wait for a connection

        Returns:
            An available connection

        Raises:
            TimeoutError: If no connection available within timeout
        """
        async with self._semaphore:
            async with self._lock:
                # Try to get from pool
                while self._pool:
                    conn = self._pool.popleft()
                    if conn.is_connected:
                        self._in_use[conn.id] = conn
                        return conn
                    # Remove dead connection
                    self._connection_count -= 1

                # Create new connection
                conn = await self._create_connection()
                if conn:
                    self._in_use[conn.id] = conn
                    return conn

            # Wait for a connection to become available
            start = time.time()
            while time.time() - start < timeout:
                async with self._lock:
                    if self._pool:
                        conn = self._pool.popleft()
                        if conn.is_connected:
                            self._in_use[conn.id] = conn
                            return conn

                await asyncio.sleep(0.1)

            raise TimeoutError("Could not acquire connection from pool")

    async def release(self, conn: MCPConnection) -> None:
        """
        Release a connection back to the pool.

        Args:
            conn: Connection to release
        """
        async with self._lock:
            self._in_use.pop(conn.id, None)

            if conn.is_connected:
                self._pool.append(conn)
            else:
                self._connection_count -= 1

    @property
    def available(self) -> int:
        """Number of available connections in pool."""
        return len(self._pool)

    @property
    def in_use(self) -> int:
        """Number of connections currently in use."""
        return len(self._in_use)

    @property
    def total(self) -> int:
        """Total number of connections."""
        return self._connection_count


class MCPClient:
    """
    High-level MCP client.

    Provides a convenient interface for interacting with MCP servers,
    with automatic connection management and retry logic.

    Example:
        >>> client = MCPClient(ConnectionConfig(host="localhost", port=8080))
        >>> await client.connect()
        >>>
        >>> # Call a method
        >>> response = await client.call("process_document", {"document_id": "doc-123"})
        >>>
        >>> await client.disconnect()
    """

    def __init__(
        self,
        config: ConnectionConfig,
        use_pool: bool = True,
        pool_size: int = 5,
    ):
        self.config = config
        self.use_pool = use_pool

        self._connection: Optional[MCPConnection] = None
        self._pool: Optional[ConnectionPool] = None

        if use_pool:
            self._pool = ConnectionPool(
                config=config,
                max_connections=pool_size,
            )

    async def connect(self) -> bool:
        """
        Connect to the MCP server.

        Returns:
            True if connected successfully
        """
        if self.use_pool:
            await self._pool.initialize()
            return True
        else:
            self._connection = MCPConnection("single", self.config)
            return await self._connection.connect()

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.use_pool and self._pool:
            await self._pool.close()
        elif self._connection:
            await self._connection.disconnect()
            self._connection = None

    async def call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> MCPResponse:
        """
        Call an MCP method.

        Args:
            method: Method name
            params: Method parameters
            timeout: Request timeout

        Returns:
            MCPResponse from server
        """
        request = MCPRequest(
            method=method,
            params=params or {},
        )

        if timeout:
            request.context["timeout"] = timeout

        if self.use_pool and self._pool:
            conn = await self._pool.acquire()
            try:
                return await conn.send_request(request)
            finally:
                await self._pool.release(conn)
        elif self._connection:
            return await self._connection.send_request(request)
        else:
            raise ConnectionError("Not connected to server")

    async def call_with_retry(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: Optional[int] = None,
    ) -> MCPResponse:
        """
        Call an MCP method with automatic retry.

        Args:
            method: Method name
            params: Method parameters
            max_retries: Maximum retry attempts

        Returns:
            MCPResponse from server
        """
        max_retries = max_retries or self.config.max_retries
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await self.call(method, params)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = self.config.retry_delay_seconds * (2 ** attempt)
                    logger.warning(f"Call failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)

        error = MCPError.internal_error(f"Max retries exceeded: {last_error}")
        return MCPResponse.error("", error)

    async def health_check(self) -> Dict[str, Any]:
        """Check server health."""
        response = await self.call("health_check")
        return response.get_result() or {}

    async def get_capabilities(self) -> List[Dict[str, Any]]:
        """Get server capabilities."""
        response = await self.call("get_capabilities")
        result = response.get_result() or {}
        return result.get("capabilities", [])
