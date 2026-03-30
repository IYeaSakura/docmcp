"""
Basic MCP Server Example

This example demonstrates how to create a simple MCP server with:
- Resources: Expose data as readable resources
- Tools: Provide executable functions
- Prompts: Offer reusable prompt templates

Usage:
    python basic_server.py

The server will run via stdio and accept MCP protocol messages.
"""

import asyncio
import json
from datetime import datetime

import sys
sys.path.insert(0, '/mnt/okcomputer/output/docmcp')

from mcp import MCPServer, ResourceContent, PromptMessage


# Create the server
server = MCPServer("basic-server", "1.0.0")


# ============================================================================
# Resources
# ============================================================================

@server.resource("system://info", "System Information")
async def get_system_info():
    """Provide system information as a resource."""
    info = {
        "server_name": "basic-server",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "features": ["resources", "tools", "prompts"]
    }
    return ResourceContent(
        uri="system://info",
        mimeType="application/json",
        text=json.dumps(info, indent=2)
    )


@server.resource("docs://guide", "User Guide", mime_type="text/markdown")
async def get_user_guide():
    """Provide a user guide as a markdown resource."""
    content = """# User Guide

Welcome to the Basic MCP Server!

## Available Resources

- `system://info` - System information
- `docs://guide` - This user guide

## Available Tools

- `echo` - Echo a message
- `greet` - Generate a greeting
- `calculate` - Perform calculations

## Available Prompts

- `introduction` - Introduction prompt
- `help` - Help prompt
"""
    return ResourceContent(
        uri="docs://guide",
        mimeType="text/markdown",
        text=content
    )


# ============================================================================
# Tools
# ============================================================================

@server.tool(
    "echo",
    "Echo a message back to the caller",
    input_schema={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Message to echo"
            }
        },
        "required": ["message"]
    }
)
async def echo_tool(arguments: dict):
    """Echo tool implementation."""
    message = arguments.get("message", "")
    return [{"type": "text", "text": f"Echo: {message}"}]


@server.tool(
    "greet",
    "Generate a personalized greeting",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name to greet"
            },
            "language": {
                "type": "string",
                "description": "Language for greeting",
                "enum": ["en", "es", "fr", "de", "zh"],
                "default": "en"
            }
        },
        "required": ["name"]
    }
)
async def greet_tool(arguments: dict):
    """Greeting tool implementation."""
    name = arguments.get("name", "World")
    language = arguments.get("language", "en")

    greetings = {
        "en": f"Hello, {name}!",
        "es": f"¡Hola, {name}!",
        "fr": f"Bonjour, {name}!",
        "de": f"Hallo, {name}!",
        "zh": f"你好, {name}!"
    }

    greeting = greetings.get(language, greetings["en"])
    return [{"type": "text", "text": greeting}]


@server.tool(
    "calculate",
    "Perform a calculation",
    input_schema={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "description": "Mathematical operation",
                "enum": ["add", "subtract", "multiply", "divide"]
            },
            "a": {
                "type": "number",
                "description": "First operand"
            },
            "b": {
                "type": "number",
                "description": "Second operand"
            }
        },
        "required": ["operation", "a", "b"]
    }
)
async def calculate_tool(arguments: dict):
    """Calculator tool implementation."""
    operation = arguments.get("operation")
    a = arguments.get("a", 0)
    b = arguments.get("b", 0)

    try:
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return [{"type": "text", "text": "Error: Division by zero"}]
            result = a / b
        else:
            return [{"type": "text", "text": f"Error: Unknown operation '{operation}'"}]

        return [{"type": "text", "text": f"Result: {result}"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {str(e)}"}]


# ============================================================================
# Prompts
# ============================================================================

@server.prompt(
    "introduction",
    "Generate an introduction message",
    arguments=[
        {
            "name": "name",
            "description": "User's name",
            "required": False
        }
    ]
)
async def introduction_prompt(arguments: dict = None):
    """Introduction prompt implementation."""
    args = arguments or {}
    name = args.get("name", "there")

    content = f"""Hello {name}! I'm an AI assistant powered by the Model Context Protocol.

I can help you with various tasks using the resources, tools, and prompts provided by this server.

How can I assist you today?"""

    return [PromptMessage(role="user", content={"type": "text", "text": content})]


@server.prompt(
    "help",
    "Get help information",
    arguments=[]
)
async def help_prompt(arguments: dict = None):
    """Help prompt implementation."""
    content = """I'm here to help! Here are some things you can do:

**Resources:**
- Read system information from `system://info`
- Read the user guide from `docs://guide`

**Tools:**
- Use `echo` to test connectivity
- Use `greet` to generate greetings
- Use `calculate` for math operations

**Prompts:**
- Use `introduction` for a welcome message
- Use `help` (this prompt) for assistance

What would you like to do?"""

    return [PromptMessage(role="user", content={"type": "text", "text": content})]


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Run the basic MCP server."""
    print("Starting Basic MCP Server...", file=sys.stderr)
    print("Server: basic-server v1.0.0", file=sys.stderr)
    print("Resources: system://info, docs://guide", file=sys.stderr)
    print("Tools: echo, greet, calculate", file=sys.stderr)
    print("Prompts: introduction, help", file=sys.stderr)
    print("-" * 40, file=sys.stderr)

    await server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
