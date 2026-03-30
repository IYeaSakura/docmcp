"""
MCP Client Example

This example demonstrates how to create an MCP client and interact with a server.

Usage:
    # First, start the basic server in one terminal:
    python basic_server.py

    # Then, run this client example in another terminal:
    python client_example.py

Note: This example uses stdio transport, so you need to run both in separate
processes or modify the transport mechanism.
"""

import asyncio
import json
import sys

sys.path.insert(0, '/mnt/okcomputer/output/docmcp')

from mcp import MCPClient, ResourceContent, PromptMessage


async def interactive_client():
    """
    Interactive MCP client example.

    This demonstrates how to:
    1. Connect to an MCP server
    2. List and read resources
    3. List and call tools
    4. List and get prompts
    5. Disconnect cleanly
    """

    print("=" * 60)
    print("MCP Client Example")
    print("=" * 60)

    # Create client
    client = MCPClient(
        name="example-client",
        version="1.0.0"
    )

    try:
        # Connect to server via stdio
        print("\n1. Connecting to server...")
        await client.connect_stdio(["python", "basic_server.py"])
        print(f"   Connected! Server: {client.server_info}")
        print(f"   Capabilities: {client.server_capabilities}")

        # List resources
        print("\n2. Listing resources...")
        resources = await client.list_resources()
        for resource in resources:
            print(f"   - {resource.uri}: {resource.name}")
            if resource.description:
                print(f"     Description: {resource.description}")

        # Read a resource
        if resources:
            print(f"\n3. Reading resource '{resources[0].uri}'...")
            contents = await client.read_resource(resources[0].uri)
            for content in contents:
                if content.text:
                    preview = content.text[:200].replace('\n', ' ')
                    if len(content.text) > 200:
                        preview += "..."
                    print(f"   Content: {preview}")

        # List tools
        print("\n4. Listing tools...")
        tools = await client.list_tools()
        for tool in tools:
            print(f"   - {tool.name}: {tool.description}")

        # Call a tool
        echo_tool = next((t for t in tools if t.name == "echo"), None)
        if echo_tool:
            print(f"\n5. Calling tool 'echo'...")
            result = await client.call_tool("echo", {"message": "Hello from client!"})
            for item in result.content:
                print(f"   Result: {item.get('text', item)}")

        # Call greet tool
        greet_tool = next((t for t in tools if t.name == "greet"), None)
        if greet_tool:
            print(f"\n6. Calling tool 'greet'...")
            result = await client.call_tool("greet", {
                "name": "MCP User",
                "language": "en"
            })
            for item in result.content:
                print(f"   Result: {item.get('text', item)}")

        # Call calculate tool
        calc_tool = next((t for t in tools if t.name == "calculate"), None)
        if calc_tool:
            print(f"\n7. Calling tool 'calculate'...")
            result = await client.call_tool("calculate", {
                "operation": "multiply",
                "a": 21,
                "b": 2
            })
            for item in result.content:
                print(f"   Result: {item.get('text', item)}")

        # List prompts
        print("\n8. Listing prompts...")
        prompts = await client.list_prompts()
        for prompt in prompts:
            print(f"   - {prompt.name}: {prompt.description}")

        # Get a prompt
        intro_prompt = next((p for p in prompts if p.name == "introduction"), None)
        if intro_prompt:
            print(f"\n9. Getting prompt 'introduction'...")
            result = await client.get_prompt("introduction", {"name": "Developer"})
            for msg in result.messages:
                print(f"   [{msg.role}]: {msg.content.get('text', '')[:100]}...")

        # Disconnect
        print("\n10. Disconnecting...")
        await client.disconnect()
        print("   Disconnected!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Client example completed!")
    print("=" * 60)


async def document_client_example():
    """
    Example client for the Document MCP Server.

    This demonstrates document-specific operations.
    """

    print("\n" + "=" * 60)
    print("Document MCP Client Example")
    print("=" * 60)

    client = MCPClient("doc-client", "1.0.0")

    try:
        # Connect to document server
        print("\n1. Connecting to document server...")
        await client.connect_stdio(["python", "-m", "mcp.doc_server"])
        print(f"   Connected! Server: {client.server_info}")

        # List resources
        print("\n2. Listing document resources...")
        resources = await client.list_resources()
        for resource in resources:
            print(f"   - {resource.uri}: {resource.name}")

        # List tools
        print("\n3. Listing document tools...")
        tools = await client.list_tools()
        for tool in tools:
            print(f"   - {tool.name}: {tool.description}")

        # Create a document
        print("\n4. Creating a new document...")
        result = await client.call_tool("doc_create", {
            "doc_id": "my-doc",
            "name": "My Document",
            "content": "This is my custom document content.",
            "mime_type": "text/plain"
        })
        for item in result.content:
            print(f"   Result: {item.get('text', '')}")

        # Parse a document
        print("\n5. Parsing the README document...")
        result = await client.call_tool("doc_parse", {
            "doc_id": "readme",
            "format_hint": "markdown"
        })
        for item in result.content:
            data = json.loads(item.get('text', '{}'))
            print(f"   Content type: {data.get('content_type')}")
            print(f"   Length: {data.get('length')} characters")
            print(f"   Word count: {data.get('word_count')}")

        # Summarize a document
        print("\n6. Summarizing the README document...")
        result = await client.call_tool("doc_summarize", {
            "doc_id": "readme",
            "max_length": 200
        })
        for item in result.content:
            print(f"   Summary: {item.get('text', '')[:150]}...")

        # Search documents
        print("\n7. Searching for 'document'...")
        result = await client.call_tool("doc_search", {
            "query": "document"
        })
        for item in result.content:
            print(f"   {item.get('text', '')}")

        # Disconnect
        print("\n8. Disconnecting...")
        await client.disconnect()
        print("   Disconnected!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main entry point."""
    print("MCP Client Examples")
    print("===================\n")
    print("Select an example:")
    print("1. Basic Client Example (requires basic_server.py)")
    print("2. Document Client Example (requires doc_server.py)")
    print("3. Run both examples")
    print("q. Quit")

    choice = input("\nEnter your choice (1/2/3/q): ").strip().lower()

    if choice == "1":
        await interactive_client()
    elif choice == "2":
        await document_client_example()
    elif choice == "3":
        await interactive_client()
        await document_client_example()
    else:
        print("Goodbye!")


if __name__ == "__main__":
    # For non-interactive testing, run the basic client
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        asyncio.run(interactive_client())
    else:
        asyncio.run(main())
