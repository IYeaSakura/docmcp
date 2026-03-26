"""
Document Processing MCP Server

This module provides an MCP server that exposes document processing capabilities
as MCP resources and tools.

Features:
- Document resources: Read document content via MCP resources
- Document tools: Process documents via MCP tools
- Document prompts: Document-related prompt templates

Resources:
- doc://{doc_id}: Access document content by ID
- doc://list: List all available documents

Tools:
- doc_parse: Parse a document and extract structured data
- doc_convert: Convert document format
- doc_summarize: Generate document summary
- doc_search: Search within documents

Prompts:
- doc_analyze: Analyze document content
- doc_compare: Compare two documents

Usage:
    # Run the server
    python -m docmcp.mcp.doc_server
    
    # Or programmatically:
    from docmcp.mcp.doc_server import DocumentMCPServer
    
    server = DocumentMCPServer()
    await server.run_stdio()
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import base64

from .protocol import (
    Resource, ResourceContent,
    Tool, ToolParameter,
    Prompt, PromptArgument, PromptMessage,
    TextContent, ImageContent,
    ServerCapabilities
)
from .server import MCPServer


# =============================================================================
# Document Types
# =============================================================================

@dataclass
class Document:
    """Represents a document."""
    id: str
    name: str
    content: str
    mime_type: str = "text/plain"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_resource(self) -> Resource:
        """Convert to MCP Resource."""
        return Resource(
            uri=f"doc://{self.id}",
            name=self.name,
            description=self.metadata.get("description"),
            mimeType=self.mime_type
        )


# =============================================================================
# Document Store
# =============================================================================

class DocumentStore:
    """In-memory document store."""
    
    def __init__(self):
        self._documents: Dict[str, Document] = {}
    
    def add(self, document: Document) -> None:
        """Add a document to the store."""
        self._documents[document.id] = document
    
    def get(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID."""
        return self._documents.get(doc_id)
    
    def remove(self, doc_id: str) -> bool:
        """Remove a document. Returns True if found."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False
    
    def list_all(self) -> List[Document]:
        """List all documents."""
        return list(self._documents.values())
    
    def search(self, query: str) -> List[Document]:
        """Search documents by content."""
        results = []
        query_lower = query.lower()
        for doc in self._documents.values():
            if query_lower in doc.content.lower():
                results.append(doc)
        return results
    
    def clear(self) -> None:
        """Clear all documents."""
        self._documents.clear()


# =============================================================================
# Document Processors
# =============================================================================

class DocumentProcessor:
    """Document processing utilities."""
    
    @staticmethod
    def parse_document(content: str, format_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse document content and extract structured information.
        
        Args:
            content: Document content
            format_hint: Optional format hint (json, yaml, markdown, etc.)
        
        Returns:
            Parsed document structure
        """
        result = {
            "content_type": "text",
            "length": len(content),
            "line_count": content.count('\n') + 1,
            "word_count": len(content.split()),
            "structured_data": None
        }
        
        # Try to detect and parse format
        content_stripped = content.strip()
        
        # Try JSON
        if format_hint == "json" or content_stripped.startswith(("{", "[")):
            try:
                result["structured_data"] = json.loads(content)
                result["content_type"] = "json"
                return result
            except json.JSONDecodeError:
                pass
        
        # Try Markdown detection
        if format_hint == "markdown" or "#" in content[:1000]:
            result["content_type"] = "markdown"
            result["headers"] = DocumentProcessor._extract_markdown_headers(content)
        
        return result
    
    @staticmethod
    def _extract_markdown_headers(content: str) -> List[Dict[str, Any]]:
        """Extract headers from markdown content."""
        headers = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                headers.append({"level": level, "title": title})
        return headers
    
    @staticmethod
    def summarize(content: str, max_length: int = 500) -> str:
        """
        Generate a simple summary of document content.
        
        Args:
            content: Document content
            max_length: Maximum summary length
        
        Returns:
            Summary text
        """
        lines = content.split('\n')
        
        # Get first non-empty paragraph
        first_para = ""
        for line in lines:
            stripped = line.strip()
            if stripped:
                first_para = stripped
                break
        
        # Get key sentences (simple heuristic: first sentence of each paragraph)
        key_sentences = []
        for line in lines:
            stripped = line.strip()
            if stripped and len(stripped) > 20:
                # Get first sentence
                sentence_end = stripped.find('.')
                if sentence_end > 0:
                    key_sentences.append(stripped[:sentence_end + 1])
        
        # Build summary
        summary_parts = []
        if first_para:
            summary_parts.append(first_para[:200])
        
        if key_sentences:
            summary_parts.extend(key_sentences[:3])
        
        summary = ' '.join(summary_parts)
        
        if len(summary) > max_length:
            summary = summary[:max_length].rsplit(' ', 1)[0] + '...'
        
        return summary
    
    @staticmethod
    def convert_format(content: str, from_format: str, to_format: str) -> str:
        """
        Convert document between formats.
        
        Args:
            content: Document content
            from_format: Source format
            to_format: Target format
        
        Returns:
            Converted content
        """
        # Simple format conversions
        if from_format == to_format:
            return content
        
        if from_format == "json" and to_format == "yaml":
            try:
                import yaml
                data = json.loads(content)
                return yaml.dump(data, default_flow_style=False)
            except ImportError:
                return "# Error: PyYAML not installed\n" + content
            except json.JSONDecodeError as e:
                return f"# Error parsing JSON: {e}\n" + content
        
        if from_format == "yaml" and to_format == "json":
            try:
                import yaml
                data = yaml.safe_load(content)
                return json.dumps(data, indent=2, ensure_ascii=False)
            except ImportError:
                return "# Error: PyYAML not installed\n" + content
            except yaml.YAMLError as e:
                return f"# Error parsing YAML: {e}\n" + content
        
        # Default: wrap in code block
        return f"```{to_format}\n{content}\n```"


# =============================================================================
# Document MCP Server
# =============================================================================

class DocumentMCPServer(MCPServer):
    """
    MCP Server for document processing.
    
    Provides:
    - Resources: Access document content
    - Tools: Process, convert, summarize, search documents
    - Prompts: Document analysis templates
    
    Example:
        server = DocumentMCPServer()
        
        # Add some documents
        server.add_document(Document(
            id="readme",
            name="README",
            content="# My Project\\n\\nThis is the readme.",
            mime_type="text/markdown"
        ))
        
        # Run the server
        await server.run_stdio()
    """
    
    def __init__(
        self,
        name: str = "docmcp-server",
        version: str = "1.0.0"
    ):
        """
        Initialize the document MCP server.
        
        Args:
            name: Server name
            version: Server version
        """
        # Initialize with capabilities
        capabilities = ServerCapabilities(
            resources={"subscribe": False},
            tools={},
            prompts={}
        )
        
        super().__init__(name, version, capabilities)
        
        # Document store
        self._store = DocumentStore()
        
        # Register built-in resources, tools, and prompts
        self._register_resources()
        self._register_tools()
        self._register_prompts()
    
    def _register_resources(self) -> None:
        """Register document resources."""
        
        # doc://list - List all documents
        self._resources.register(
            uri="doc://list",
            name="Document List",
            description="List of all available documents",
            mime_type="application/json",
            handler=self._handle_doc_list
        )
    
    def _register_tools(self) -> None:
        """Register document processing tools."""
        
        # doc_parse - Parse document
        self._tools.register(
            name="doc_parse",
            description="Parse a document and extract structured information",
            input_schema={
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Document ID to parse"
                    },
                    "format_hint": {
                        "type": "string",
                        "description": "Optional format hint (json, yaml, markdown)"
                    }
                },
                "required": ["doc_id"]
            },
            handler=self._handle_doc_parse
        )
        
        # doc_summarize - Summarize document
        self._tools.register(
            name="doc_summarize",
            description="Generate a summary of a document",
            input_schema={
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Document ID to summarize"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Maximum summary length",
                        "default": 500
                    }
                },
                "required": ["doc_id"]
            },
            handler=self._handle_doc_summarize
        )
        
        # doc_convert - Convert document format
        self._tools.register(
            name="doc_convert",
            description="Convert a document to a different format",
            input_schema={
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Document ID to convert"
                    },
                    "to_format": {
                        "type": "string",
                        "description": "Target format (json, yaml, markdown, text)",
                        "enum": ["json", "yaml", "markdown", "text"]
                    }
                },
                "required": ["doc_id", "to_format"]
            },
            handler=self._handle_doc_convert
        )
        
        # doc_search - Search documents
        self._tools.register(
            name="doc_search",
            description="Search for documents containing specific text",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            },
            handler=self._handle_doc_search
        )
        
        # doc_create - Create a new document
        self._tools.register(
            name="doc_create",
            description="Create a new document",
            input_schema={
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Unique document ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Document name"
                    },
                    "content": {
                        "type": "string",
                        "description": "Document content"
                    },
                    "mime_type": {
                        "type": "string",
                        "description": "MIME type",
                        "default": "text/plain"
                    }
                },
                "required": ["doc_id", "name", "content"]
            },
            handler=self._handle_doc_create
        )
    
    def _register_prompts(self) -> None:
        """Register document prompts."""
        
        # doc_analyze - Document analysis prompt
        self._prompts.register(
            name="doc_analyze",
            description="Analyze a document and provide insights",
            arguments=[
                PromptArgument(
                    name="doc_id",
                    description="Document ID to analyze",
                    required=True
                )
            ],
            handler=self._handle_doc_analyze
        )
        
        # doc_compare - Compare two documents
        self._prompts.register(
            name="doc_compare",
            description="Compare two documents and identify differences",
            arguments=[
                PromptArgument(
                    name="doc_id_1",
                    description="First document ID",
                    required=True
                ),
                PromptArgument(
                    name="doc_id_2",
                    description="Second document ID",
                    required=True
                )
            ],
            handler=self._handle_doc_compare
        )
    
    # ==========================================================================
    # Resource Handlers
    # ==========================================================================
    
    async def _handle_doc_list(self) -> ResourceContent:
        """Handle doc://list resource request."""
        documents = self._store.list_all()
        
        data = {
            "count": len(documents),
            "documents": [
                {
                    "id": d.id,
                    "name": d.name,
                    "mime_type": d.mime_type,
                    "metadata": d.metadata
                }
                for d in documents
            ]
        }
        
        return ResourceContent(
            uri="doc://list",
            mimeType="application/json",
            text=json.dumps(data, indent=2, ensure_ascii=False)
        )
    
    # ==========================================================================
    # Tool Handlers
    # ==========================================================================
    
    async def _handle_doc_parse(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle doc_parse tool."""
        doc_id = arguments.get("doc_id")
        format_hint = arguments.get("format_hint")
        
        doc = self._store.get(doc_id)
        if doc is None:
            return [{
                "type": "text",
                "text": f"Error: Document '{doc_id}' not found"
            }]
        
        result = DocumentProcessor.parse_document(doc.content, format_hint)
        
        return [{
            "type": "text",
            "text": json.dumps(result, indent=2, ensure_ascii=False)
        }]
    
    async def _handle_doc_summarize(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle doc_summarize tool."""
        doc_id = arguments.get("doc_id")
        max_length = arguments.get("max_length", 500)
        
        doc = self._store.get(doc_id)
        if doc is None:
            return [{
                "type": "text",
                "text": f"Error: Document '{doc_id}' not found"
            }]
        
        summary = DocumentProcessor.summarize(doc.content, max_length)
        
        return [{
            "type": "text",
            "text": f"# Summary of {doc.name}\n\n{summary}"
        }]
    
    async def _handle_doc_convert(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle doc_convert tool."""
        doc_id = arguments.get("doc_id")
        to_format = arguments.get("to_format")
        
        doc = self._store.get(doc_id)
        if doc is None:
            return [{
                "type": "text",
                "text": f"Error: Document '{doc_id}' not found"
            }]
        
        # Detect source format from mime_type
        from_format = "text"
        if doc.mime_type == "application/json":
            from_format = "json"
        elif doc.mime_type in ("text/yaml", "application/x-yaml"):
            from_format = "yaml"
        elif doc.mime_type == "text/markdown":
            from_format = "markdown"
        
        converted = DocumentProcessor.convert_format(
            doc.content, from_format, to_format
        )
        
        return [{
            "type": "text",
            "text": converted
        }]
    
    async def _handle_doc_search(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle doc_search tool."""
        query = arguments.get("query", "")
        
        results = self._store.search(query)
        
        if not results:
            return [{
                "type": "text",
                "text": f"No documents found matching '{query}'"
            }]
        
        text = f"# Search Results for '{query}'\n\n"
        text += f"Found {len(results)} document(s):\n\n"
        
        for doc in results:
            text += f"- **{doc.name}** (`{doc.id}`)\n"
        
        return [{
            "type": "text",
            "text": text
        }]
    
    async def _handle_doc_create(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle doc_create tool."""
        doc_id = arguments.get("doc_id")
        name = arguments.get("name")
        content = arguments.get("content")
        mime_type = arguments.get("mime_type", "text/plain")
        
        if self._store.get(doc_id) is not None:
            return [{
                "type": "text",
                "text": f"Error: Document '{doc_id}' already exists"
            }]
        
        doc = Document(
            id=doc_id,
            name=name,
            content=content,
            mime_type=mime_type
        )
        
        self._store.add(doc)
        
        # Register as dynamic resource
        self._register_document_resource(doc)
        
        return [{
            "type": "text",
            "text": f"Document '{name}' created successfully with ID '{doc_id}'"
        }]
    
    # ==========================================================================
    # Prompt Handlers
    # ==========================================================================
    
    async def _handle_doc_analyze(
        self,
        arguments: Optional[Dict[str, str]]
    ) -> List[PromptMessage]:
        """Handle doc_analyze prompt."""
        args = arguments or {}
        doc_id = args.get("doc_id")
        
        doc = self._store.get(doc_id)
        if doc is None:
            return [PromptMessage(
                role="user",
                content={
                    "type": "text",
                    "text": f"Please analyze document '{doc_id}'. Note: This document was not found in the store."
                }
            )]
        
        content = f"""Please analyze the following document and provide insights:

Document: {doc.name} (ID: {doc.id})
Type: {doc.mime_type}

---

{doc.content[:2000]}

---

Please provide:
1. A brief summary of the content
2. Key points or main themes
3. Any notable observations
"""
        
        return [PromptMessage(
            role="user",
            content={"type": "text", "text": content}
        )]
    
    async def _handle_doc_compare(
        self,
        arguments: Optional[Dict[str, str]]
    ) -> List[PromptMessage]:
        """Handle doc_compare prompt."""
        args = arguments or {}
        doc_id_1 = args.get("doc_id_1")
        doc_id_2 = args.get("doc_id_2")
        
        doc1 = self._store.get(doc_id_1)
        doc2 = self._store.get(doc_id_2)
        
        if doc1 is None or doc2 is None:
            return [PromptMessage(
                role="user",
                content={
                    "type": "text",
                    "text": f"Please compare documents. Note: One or both documents were not found."
                }
            )]
        
        content = f"""Please compare the following two documents and identify key differences:

# Document 1: {doc1.name} (ID: {doc1.id})

---

{doc1.content[:1500]}

---

# Document 2: {doc2.name} (ID: {doc2.id})

---

{doc2.content[:1500]}

---

Please provide:
1. Similarities between the documents
2. Key differences
3. Which document is more comprehensive (if applicable)
"""
        
        return [PromptMessage(
            role="user",
            content={"type": "text", "text": content}
        )]
    
    # ==========================================================================
    # Public API
    # ==========================================================================
    
    def add_document(self, document: Document) -> None:
        """
        Add a document to the server.
        
        Args:
            document: Document to add
        """
        self._store.add(document)
        self._register_document_resource(document)
    
    def _register_document_resource(self, document: Document) -> None:
        """Register a document as a dynamic resource."""
        uri = f"doc://{document.id}"
        
        # Create handler for this document
        async def handler() -> ResourceContent:
            return ResourceContent(
                uri=uri,
                mimeType=document.mime_type,
                text=document.content
            )
        
        # Register or update resource
        self._resources.register(
            uri=uri,
            name=document.name,
            description=document.metadata.get("description"),
            mime_type=document.mime_type,
            handler=handler
        )
    
    def remove_document(self, doc_id: str) -> bool:
        """
        Remove a document from the server.
        
        Args:
            doc_id: Document ID
        
        Returns:
            True if document was found and removed
        """
        self._resources.unregister(f"doc://{doc_id}")
        return self._store.remove(doc_id)
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """
        Get a document by ID.
        
        Args:
            doc_id: Document ID
        
        Returns:
            Document or None
        """
        return self._store.get(doc_id)
    
    def list_documents(self) -> List[Document]:
        """
        List all documents.
        
        Returns:
            List of documents
        """
        return self._store.list_all()


# =============================================================================
# Main Entry Point
# =============================================================================

async def main():
    """Main entry point for the document MCP server."""
    server = DocumentMCPServer()
    
    # Add some sample documents
    server.add_document(Document(
        id="readme",
        name="README",
        content="""# Document MCP Server

This is a Model Context Protocol server for document processing.

## Features

- Document resources
- Document processing tools
- Document analysis prompts

## Usage

Connect to this server using any MCP client.
""",
        mime_type="text/markdown",
        metadata={"description": "Project README"}
    ))
    
    server.add_document(Document(
        id="config",
        name="Configuration",
        content=json.dumps({
            "server": {
                "name": "docmcp-server",
                "version": "1.0.0"
            },
            "features": ["resources", "tools", "prompts"],
            "settings": {
                "max_document_size": 1048576,
                "supported_formats": ["text", "markdown", "json", "yaml"]
            }
        }, indent=2),
        mime_type="application/json",
        metadata={"description": "Server configuration"}
    ))
    
    # Run the server
    await server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
