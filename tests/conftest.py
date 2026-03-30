"""
Pytest configuration and fixtures for DocMCP tests.

This module provides:
- Test fixtures for all test modules
- Shared test utilities
- Mock objects and test data
"""

import pytest
import asyncio
import tempfile
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from unittest.mock import Mock, MagicMock, AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from docmcp.core.document import (
    BaseDocument,
    DocumentType,
    DocumentMetadata,
    DocumentContent,
    DocumentFormat,
)
from docmcp.core.engine import (
    ProcessingEngine,
    ProcessingContext,
    ProcessingResult,
    ProcessingStatus,
    ValidationResult,
    ValidationStatus,
)
from docmcp.mcp.protocol import (
    MCPMessage,
    MCPResponse,
    MCPRequest,
    MCPError,
    MCPErrorCode,
    MCPMethod,
    MCPCapability,
)
from docmcp.mcp.server import MCPServer, MCPHandler
from docmcp.skills.base import (
    BaseSkill,
    SkillContext,
    SkillResult,
    SkillStatus,
    SkillMetadata,
    SkillChain,
    SkillParallel,
)
from docmcp.skills.registry import SkillRegistry
from docmcp.security.auth import (
    AuthManager,
    User,
    Role,
    Permission,
    Resource,
    PasswordManager,
    TokenManager,
    PermissionChecker,
)
from docmcp.security.sandbox import (
    SandboxExecutor,
    SandboxResult,
    SandboxStatus,
    ResourceLimits,
)
from docmcp.performance.monitor import (
    MetricsCollector,
    HealthChecker,
    AlertManager,
    SystemMonitor,
    MetricType,
    HealthStatus,
    AlertRule,
)


# ============================================================================
# Event Loop Fixture
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Document Fixtures
# ============================================================================

@pytest.fixture
def sample_text_content() -> str:
    """Sample text content for testing."""
    return """
    This is a sample document for testing purposes.

    It contains multiple paragraphs and some formatting.

    Key points:
    - Point 1: Testing is important
    - Point 2: Coverage matters
    - Point 3: Quality first

    End of document.
    """


@pytest.fixture
def sample_document_metadata() -> DocumentMetadata:
    """Sample document metadata for testing."""
    return DocumentMetadata(
        filename="test_document.pdf",
        file_size=1024,
        author="Test Author",
        title="Test Document",
        description="A test document for unit testing",
        tags=["test", "sample", "pdf"],
        custom_properties={"key": "value"},
        source="test",
    )


@pytest.fixture
def sample_document_content(sample_text_content: str) -> DocumentContent:
    """Sample document content for testing."""
    return DocumentContent(
        text=sample_text_content,
        structured_content={
            "paragraphs": [
                {"text": "Paragraph 1", "style": "normal"},
                {"text": "Paragraph 2", "style": "heading"},
            ],
            "sections": [
                {"title": "Introduction", "level": 1},
                {"title": "Conclusion", "level": 1},
            ],
        },
        images=[
            {"id": "img1", "format": "png", "width": 100, "height": 100},
        ],
        tables=[
            {
                "headers": ["Name", "Value"],
                "rows": [["Item1", "100"], ["Item2", "200"]],
            },
        ],
        hyperlinks=[
            {"url": "https://example.com", "text": "Example"},
        ],
        metadata={"page_count": 5},
    )


@pytest.fixture
def sample_document_bytes() -> bytes:
    """Sample document bytes for testing."""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"


@pytest.fixture
def sample_base_document(
    sample_document_bytes: bytes,
    sample_document_metadata: DocumentMetadata,
) -> BaseDocument:
    """Sample base document for testing."""
    return BaseDocument.from_bytes(
        content=sample_document_bytes,
        filename="test.pdf",
        format=DocumentType.PDF,
        metadata=sample_document_metadata,
    )


@pytest.fixture
def sample_documents() -> Dict[DocumentFormat, BaseDocument]:
    """Sample documents for all supported formats."""
    documents = {}

    # PDF document
    documents[DocumentFormat.PDF] = BaseDocument.from_bytes(
        content=b"%PDF-1.4 test content",
        filename="test.pdf",
        format=DocumentFormat.PDF,
    )

    # DOCX document
    documents[DocumentFormat.DOCX] = BaseDocument.from_bytes(
        content=b"PK\x03\x04 docx content",
        filename="test.docx",
        format=DocumentFormat.DOCX,
    )

    # XLSX document
    documents[DocumentFormat.XLSX] = BaseDocument.from_bytes(
        content=b"PK\x03\x04 xlsx content",
        filename="test.xlsx",
        format=DocumentFormat.XLSX,
    )

    # PPTX document
    documents[DocumentFormat.PPTX] = BaseDocument.from_bytes(
        content=b"PK\x03\x04 pptx content",
        filename="test.pptx",
        format=DocumentFormat.PPTX,
    )

    # TXT document
    documents[DocumentFormat.TXT] = BaseDocument.from_bytes(
        content=b"Plain text content for testing",
        filename="test.txt",
        format=DocumentFormat.TXT,
    )

    return documents


# ============================================================================
# Processing Engine Fixtures
# ============================================================================

@pytest.fixture
async def processing_engine() -> ProcessingEngine:
    """Create and start a processing engine for testing."""
    engine = ProcessingEngine(max_workers=2, enable_metrics=True)
    await engine.start()
    yield engine
    await engine.stop()


@pytest.fixture
def processing_context() -> ProcessingContext:
    """Sample processing context for testing."""
    return ProcessingContext(
        request_id="test-request-001",
        user_id="test-user",
        tenant_id="test-tenant",
        options={"extract_text": True, "extract_images": False},
        priority=5,
        timeout_seconds=60.0,
        max_retries=2,
    )


@pytest.fixture
def sample_processing_result() -> ProcessingResult:
    """Sample processing result for testing."""
    return ProcessingResult(
        document_id="doc-123",
        status=ProcessingStatus.COMPLETED,
        content=DocumentContent(text="Extracted text"),
        validation_result=ValidationResult.valid(),
        processing_time_ms=150.0,
        context=ProcessingContext(),
    )


# ============================================================================
# MCP Fixtures
# ============================================================================

@pytest.fixture
def mcp_server() -> MCPServer:
    """Create an MCP server for testing."""
    return MCPServer(name="test-server", version="1.0.0", max_connections=10)


@pytest.fixture
def sample_mcp_request() -> MCPRequest:
    """Sample MCP request for testing."""
    return MCPRequest(
        method="process_document",
        params={"document_id": "doc-123", "options": {}},
        id="req-001",
    )


@pytest.fixture
def sample_mcp_response() -> MCPResponse:
    """Sample MCP response for testing."""
    return MCPResponse.success(
        id="req-001",
        result={"status": "completed", "document_id": "doc-123"},
    )


@pytest.fixture
def sample_mcp_message() -> MCPMessage:
    """Sample MCP message for testing."""
    return MCPMessage.request(
        method="extract_content",
        params={"document_id": "doc-123"},
        id="msg-001",
    )


@pytest.fixture
def sample_mcp_error() -> MCPError:
    """Sample MCP error for testing."""
    return MCPError.document_not_found("doc-123")


# ============================================================================
# Skills Fixtures
# ============================================================================

class MockSkill(BaseSkill):
    """Mock skill for testing."""

    name = "mock_skill"
    version = "1.0.0"
    description = "A mock skill for testing"
    supported_formats = [DocumentFormat.PDF, DocumentFormat.DOCX]

    async def execute(self, input_data: Any, context: SkillContext) -> SkillResult:
        """Execute the mock skill."""
        return SkillResult.success(
            data={"input": input_data, "processed": True},
            execution_time_ms=10.0,
        )


class FailingSkill(BaseSkill):
    """Failing skill for testing error handling."""

    name = "failing_skill"
    version = "1.0.0"
    description = "A skill that always fails"

    async def execute(self, input_data: Any, context: SkillContext) -> SkillResult:
        """Execute and fail."""
        return SkillResult.failure(
            error="Intentional failure for testing",
            execution_time_ms=5.0,
        )


class TimeoutSkill(BaseSkill):
    """Skill that times out for testing."""

    name = "timeout_skill"
    version = "1.0.0"
    description = "A skill that times out"

    async def execute(self, input_data: Any, context: SkillContext) -> SkillResult:
        """Execute and timeout."""
        await asyncio.sleep(10)  # Will be interrupted by timeout
        return SkillResult.success(data={})


@pytest.fixture
def mock_skill() -> MockSkill:
    """Create a mock skill for testing."""
    return MockSkill()


@pytest.fixture
def failing_skill() -> FailingSkill:
    """Create a failing skill for testing."""
    return FailingSkill()


@pytest.fixture
def timeout_skill() -> TimeoutSkill:
    """Create a timeout skill for testing."""
    return TimeoutSkill()


@pytest.fixture
def skill_registry() -> SkillRegistry:
    """Create a skill registry for testing."""
    return SkillRegistry()


@pytest.fixture
def skill_context(sample_base_document: BaseDocument) -> SkillContext:
    """Create a skill context for testing."""
    return SkillContext(
        document=sample_base_document,
        config={"option1": "value1"},
        variables={"var1": "value1"},
        user_id="test-user",
        request_id="test-request-001",
    )


# ============================================================================
# Security Fixtures
# ============================================================================

@pytest.fixture
def auth_manager() -> AuthManager:
    """Create an auth manager for testing."""
    return AuthManager(secret_key="test-secret-key-for-testing-only")


@pytest.fixture
def password_manager() -> PasswordManager:
    """Create a password manager for testing."""
    return PasswordManager(
        min_length=8,
        require_uppercase=True,
        require_lowercase=True,
        require_digits=True,
        require_special=True,
    )


@pytest.fixture
def token_manager() -> TokenManager:
    """Create a token manager for testing."""
    return TokenManager(
        secret_key="test-secret-key",
        algorithm="HS256",
        access_token_expire=1,  # 1 hour
        refresh_token_expire=7,  # 7 days
    )


@pytest.fixture
def sample_user() -> User:
    """Create a sample user for testing."""
    return User(
        id="user-123",
        username="testuser",
        email="test@example.com",
        role=Role.USER,
        is_active=True,
    )


@pytest.fixture
def sample_admin_user() -> User:
    """Create a sample admin user for testing."""
    return User(
        id="admin-123",
        username="adminuser",
        email="admin@example.com",
        role=Role.ADMIN,
        is_active=True,
    )


@pytest.fixture
def sample_resource() -> Resource:
    """Create a sample resource for testing."""
    return Resource(
        id="res-123",
        type="document",
        owner_id="user-123",
        is_public=False,
    )


@pytest.fixture
def sandbox_executor() -> SandboxExecutor:
    """Create a sandbox executor for testing."""
    return SandboxExecutor(
        resource_limits=ResourceLimits(
            max_memory_mb=128,
            max_cpu_percent=50.0,
            max_execution_time=5.0,
            max_processes=2,
        ),
        network_enabled=False,
    )


# ============================================================================
# Performance Fixtures
# ============================================================================

@pytest.fixture
def metrics_collector() -> MetricsCollector:
    """Create a metrics collector for testing."""
    return MetricsCollector(max_data_points=100, retention_hours=1)


@pytest.fixture
def health_checker() -> HealthChecker:
    """Create a health checker for testing."""
    return HealthChecker()


@pytest.fixture
def alert_manager(metrics_collector: MetricsCollector) -> AlertManager:
    """Create an alert manager for testing."""
    return AlertManager(metrics_collector, check_interval=5.0)


@pytest.fixture
def system_monitor() -> SystemMonitor:
    """Create a system monitor for testing."""
    return SystemMonitor()


@pytest.fixture
def sample_alert_rule() -> AlertRule:
    """Create a sample alert rule for testing."""
    return AlertRule(
        name="high_cpu_usage",
        metric_name="system_cpu_percent",
        condition=">",
        threshold=80.0,
        duration=60.0,
        severity="warning",
        message="CPU usage is above 80%",
    )


# ============================================================================
# Temporary Directory Fixtures
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_file(temp_dir: Path) -> Path:
    """Create a temporary file for testing."""
    file_path = temp_dir / "test_file.txt"
    file_path.write_text("Test content")
    yield file_path


# ============================================================================
# Mock Handler for MCP
# ============================================================================

class MockMCPHandler(MCPHandler):
    """Mock MCP handler for testing."""

    def __init__(self, method_name: str = "test_method"):
        self._method = method_name
        self.handle_called = False
        self.last_request = None

    @property
    def method(self) -> str:
        return self._method

    async def handle(self, request: MCPRequest) -> MCPResponse:
        self.handle_called = True
        self.last_request = request
        return MCPResponse.success(
            id=request.id,
            result={"handled": True, "method": self._method},
        )


@pytest.fixture
def mock_mcp_handler() -> MockMCPHandler:
    """Create a mock MCP handler for testing."""
    return MockMCPHandler()


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )


# ============================================================================
# Async Test Helpers
# ============================================================================

async def run_async(coro):
    """Helper to run async coroutines in sync context."""
    return await coro
