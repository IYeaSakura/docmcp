"""
Interactive MCP Demo

This script provides an interactive demonstration of MCP protocol features.
It can be used to test and explore MCP servers.

Usage:
    python interactive_demo.py [server_script.py]

If no server script is provided, it will use basic_server.py by default.
"""

import asyncio
import json
import sys
from typing import Optional

sys.path.insert(0, '/mnt/okcomputer/output/docmcp')

from mcp import MCPClient, ResourceContent


class MCPDemo:
    """Interactive MCP demo client."""
    
    def __init__(self):
        self.client: Optional[MCPClient] = None
        self.server_command: Optional[list] = None
    
    async def connect(self, server_script: str = "basic_server.py"):
        """Connect to an MCP server."""
        print(f"\nConnecting to server: {server_script}")
        
        self.client = MCPClient("demo-client", "1.0.0")
        self.server_command = ["python", server_script]
        
        await self.client.connect_stdio(self.server_command)
        
        print(f"✓ Connected!")
        print(f"  Server: {self.client.server_info}")
        
        if self.client.server_capabilities:
            caps = self.client.server_capabilities
            if caps.resources:
                print(f"  Resources: Supported")
            if caps.tools:
                print(f"  Tools: Supported")
            if caps.prompts:
                print(f"  Prompts: Supported")
    
    async def disconnect(self):
        """Disconnect from the server."""
        if self.client:
            await self.client.disconnect()
            self.client = None
            print("\n✓ Disconnected")
    
    async def show_resources(self):
        """Display available resources."""
        if not self.client:
            print("Not connected!")
            return
        
        print("\n" + "=" * 50)
        print("RESOURCES")
        print("=" * 50)
        
        resources = await self.client.list_resources()
        
        if not resources:
            print("No resources available")
            return
        
        for i, resource in enumerate(resources, 1):
            print(f"\n[{i}] {resource.name}")
            print(f"    URI: {resource.uri}")
            if resource.description:
                print(f"    Description: {resource.description}")
            if resource.mimeType:
                print(f"    MIME Type: {resource.mimeType}")
        
        # Allow reading a resource
        print("\nEnter resource number to read (or press Enter to skip):")
        choice = input("> ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(resources):
                await self.read_resource(resources[idx].uri)
    
    async def read_resource(self, uri: str):
        """Read and display a resource."""
        if not self.client:
            print("Not connected!")
            return
        
        print(f"\nReading resource: {uri}")
        print("-" * 50)
        
        try:
            contents = await self.client.read_resource(uri)
            
            for content in contents:
                if content.text:
                    print(content.text)
                elif content.blob:
                    print(f"[Binary content: {len(content.blob)} bytes]")
        
        except Exception as e:
            print(f"Error reading resource: {e}")
    
    async def show_tools(self):
        """Display available tools."""
        if not self.client:
            print("Not connected!")
            return
        
        print("\n" + "=" * 50)
        print("TOOLS")
        print("=" * 50)
        
        tools = await self.client.list_tools()
        
        if not tools:
            print("No tools available")
            return
        
        for i, tool in enumerate(tools, 1):
            print(f"\n[{i}] {tool.name}")
            print(f"    Description: {tool.description}")
            if tool.inputSchema:
                print(f"    Input Schema:")
                schema_str = json.dumps(tool.inputSchema, indent=6)
                for line in schema_str.split('\n'):
                    print(f"      {line}")
        
        # Allow calling a tool
        print("\nEnter tool number to call (or press Enter to skip):")
        choice = input("> ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(tools):
                await self.call_tool(tools[idx])
    
    async def call_tool(self, tool):
        """Call a tool with user-provided arguments."""
        if not self.client:
            print("Not connected!")
            return
        
        print(f"\nCalling tool: {tool.name}")
        print("-" * 50)
        
        # Build arguments from schema
        arguments = {}
        schema = tool.inputSchema or {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "any")
            is_required = prop_name in required
            
            prompt = f"  {prop_name} ({prop_type})"
            if is_required:
                prompt += " [required]"
            if "enum" in prop_info:
                prompt += f" options: {prop_info['enum']}"
            if "default" in prop_info:
                prompt += f" default: {prop_info['default']}"
            prompt += ": "
            
            value = input(prompt).strip()
            
            if not value and not is_required:
                continue
            
            # Convert value based on type
            if prop_type == "integer":
                value = int(value)
            elif prop_type == "number":
                value = float(value)
            elif prop_type == "boolean":
                value = value.lower() in ("true", "yes", "1", "y")
            
            arguments[prop_name] = value
        
        print("\nCalling with arguments:")
        print(json.dumps(arguments, indent=2))
        
        try:
            result = await self.client.call_tool(tool.name, arguments)
            
            print("\nResult:")
            print("-" * 50)
            
            if result.isError:
                print("Error!")
            
            for item in result.content:
                if item.get("type") == "text":
                    print(item.get("text", ""))
                elif item.get("type") == "image":
                    print(f"[Image: {item.get('mimeType', 'unknown')}]")
                elif item.get("type") == "resource":
                    print(f"[Embedded resource]")
                else:
                    print(json.dumps(item, indent=2))
        
        except Exception as e:
            print(f"Error calling tool: {e}")
    
    async def show_prompts(self):
        """Display available prompts."""
        if not self.client:
            print("Not connected!")
            return
        
        print("\n" + "=" * 50)
        print("PROMPTS")
        print("=" * 50)
        
        prompts = await self.client.list_prompts()
        
        if not prompts:
            print("No prompts available")
            return
        
        for i, prompt in enumerate(prompts, 1):
            print(f"\n[{i}] {prompt.name}")
            if prompt.description:
                print(f"    Description: {prompt.description}")
            if prompt.arguments:
                print(f"    Arguments:")
                for arg in prompt.arguments:
                    req = "required" if arg.get("required") else "optional"
                    print(f"      - {arg.get('name')} ({req})")
        
        # Allow getting a prompt
        print("\nEnter prompt number to get (or press Enter to skip):")
        choice = input("> ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(prompts):
                await self.get_prompt(prompts[idx])
    
    async def get_prompt(self, prompt):
        """Get a prompt with user-provided arguments."""
        if not self.client:
            print("Not connected!")
            return
        
        print(f"\nGetting prompt: {prompt.name}")
        print("-" * 50)
        
        # Build arguments
        arguments = {}
        
        if prompt.arguments:
            for arg in prompt.arguments:
                arg_name = arg.get("name")
                is_required = arg.get("required", False)
                
                prompt_text = f"  {arg_name}"
                if is_required:
                    prompt_text += " [required]"
                prompt_text += ": "
                
                value = input(prompt_text).strip()
                
                if value or is_required:
                    arguments[arg_name] = value
        
        try:
            result = await self.client.get_prompt(prompt.name, arguments)
            
            print("\nMessages:")
            print("-" * 50)
            
            for msg in result.messages:
                role = msg.role.upper()
                content = msg.content
                
                if content.get("type") == "text":
                    print(f"[{role}]: {content.get('text', '')}")
                elif content.get("type") == "image":
                    print(f"[{role}]: [Image]")
                else:
                    print(f"[{role}]: {json.dumps(content, indent=2)}")
        
        except Exception as e:
            print(f"Error getting prompt: {e}")
    
    async def run(self, server_script: str = "basic_server.py"):
        """Run the interactive demo."""
        try:
            await self.connect(server_script)
            
            while True:
                print("\n" + "=" * 50)
                print("MCP INTERACTIVE DEMO")
                print("=" * 50)
                print("1. List Resources")
                print("2. List Tools")
                print("3. List Prompts")
                print("4. Reconnect")
                print("q. Quit")
                
                choice = input("\nSelect an option: ").strip().lower()
                
                if choice == "1":
                    await self.show_resources()
                elif choice == "2":
                    await self.show_tools()
                elif choice == "3":
                    await self.show_prompts()
                elif choice == "4":
                    await self.disconnect()
                    await self.connect(server_script)
                elif choice == "q":
                    break
                else:
                    print("Invalid option")
        
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.disconnect()


async def main():
    """Main entry point."""
    server_script = sys.argv[1] if len(sys.argv) > 1 else "basic_server.py"
    
    print("MCP Interactive Demo")
    print("====================")
    print(f"Server script: {server_script}")
    
    demo = MCPDemo()
    await demo.run(server_script)
    
    print("\nGoodbye!")


if __name__ == "__main__":
    asyncio.run(main())
