"""
MCP Protocol Test Suite

This module provides tests for the MCP protocol implementation.
It can be run standalone to verify the implementation.

Usage:
    python test_mcp.py

Tests include:
- Protocol message parsing and serialization
- Server lifecycle management
- Resource operations
- Tool operations
- Prompt operations
"""

import asyncio
import json
import sys
from typing import Dict, Any, List

sys.path.insert(0, '/mnt/okcomputer/output/docmcp')

from mcp import (
    # Protocol
    JSONRPCRequest, JSONRPCResponse, JSONRPCError,
    JSONRPCErrorCode, MCPErrorCode,
    parse_message, serialize_message,
    create_request, create_response, create_error_response,

    # Types
    Resource, ResourceContent,
    Tool, Prompt, PromptMessage,
    ServerCapabilities, ClientCapabilities,
    InitializeRequest, InitializeResult,

    # Server
    MCPServer, ServerState,
    StdioTransport,

    # Client
    MCPClient, ClientState,

    # Exceptions
    MCPError, ProtocolError, ResourceNotFoundError, ToolNotFoundError
)


# =============================================================================
# Protocol Tests
# =============================================================================

def test_jsonrpc_request():
    """Test JSON-RPC request creation and parsing."""
    print("Testing JSON-RPC Request...")

    # Create request
    request = JSONRPCRequest(
        method="test/method",
        params={"key": "value"},
        id=1
    )

    # Serialize
    serialized = serialize_message(request)
    data = json.loads(serialized)

    assert data["jsonrpc"] == "2.0"
    assert data["method"] == "test/method"
    assert data["params"]["key"] == "value"
    assert data["id"] == 1

    # Parse back
    parsed = parse_message(serialized)
    assert isinstance(parsed, JSONRPCRequest)
    assert parsed.method == "test/method"

    print("  ✓ JSON-RPC Request test passed")


def test_jsonrpc_response():
    """Test JSON-RPC response creation and parsing."""
    print("Testing JSON-RPC Response...")

    # Create success response
    response = create_response(1, {"result": "success"})
    serialized = serialize_message(response)
    data = json.loads(serialized)

    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert data["result"]["result"] == "success"

    # Create error response
    error = JSONRPCError(
        code=JSONRPCErrorCode.METHOD_NOT_FOUND.value,
        message="Method not found"
    )
    error_response = create_error_response(2, error)
    serialized = serialize_message(error_response)
    data = json.loads(serialized)

    assert data["error"]["code"] == -32601
    assert data["error"]["message"] == "Method not found"

    print("  ✓ JSON-RPC Response test passed")


def test_notification():
    """Test notification (request without id)."""
    print("Testing Notification...")

    request = create_request("notifications/test", {"data": "value"}, None)
    assert request.is_notification()

    serialized = serialize_message(request)
    data = json.loads(serialized)
    assert "id" not in data

    print("  ✓ Notification test passed")


# =============================================================================
# Type Tests
# =============================================================================

def test_resource_types():
    """Test resource types."""
    print("Testing Resource Types...")

    resource = Resource(
        uri="test://resource",
        name="Test Resource",
        description="A test resource",
        mimeType="text/plain"
    )

    data = resource.to_dict()
    assert data["uri"] == "test://resource"
    assert data["name"] == "Test Resource"

    restored = Resource.from_dict(data)
    assert restored.uri == resource.uri

    print("  ✓ Resource Types test passed")


def test_tool_types():
    """Test tool types."""
    print("Testing Tool Types...")

    tool = Tool(
        name="test_tool",
        description="A test tool",
        inputSchema={
            "type": "object",
            "properties": {
                "param": {"type": "string"}
            }
        }
    )

    data = tool.to_dict()
    assert data["name"] == "test_tool"
    assert "inputSchema" in data

    restored = Tool.from_dict(data)
    assert restored.name == tool.name

    print("  ✓ Tool Types test passed")


def test_prompt_types():
    """Test prompt types."""
    print("Testing Prompt Types...")

    from mcp import PromptArgument

    prompt = Prompt(
        name="test_prompt",
        description="A test prompt",
        arguments=[
            PromptArgument(name="arg1", description="Argument 1", required=True)
        ]
    )

    data = prompt.to_dict()
    assert data["name"] == "test_prompt"
    assert "arguments" in data

    restored = Prompt.from_dict(data)
    assert restored.name == prompt.name

    print("  ✓ Prompt Types test passed")


# =============================================================================
# Server Tests
# =============================================================================

async def test_server_lifecycle():
    """Test server lifecycle management."""
    print("Testing Server Lifecycle...")

    server = MCPServer("test-server", "1.0.0")

    # Initial state
    assert server.state == ServerState.CREATED
    assert not server.is_initialized

    # Test initialize handler
    init_request = InitializeRequest(
        protocolVersion="2024-11-05",
        capabilities=ClientCapabilities(),
        clientInfo={"name": "test-client", "version": "1.0.0"}
    )

    result = await server._handle_initialize(init_request.to_dict())

    assert "protocolVersion" in result
    assert "capabilities" in result
    assert "serverInfo" in result
    assert result["serverInfo"]["name"] == "test-server"

    # Test initialized notification
    await server._handle_initialized_notification({})
    assert server.is_initialized

    print("  ✓ Server Lifecycle test passed")


async def test_server_resources():
    """Test server resource registration and handling."""
    print("Testing Server Resources...")

    server = MCPServer("test-server", "1.0.0")

    # Register a resource
    @server.resource("test://data", "Test Data", mime_type="application/json")
    async def get_data():
        return ResourceContent(
            uri="test://data",
            mimeType="application/json",
            text='{"test": true}'
        )

    # List resources
    result = await server._handle_resources_list({})
    assert len(result["resources"]) == 1
    assert result["resources"][0]["uri"] == "test://data"

    # Read resource
    result = await server._handle_resources_read({"uri": "test://data"})
    assert len(result["contents"]) == 1
    assert result["contents"][0]["uri"] == "test://data"

    # Read non-existent resource
    try:
        await server._handle_resources_read({"uri": "test://nonexistent"})
        assert False, "Should have raised ResourceNotFoundError"
    except ResourceNotFoundError:
        pass

    print("  ✓ Server Resources test passed")


async def test_server_tools():
    """Test server tool registration and handling."""
    print("Testing Server Tools...")

    server = MCPServer("test-server", "1.0.0")

    # Register a tool
    @server.tool("echo", "Echo tool", input_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string"}
        }
    })
    async def echo_tool(arguments: dict):
        return [{"type": "text", "text": arguments.get("message", "")}]

    # List tools
    result = await server._handle_tools_list({})
    assert len(result["tools"]) == 1
    assert result["tools"][0]["name"] == "echo"

    # Call tool
    result = await server._handle_tools_call({
        "name": "echo",
        "arguments": {"message": "Hello"}
    })
    assert not result["isError"]
    assert len(result["content"]) == 1
    assert result["content"][0]["text"] == "Hello"

    # Call non-existent tool
    try:
        await server._handle_tools_call({"name": "nonexistent", "arguments": {}})
        assert False, "Should have raised ToolNotFoundError"
    except ToolNotFoundError:
        pass

    print("  ✓ Server Tools test passed")


async def test_server_prompts():
    """Test server prompt registration and handling."""
    print("Testing Server Prompts...")

    server = MCPServer("test-server", "1.0.0")

    # Register a prompt
    @server.prompt("greeting", "Greeting prompt")
    async def greeting_prompt(arguments: dict = None):
        args = arguments or {}
        name = args.get("name", "World")
        return [PromptMessage(
            role="user",
            content={"type": "text", "text": f"Hello, {name}!"}
        )]

    # List prompts
    result = await server._handle_prompts_list({})
    assert len(result["prompts"]) == 1
    assert result["prompts"][0]["name"] == "greeting"

    # Get prompt
    result = await server._handle_prompts_get({
        "name": "greeting",
        "arguments": {"name": "Test"}
    })
    assert len(result["messages"]) == 1
    assert "Hello, Test!" in result["messages"][0]["content"]["text"]

    print("  ✓ Server Prompts test passed")


# =============================================================================
# Document Server Tests
# =============================================================================

async def test_document_server():
    """Test document MCP server."""
    print("Testing Document Server...")

    from mcp import DocumentMCPServer, Document

    server = DocumentMCPServer()

    # Add a test document
    server.add_document(Document(
        id="test",
        name="Test Document",
        content="This is a test document.",
        mime_type="text/plain"
    ))

    # List resources (should include doc://test)
    result = await server._handle_resources_list({})
    uris = [r["uri"] for r in result["resources"]]
    assert "doc://list" in uris
    assert "doc://test" in uris

    # Test doc_parse tool
    result = await server._handle_doc_parse({"doc_id": "test"})
    data = json.loads(result[0]["text"])
    assert data["content_type"] == "text"
    assert data["length"] > 0

    # Test doc_summarize tool
    result = await server._handle_doc_summarize({"doc_id": "test"})
    assert "Test Document" in result[0]["text"]

    # Test doc_search tool
    result = await server._handle_doc_search({"query": "test"})
    assert "test" in result[0]["text"].lower()

    print("  ✓ Document Server test passed")


# =============================================================================
# Integration Test
# =============================================================================

async def test_message_handling():
    """Test server message handling."""
    print("Testing Message Handling...")

    server = MCPServer("test-server", "1.0.0")

    @server.resource("test://data", "Test Data")
    async def get_data():
        return ResourceContent(uri="test://data", text="test data")

    # Test initialize message
    init_msg = json.dumps({
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        },
        "id": 1
    })

    response = await server._handle_message(init_msg)
    data = json.loads(response)
    assert "result" in data
    assert data["id"] == 1

    # Test resources/list message
    list_msg = json.dumps({
        "jsonrpc": "2.0",
        "method": "resources/list",
        "params": {},
        "id": 2
    })

    response = await server._handle_message(list_msg)
    data = json.loads(response)
    assert "result" in data
    assert "resources" in data["result"]

    # Test error handling
    error_msg = json.dumps({
        "jsonrpc": "2.0",
        "method": "unknown/method",
        "params": {},
        "id": 3
    })

    response = await server._handle_message(error_msg)
    data = json.loads(response)
    assert "error" in data
    assert data["error"]["code"] == JSONRPCErrorCode.METHOD_NOT_FOUND.value

    print("  ✓ Message Handling test passed")


# =============================================================================
# Run All Tests
# =============================================================================

async def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("MCP Protocol Test Suite")
    print("=" * 60)

    # Protocol tests
    print("\n--- Protocol Tests ---")
    test_jsonrpc_request()
    test_jsonrpc_response()
    test_notification()

    # Type tests
    print("\n--- Type Tests ---")
    test_resource_types()
    test_tool_types()
    test_prompt_types()

    # Server tests
    print("\n--- Server Tests ---")
    await test_server_lifecycle()
    await test_server_resources()
    await test_server_tools()
    await test_server_prompts()

    # Document server tests
    print("\n--- Document Server Tests ---")
    await test_document_server()

    # Integration tests
    print("\n--- Integration Tests ---")
    await test_message_handling()

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
