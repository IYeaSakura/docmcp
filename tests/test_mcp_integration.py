"""
MCP (Model Context Protocol) integration tests.

This module tests:
- MCP protocol message handling
- MCP server functionality
- Request/Response processing
- Error handling
- Connection management
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from docmcp.mcp.protocol import (
    MCPMessage,
    MCPResponse,
    MCPRequest,
    MCPError,
    MCPErrorCode,
    MCPMethod,
    MCPCapability,
    MCPBatch,
)
from docmcp.mcp.server import (
    MCPServer,
    MCPHandler,
    ConnectionManager,
    ConnectionInfo,
    GetCapabilitiesHandler,
    HealthCheckHandler,
    GetMetricsHandler,
)


# ============================================================================
# MCPError Tests
# ============================================================================

class TestMCPError:
    """Test MCPError class."""

    def test_error_creation(self):
        """Test error creation."""
        error = MCPError(
            code=MCPErrorCode.DOCUMENT_NOT_FOUND.value,
            message="Document not found",
            data={"document_id": "doc-123"},
        )
        assert error.code == -32001
        assert error.message == "Document not found"
        assert error.data == {"document_id": "doc-123"}

    def test_error_to_dict(self):
        """Test error serialization."""
        error = MCPError(
            code=MCPErrorCode.INVALID_PARAMS.value,
            message="Invalid parameters",
        )
        data = error.to_dict()
        assert data["code"] == -32602
        assert data["message"] == "Invalid parameters"

    def test_error_from_dict(self):
        """Test error deserialization."""
        data = {
            "code": -32001,
            "message": "Document not found",
            "data": {"document_id": "doc-123"},
        }
        error = MCPError.from_dict(data)
        assert error.code == -32001
        assert error.message == "Document not found"

    def test_parse_error_factory(self):
        """Test parse error factory method."""
        error = MCPError.parse_error("Invalid JSON")
        assert error.code == MCPErrorCode.PARSE_ERROR.value
        assert "Invalid JSON" in error.message

    def test_invalid_request_factory(self):
        """Test invalid request factory method."""
        error = MCPError.invalid_request("Missing method")
        assert error.code == MCPErrorCode.INVALID_REQUEST.value

    def test_method_not_found_factory(self):
        """Test method not found factory method."""
        error = MCPError.method_not_found("unknown_method")
        assert error.code == MCPErrorCode.METHOD_NOT_FOUND.value
        assert "unknown_method" in error.message

    def test_document_not_found_factory(self):
        """Test document not found factory method."""
        error = MCPError.document_not_found("doc-123")
        assert error.code == MCPErrorCode.DOCUMENT_NOT_FOUND.value
        assert "doc-123" in error.message
        assert error.data == {"document_id": "doc-123"}

    def test_processing_failed_factory(self):
        """Test processing failed factory method."""
        error = MCPError.processing_failed(
            "Processing error",
            details={"step": "extraction"}
        )
        assert error.code == MCPErrorCode.PROCESSING_FAILED.value
        assert error.data == {"step": "extraction"}

    def test_timeout_factory(self):
        """Test timeout factory method."""
        error = MCPError.timeout("extraction", 30.0)
        assert error.code == MCPErrorCode.TIMEOUT.value
        assert "extraction" in error.message
        assert "30" in error.message


# ============================================================================
# MCPMessage Tests
# ============================================================================

class TestMCPMessage:
    """Test MCPMessage class."""

    def test_request_message_creation(self):
        """Test request message creation."""
        msg = MCPMessage.request(
            method="process_document",
            params={"document_id": "doc-123"},
            id="req-001",
        )
        assert msg.jsonrpc == "2.0"
        assert msg.method == "process_document"
        assert msg.params == {"document_id": "doc-123"}
        assert msg.id == "req-001"

    def test_request_auto_id_generation(self):
        """Test auto ID generation for requests."""
        msg = MCPMessage.request(method="test")
        assert msg.id is not None
        assert len(msg.id) > 0

    def test_notification_message_creation(self):
        """Test notification message creation."""
        msg = MCPMessage.notification(
            method="update_status",
            params={"status": "processing"},
        )
        assert msg.method == "update_status"
        assert msg.id is None  # Notifications have no ID

    def test_success_response_creation(self):
        """Test success response creation."""
        msg = MCPMessage.success_response(
            id="req-001",
            result={"status": "completed"},
        )
        assert msg.id == "req-001"
        assert msg.result == {"status": "completed"}
        assert msg.error is None

    def test_error_response_creation(self):
        """Test error response creation."""
        error = MCPError.document_not_found("doc-123")
        msg = MCPMessage.error_response("req-001", error)
        assert msg.id == "req-001"
        assert msg.error is not None
        assert msg.result is None

    def test_is_request(self):
        """Test is_request method."""
        request = MCPMessage.request(method="test", id="1")
        assert request.is_request() is True

        notification = MCPMessage.notification(method="test")
        assert notification.is_request() is False

        response = MCPMessage.success_response("1", {})
        assert response.is_request() is False

    def test_is_notification(self):
        """Test is_notification method."""
        notification = MCPMessage.notification(method="test")
        assert notification.is_notification() is True

        request = MCPMessage.request(method="test", id="1")
        assert request.is_notification() is False

    def test_is_response(self):
        """Test is_response method."""
        response = MCPMessage.success_response("1", {})
        assert response.is_response() is True

        request = MCPMessage.request(method="test", id="1")
        assert request.is_response() is False

    def test_is_success(self):
        """Test is_success method."""
        success = MCPMessage.success_response("1", {})
        assert success.is_success() is True

        error = MCPError.internal_error("test")
        failure = MCPMessage.error_response("1", error)
        assert failure.is_success() is False

    def test_is_error(self):
        """Test is_error method."""
        error = MCPError.internal_error("test")
        failure = MCPMessage.error_response("1", error)
        assert failure.is_error() is True

        success = MCPMessage.success_response("1", {})
        assert success.is_error() is False

    def test_to_dict(self):
        """Test message serialization."""
        msg = MCPMessage.request(method="test", params={"key": "value"}, id="1")
        data = msg.to_dict()
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "test"
        assert data["params"] == {"key": "value"}
        assert data["id"] == "1"

    def test_to_json(self):
        """Test message JSON serialization."""
        msg = MCPMessage.request(method="test", id="1")
        json_str = msg.to_json()
        assert '"jsonrpc": "2.0"' in json_str
        assert '"method": "test"' in json_str

    def test_from_dict(self):
        """Test message deserialization."""
        data = {
            "jsonrpc": "2.0",
            "method": "test",
            "params": {"key": "value"},
            "id": "1",
        }
        msg = MCPMessage.from_dict(data)
        assert msg.method == "test"
        assert msg.params == {"key": "value"}

    def test_from_json(self):
        """Test message JSON deserialization."""
        json_str = '{"jsonrpc": "2.0", "method": "test", "id": "1"}'
        msg = MCPMessage.from_json(json_str)
        assert msg.method == "test"
        assert msg.id == "1"


# ============================================================================
# MCPRequest Tests
# ============================================================================

class TestMCPRequest:
    """Test MCPRequest class."""

    def test_request_creation(self):
        """Test request creation."""
        req = MCPRequest(
            method="process_document",
            params={"document_id": "doc-123"},
            id="req-001",
        )
        assert req.method == "process_document"
        assert req.params == {"document_id": "doc-123"}
        assert req.id == "req-001"

    def test_request_auto_id(self):
        """Test auto ID generation."""
        req = MCPRequest(method="test")
        assert req.id is not None

    def test_to_message(self):
        """Test conversion to MCPMessage."""
        req = MCPRequest(method="test", params={"key": "value"}, id="1")
        msg = req.to_message()
        assert msg.method == "test"
        assert msg.params == {"key": "value"}

    def test_from_message(self):
        """Test creation from MCPMessage."""
        msg = MCPMessage.request(method="test", params={"key": "value"}, id="1")
        req = MCPRequest.from_message(msg)
        assert req.method == "test"
        assert req.params == {"key": "value"}


# ============================================================================
# MCPResponse Tests
# ============================================================================

class TestMCPResponse:
    """Test MCPResponse class."""

    def test_success_response(self):
        """Test success response creation."""
        resp = MCPResponse.success("req-001", {"status": "completed"})
        assert resp.id == "req-001"
        assert resp.result == {"status": "completed"}
        assert resp.error is None
        assert resp.is_success is True

    def test_error_response(self):
        """Test error response creation."""
        error = MCPError.internal_error("test error")
        resp = MCPResponse.error("req-001", error)
        assert resp.id == "req-001"
        assert resp.error == error
        assert resp.result is None
        assert resp.is_error is True

    def test_get_result(self):
        """Test get_result method."""
        resp = MCPResponse.success("1", {"key": "value", "nested": {"a": 1}})
        assert resp.get_result() == {"key": "value", "nested": {"a": 1}}
        assert resp.get_result("key") == "value"
        assert resp.get_result("nested") == {"a": 1}

    def test_get_result_on_error(self):
        """Test get_result raises on error response."""
        error = MCPError.internal_error("test")
        resp = MCPResponse.error("1", error)
        with pytest.raises(RuntimeError):
            resp.get_result()

    def test_to_message_success(self):
        """Test success response to message conversion."""
        resp = MCPResponse.success("1", {"status": "ok"})
        msg = resp.to_message()
        assert msg.result == {"status": "ok"}
        assert msg.error is None

    def test_to_message_error(self):
        """Test error response to message conversion."""
        error = MCPError.internal_error("test")
        resp = MCPResponse.error("1", error)
        msg = resp.to_message()
        assert msg.error is not None
        assert msg.result is None

    def test_from_message_success(self):
        """Test creation from success message."""
        msg = MCPMessage.success_response("1", {"status": "ok"})
        resp = MCPResponse.from_message(msg)
        assert resp.is_success is True
        assert resp.result == {"status": "ok"}

    def test_from_message_error(self):
        """Test creation from error message."""
        error = MCPError.internal_error("test")
        msg = MCPMessage.error_response("1", error)
        resp = MCPResponse.from_message(msg)
        assert resp.is_error is True
        assert resp.error is not None


# ============================================================================
# MCPBatch Tests
# ============================================================================

class TestMCPBatch:
    """Test MCPBatch class."""

    def test_batch_creation(self):
        """Test batch creation."""
        batch = MCPBatch()
        assert batch.messages == []

    def test_batch_add(self):
        """Test adding messages to batch."""
        batch = MCPBatch()
        msg1 = MCPMessage.request(method="test1", id="1")
        msg2 = MCPMessage.request(method="test2", id="2")

        batch.add(msg1)
        batch.add(msg2)

        assert len(batch.messages) == 2

    def test_batch_to_json(self):
        """Test batch JSON serialization."""
        batch = MCPBatch()
        batch.add(MCPMessage.request(method="test", id="1"))

        json_str = batch.to_json()
        assert '"jsonrpc": "2.0"' in json_str
        assert '"method": "test"' in json_str

    def test_batch_from_json(self):
        """Test batch JSON deserialization."""
        json_str = '[{"jsonrpc": "2.0", "method": "test", "id": "1"}]'
        batch = MCPBatch.from_json(json_str)

        assert len(batch.messages) == 1
        assert batch.messages[0].method == "test"

    def test_get_requests(self):
        """Test getting requests from batch."""
        batch = MCPBatch()
        batch.add(MCPMessage.request(method="test", id="1"))
        batch.add(MCPMessage.success_response("1", {}))

        requests = batch.get_requests()
        assert len(requests) == 1
        assert requests[0].method == "test"

    def test_get_responses(self):
        """Test getting responses from batch."""
        batch = MCPBatch()
        batch.add(MCPMessage.request(method="test", id="1"))
        batch.add(MCPMessage.success_response("1", {}))

        responses = batch.get_responses()
        assert len(responses) == 1
        assert responses[0].result == {}


# ============================================================================
# ConnectionManager Tests
# ============================================================================

@pytest.mark.asyncio
class TestConnectionManager:
    """Test ConnectionManager class."""

    async def test_connect(self):
        """Test client connection."""
        manager = ConnectionManager(max_connections=10)
        conn = await manager.connect("client-1", {"version": "1.0"})

        assert conn.id == "client-1"
        assert conn.client_info == {"version": "1.0"}
        assert conn.request_count == 0

    async def test_connect_max_connections(self):
        """Test max connections limit."""
        manager = ConnectionManager(max_connections=1)
        await manager.connect("client-1")

        with pytest.raises(RuntimeError, match="Maximum connections reached"):
            await manager.connect("client-2")

    async def test_disconnect(self):
        """Test client disconnection."""
        manager = ConnectionManager()
        await manager.connect("client-1")

        result = await manager.disconnect("client-1")
        assert result is True

        # Disconnect nonexistent client
        result = await manager.disconnect("client-1")
        assert result is False

    async def test_update_activity(self):
        """Test activity update."""
        manager = ConnectionManager()
        await manager.connect("client-1")

        result = await manager.update_activity("client-1")
        assert result is True

        conn = await manager.get_connection("client-1")
        assert conn.request_count == 1

    async def test_get_connection(self):
        """Test getting connection info."""
        manager = ConnectionManager()
        await manager.connect("client-1", {"name": "test"})

        conn = await manager.get_connection("client-1")
        assert conn is not None
        assert conn.client_info == {"name": "test"}

        # Nonexistent connection
        conn = await manager.get_connection("nonexistent")
        assert conn is None

    async def test_get_all_connections(self):
        """Test getting all connections."""
        manager = ConnectionManager()
        await manager.connect("client-1")
        await manager.connect("client-2")

        connections = await manager.get_all_connections()
        assert len(connections) == 2

    async def test_cleanup_idle_connections(self):
        """Test idle connection cleanup."""
        manager = ConnectionManager(idle_timeout_seconds=0.001)
        await manager.connect("client-1")

        # Wait for timeout
        await asyncio.sleep(0.01)

        count = await manager.cleanup_idle_connections()
        assert count == 1
        assert manager.connection_count == 0

    async def test_connection_count_property(self):
        """Test connection count property."""
        manager = ConnectionManager()
        assert manager.connection_count == 0

        await manager.connect("client-1")
        assert manager.connection_count == 1

        await manager.connect("client-2")
        assert manager.connection_count == 2


# ============================================================================
# MCPServer Tests
# ============================================================================

@pytest.mark.asyncio
class TestMCPServer:
    """Test MCPServer class."""

    async def test_server_creation(self):
        """Test server creation."""
        server = MCPServer(name="test-server", version="1.0.0")
        assert server.name == "test-server"
        assert server.version == "1.0.0"
        assert server.enable_metrics is True

    async def test_server_start_stop(self):
        """Test server start and stop."""
        server = MCPServer()

        await server.start()
        assert server._running is True

        await server.stop()
        assert server._running is False

    async def test_register_handler(self, mock_mcp_handler):
        """Test handler registration."""
        server = MCPServer()
        server.register_handler(mock_mcp_handler)

        assert "test_method" in server._handlers

    async def test_register_handlers(self, mock_mcp_handler):
        """Test multiple handler registration."""
        server = MCPServer()

        handler2 = MockMCPHandler("method2")
        server.register_handlers(mock_mcp_handler, handler2)

        assert "test_method" in server._handlers
        assert "method2" in server._handlers

    async def test_add_capability(self):
        """Test capability addition."""
        server = MCPServer()
        cap = MCPCapability(name="test_cap", version="1.0.0")

        server.add_capability(cap)
        assert len(server.get_capabilities()) == 1

    async def test_handle_message_success(self, mock_mcp_handler):
        """Test successful message handling."""
        server = MCPServer()
        server.register_handler(mock_mcp_handler)
        await server.start()

        request = MCPMessage.request(
            method="test_method",
            params={"key": "value"},
            id="req-001",
        )

        response = await server.handle_message(request)

        assert mock_mcp_handler.handle_called is True
        assert response.is_success() is True

        await server.stop()

    async def test_handle_message_method_not_found(self):
        """Test handling unknown method."""
        server = MCPServer()
        await server.start()

        request = MCPMessage.request(
            method="unknown_method",
            id="req-001",
        )

        response = await server.handle_message(request)

        assert response.is_error() is True
        assert response.error["code"] == MCPErrorCode.METHOD_NOT_FOUND.value

        await server.stop()

    async def test_handle_message_notification(self):
        """Test handling notification (no response needed)."""
        server = MCPServer()
        await server.start()

        notification = MCPMessage.notification(
            method="update_status",
            params={"status": "ok"},
        )

        response = await server.handle_message(notification)

        # Notifications return empty success
        assert response.is_success() is True

        await server.stop()

    async def test_connect_disconnect_client(self):
        """Test client connection and disconnection."""
        server = MCPServer()

        conn = await server.connect_client("client-1", {"version": "1.0"})
        assert conn.id == "client-1"
        assert server.connection_manager.connection_count == 1

        result = await server.disconnect_client("client-1")
        assert result is True
        assert server.connection_manager.connection_count == 0

    async def test_get_metrics(self, mock_mcp_handler):
        """Test metrics collection."""
        server = MCPServer(enable_metrics=True)
        server.register_handler(mock_mcp_handler)
        await server.start()

        # Make a request
        request = MCPMessage.request(method="test_method", id="1")
        await server.handle_message(request)

        metrics = server.get_metrics()
        assert "requests_total" in metrics
        assert metrics["requests_total"] == 1

        await server.stop()

    async def test_health_check(self):
        """Test health check."""
        server = MCPServer()
        await server.start()

        health = await server.health_check()
        assert health["status"] == "healthy"
        assert health["server"] == server.name
        assert health["running"] is True

        await server.stop()


# ============================================================================
# Built-in Handler Tests
# ============================================================================

@pytest.mark.asyncio
class TestBuiltinHandlers:
    """Test built-in MCP handlers."""

    async def test_get_capabilities_handler(self):
        """Test GetCapabilitiesHandler."""
        server = MCPServer(name="test", version="1.0.0")
        handler = GetCapabilitiesHandler(server)

        request = MCPRequest(method="get_capabilities", id="1")
        response = await handler.handle(request)

        assert response.is_success is True
        result = response.get_result()
        assert result["server"] == "test"
        assert result["version"] == "1.0.0"

    async def test_health_check_handler(self):
        """Test HealthCheckHandler."""
        server = MCPServer()
        await server.start()

        handler = HealthCheckHandler(server)
        request = MCPRequest(method="health_check", id="1")
        response = await handler.handle(request)

        assert response.is_success is True
        result = response.get_result()
        assert result["status"] == "healthy"

        await server.stop()

    async def test_get_metrics_handler(self, mock_mcp_handler):
        """Test GetMetricsHandler."""
        server = MCPServer()
        server.register_handler(mock_mcp_handler)
        await server.start()

        handler = GetMetricsHandler(server)
        request = MCPRequest(method="get_metrics", id="1")
        response = await handler.handle(request)

        assert response.is_success is True
        result = response.get_result()
        assert "requests_total" in result

        await server.stop()


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
class TestMCPIntegration:
    """Integration tests for MCP."""

    async def test_full_request_response_cycle(self, mock_mcp_handler):
        """Test full request-response cycle."""
        server = MCPServer()
        server.register_handler(mock_mcp_handler)
        await server.start()

        # Create and send request
        request = MCPMessage.request(
            method="test_method",
            params={"document_id": "doc-123"},
            id="req-001",
        )

        response_msg = await server.handle_message(request)

        # Verify response
        assert response_msg.is_success() is True
        result = response_msg.result
        assert result["handled"] is True

        await server.stop()

    async def test_batch_request_handling(self):
        """Test batch request handling."""
        server = MCPServer()
        await server.start()

        # Create batch
        batch = [
            MCPMessage.request(method="health_check", id="1").to_dict(),
            MCPMessage.request(method="get_capabilities", id="2").to_dict(),
        ]

        # Note: Server expects MCPMessage, not list directly
        # This tests the batch handling in handle_message
        responses = await server.handle_message(batch)

        # Should return list of responses
        assert isinstance(responses, list)
        assert len(responses) == 2

        await server.stop()

    async def test_error_handling(self):
        """Test error handling in server."""
        server = MCPServer()
        await server.start()

        # Request with invalid params
        request = MCPMessage.request(
            method="nonexistent_method",
            id="req-001",
        )

        response = await server.handle_message(request)

        assert response.is_error() is True
        assert response.error["code"] == MCPErrorCode.METHOD_NOT_FOUND.value

        await server.stop()


# ============================================================================
# MCPCapability Tests
# ============================================================================

class TestMCPCapability:
    """Test MCPCapability class."""

    def test_capability_creation(self):
        """Test capability creation."""
        cap = MCPCapability(
            name="test_capability",
            version="1.0.0",
            description="Test capability",
            options={"key": "value"},
        )
        assert cap.name == "test_capability"
        assert cap.version == "1.0.0"
        assert cap.description == "Test capability"
        assert cap.options == {"key": "value"}

    def test_capability_defaults(self):
        """Test capability default values."""
        cap = MCPCapability(name="test")
        assert cap.version == "1.0.0"
        assert cap.description == ""
        assert cap.options == {}

    def test_to_dict(self):
        """Test capability serialization."""
        cap = MCPCapability(name="test", version="1.0.0")
        data = cap.to_dict()
        assert data["name"] == "test"
        assert data["version"] == "1.0.0"

    def test_from_dict(self):
        """Test capability deserialization."""
        data = {
            "name": "test_cap",
            "version": "2.0.0",
            "description": "Test",
            "options": {"opt": 1},
        }
        cap = MCPCapability.from_dict(data)
        assert cap.name == "test_cap"
        assert cap.version == "2.0.0"
        assert cap.options == {"opt": 1}


# ============================================================================
# MCPMethod Tests
# ============================================================================

class TestMCPMethod:
    """Test MCPMethod enum."""

    def test_document_methods(self):
        """Test document-related methods."""
        assert MCPMethod.PROCESS_DOCUMENT.value == "process_document"
        assert MCPMethod.EXTRACT_CONTENT.value == "extract_content"
        assert MCPMethod.CONVERT_FORMAT.value == "convert_format"
        assert MCPMethod.VALIDATE_DOCUMENT.value == "validate_document"
        assert MCPMethod.GET_DOCUMENT_INFO.value == "get_document_info"

    def test_skill_methods(self):
        """Test skill-related methods."""
        assert MCPMethod.LIST_SKILLS.value == "list_skills"
        assert MCPMethod.EXECUTE_SKILL.value == "execute_skill"
        assert MCPMethod.GET_SKILL_INFO.value == "get_skill_info"

    def test_context_methods(self):
        """Test context-related methods."""
        assert MCPMethod.GET_CONTEXT.value == "get_context"
        assert MCPMethod.SET_CONTEXT.value == "set_context"
        assert MCPMethod.CLEAR_CONTEXT.value == "clear_context"

    def test_server_methods(self):
        """Test server-related methods."""
        assert MCPMethod.GET_CAPABILITIES.value == "get_capabilities"
        assert MCPMethod.HEALTH_CHECK.value == "health_check"
        assert MCPMethod.GET_METRICS.value == "get_metrics"
