# DocMCP

Enterprise Document Processing System with MCP (Model Context Protocol) and Skills Support.

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

DocMCP is a production-grade document processing platform designed for seamless integration with AI coding assistants like Claude Code, Kimi Code CLI, and Trae. It eliminates the need for temporary processing scripts when working with binary documents by providing a unified, secure, and robust interface for document content extraction and manipulation.

### Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Format Support** | Native support for DOC, DOCX, PDF, XLS, XLSX, PPT, PPTX, TXT, MD, HTML, and JSON |
| **MCP Protocol** | Full implementation of Model Context Protocol for standardized AI assistant integration |
| **Skills System** | Dynamic, pluggable skill system for custom document processing workflows |
| **Security-First** | Sandboxed execution environment with resource limits, content scanning, and audit logging |
| **High Performance** | Async processing engine with connection pooling, caching, and rate limiting |
| **Content Extraction** | Complete document structure extraction including text, tables, images, and metadata |

### Supported Document Formats

| Format | Extension | Read | Write | Convert | Notes |
|--------|-----------|------|-------|---------|-------|
| Word Document | .doc, .docx | Yes | Yes | Yes | Full formatting support |
| PDF Document | .pdf | Yes | Partial | Yes | Requires LibreOffice for creation |
| Excel Spreadsheet | .xls, .xlsx | Yes | Yes | Yes | Multi-sheet support |
| PowerPoint | .ppt, .pptx | Yes | Yes | Yes | Slide notes and images |
| Plain Text | .txt | Yes | Yes | Yes | Universal format |
| Markdown | .md | Yes | Yes | Yes | Preserves structure |
| HTML | .html, .htm | Yes | Yes | Yes | Web documents |
| JSON | .json | Yes | Yes | Yes | Structured data |

## Quick Start

### Installation

```bash
# Basic installation
pip install docmcp

# Full installation with all features
pip install docmcp[all]

# Development installation
pip install -e ".[dev]"
```

### Basic Usage

```python
from docmcp import ProcessingEngine, DocumentFormat

# Initialize the processing engine
engine = ProcessingEngine()

# Process a document
doc = engine.load_document("path/to/document.docx")

# Extract content
content = await engine.extract_content(doc)
print(content.text)
print(content.tables)
print(content.metadata)
```

### Using Skills

```python
from docmcp.skills import SkillRegistry, SkillContext

# Create skill registry
registry = SkillRegistry()

# Execute a built-in skill
context = SkillContext(document=doc)
result = await registry.execute("extract_text", context)
print(result.data)
```

### MCP Server

```python
from docmcp.mcp import MCPServer

# Start MCP server
server = MCPServer(host="0.0.0.0", port=8080)
await server.start()
```

## Project Structure

```
docmcp/
├── docmcp/                     # Main package
│   ├── core/                   # Core document processing
│   │   ├── document.py         # Document abstraction
│   │   ├── engine.py           # Processing engine
│   │   ├── pipeline.py         # Processing pipeline
│   │   └── handlers/           # Format handlers
│   │       ├── word_handler.py
│   │       ├── pdf_handler.py
│   │       ├── excel_handler.py
│   │       └── ppt_handler.py
│   ├── mcp/                    # MCP protocol implementation
│   │   ├── protocol.py         # Protocol definitions
│   │   ├── server.py           # MCP server
│   │   └── client.py           # MCP client
│   ├── skills/                 # Skills system
│   │   ├── base.py             # Base skill classes
│   │   ├── registry.py         # Skill registry
│   │   ├── scheduler.py        # Task scheduler
│   │   └── builtins/           # Built-in skills
│   ├── security/               # Security module
│   │   ├── sandbox.py          # Sandbox execution
│   │   ├── auth.py             # Authentication
│   │   └── scanner.py          # Content scanning
│   └── performance/            # Performance module
│       ├── cache.py            # Caching
│       ├── pool.py             # Connection pooling
│       └── limiter.py          # Rate limiting
├── tests/                      # Test suite
├── examples/                   # Usage examples
└── skills/                     # Additional skills directory
```

## Architecture

### Core Components

1. **Document Abstraction Layer**
   - Unified interface for all document types
   - Automatic format detection
   - Content extraction and manipulation

2. **Processing Engine**
   - Async/await based architecture
   - Plugin-based handler system
   - Pipeline processing support

3. **Skills System**
   - Dynamic loading and execution
   - Dependency resolution
   - Sandboxed execution environment

4. **MCP Protocol Implementation**
   - JSON-RPC 2.0 based communication
   - Method routing and handlers
   - Connection management

5. **Security Layer**
   - Process isolation
   - Resource limits (memory, CPU, time)
   - Content validation and scanning

## Configuration

DocMCP can be configured via environment variables or configuration files:

```yaml
# config.yaml
app:
  name: DocMCP
  debug: false

sandbox:
  max_memory_mb: 512
  max_execution_time: 30
  network_enabled: false

cache:
  enabled: true
  type: memory
  ttl: 3600
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DOCMCP_DEBUG` | Enable debug mode | `false` |
| `DOCMCP_SANDBOX_MAX_MEMORY` | Max memory for sandbox (MB) | `512` |
| `DOCMCP_SANDBOX_MAX_TIME` | Max execution time (seconds) | `30` |
| `DOCMCP_CACHE_TYPE` | Cache type (memory/redis) | `memory` |
| `DOCMCP_LOG_LEVEL` | Logging level | `info` |

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=docmcp --cov-report=html

# Run specific test categories
pytest tests/ -m "not slow"
pytest tests/ -m integration
pytest tests/ -m security
```

## Development

### Setting up Development Environment

```bash
# Clone repository
git clone https://github.com/your-org/docmcp.git
cd docmcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Code Style

```bash
# Format code
black docmcp/ tests/

# Sort imports
isort docmcp/ tests/

# Type checking
mypy docmcp/

# Linting
flake8 docmcp/
```

## Security Considerations

1. **Sandboxed Execution**: All user-provided code runs in isolated subprocesses with strict resource limits
2. **Content Validation**: File type validation using magic bytes before processing
3. **Audit Logging**: All operations are logged for security review
4. **Network Isolation**: Sandboxed processes have no network access by default

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built for seamless integration with AI coding assistants
- Inspired by the need for robust document processing in AI workflows
- Uses industry-standard libraries for document format support

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/your-org/docmcp/issues).

## Roadmap

- [ ] Enhanced OCR support for scanned documents
- [ ] Additional output formats (EPUB, MOBI)
- [ ] Cloud storage integration (S3, Azure Blob, GCS)
- [ ] Distributed processing support
- [ ] Web-based management interface
