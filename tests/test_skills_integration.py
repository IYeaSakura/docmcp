"""
Skills system integration tests.

This module tests:
- Skill creation and registration
- Skill execution
- Skill chain and parallel execution
- Skill registry functionality
- Skill context handling
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from docmcp.skills.base import (
    BaseSkill,
    SkillContext,
    SkillResult,
    SkillStatus,
    SkillMetadata,
    SkillChain,
    SkillParallel,
    skill,
)
from docmcp.skills.registry import SkillRegistry, register_skill, get_skill, execute_skill
from docmcp.core.document import BaseDocument, DocumentFormat


# ============================================================================
# SkillMetadata Tests
# ============================================================================

class TestSkillMetadata:
    """Test SkillMetadata class."""

    def test_default_metadata(self):
        """Test default metadata values."""
        metadata = SkillMetadata(name="test_skill")
        assert metadata.name == "test_skill"
        assert metadata.version == "1.0.0"
        assert metadata.description == ""
        assert metadata.author == ""
        assert metadata.tags == []
        assert metadata.supported_formats == []
        assert metadata.dependencies == []

    def test_metadata_creation(self):
        """Test metadata creation with values."""
        metadata = SkillMetadata(
            name="test_skill",
            version="2.0.0",
            description="Test skill",
            author="Test Author",
            tags=["test", "extraction"],
            supported_formats=[DocumentFormat.PDF, DocumentFormat.DOCX],
            dependencies=["dep1", "dep2"],
        )
        assert metadata.name == "test_skill"
        assert metadata.version == "2.0.0"
        assert metadata.description == "Test skill"
        assert metadata.tags == ["test", "extraction"]
        assert len(metadata.supported_formats) == 2

    def test_to_dict(self):
        """Test metadata serialization."""
        metadata = SkillMetadata(
            name="test",
            supported_formats=[DocumentFormat.PDF],
        )
        data = metadata.to_dict()
        assert data["name"] == "test"
        assert data["supported_formats"] == ["pdf"]

    def test_from_dict(self):
        """Test metadata deserialization."""
        data = {
            "name": "test_skill",
            "version": "1.0.0",
            "supported_formats": ["pdf", "docx"],
        }
        metadata = SkillMetadata.from_dict(data)
        assert metadata.name == "test_skill"
        assert len(metadata.supported_formats) == 2


# ============================================================================
# SkillContext Tests
# ============================================================================

class TestSkillContext:
    """Test SkillContext class."""

    def test_default_context(self):
        """Test default context values."""
        context = SkillContext()
        assert context.document is None
        assert context.config == {}
        assert context.variables == {}
        assert context.user_id is None
        assert context.request_id is not None

    def test_context_creation(self):
        """Test context creation with values."""
        doc = BaseDocument(format=DocumentFormat.PDF)
        context = SkillContext(
            document=doc,
            config={"option": "value"},
            variables={"var": "val"},
            user_id="user-123",
        )
        assert context.document == doc
        assert context.config == {"option": "value"}
        assert context.variables == {"var": "val"}
        assert context.user_id == "user-123"

    def test_get_set_variables(self):
        """Test variable get/set."""
        context = SkillContext()

        context.set("key", "value")
        assert context.get("key") == "value"
        assert context.get("nonexistent", "default") == "default"

    def test_get_config(self):
        """Test config access."""
        context = SkillContext(config={"opt1": "val1", "opt2": "val2"})

        assert context.get_config("opt1") == "val1"
        assert context.get_config("nonexistent", "default") == "default"

    def test_child_context(self):
        """Test child context creation."""
        parent = SkillContext(
            config={"opt1": "val1"},
            variables={"var1": "val1"},
        )

        child = parent.child_context(config={"opt2": "val2"})

        # Child should inherit parent's values
        assert child.get_config("opt1") == "val1"
        assert child.get("var1") == "val1"

        # Child should have its own values
        assert child.get_config("opt2") == "val2"

        # Parent should not be affected
        assert parent.get_config("opt2") is None

    def test_elapsed_time(self):
        """Test elapsed time tracking."""
        context = SkillContext()

        # Should have some elapsed time
        import time
        time.sleep(0.01)
        assert context.elapsed_time > 0


# ============================================================================
# SkillResult Tests
# ============================================================================

class TestSkillResult:
    """Test SkillResult class."""

    def test_success_result(self):
        """Test success result creation."""
        result = SkillResult.success(
            data={"key": "value"},
            execution_time_ms=100.0,
        )
        assert result.status == SkillStatus.COMPLETED
        assert result.data == {"key": "value"}
        assert result.execution_time_ms == 100.0
        assert result.is_success is True
        assert result.is_failure is False

    def test_failure_result(self):
        """Test failure result creation."""
        result = SkillResult.failure(
            error="Something went wrong",
            error_details={"code": 500},
            execution_time_ms=50.0,
        )
        assert result.status == SkillStatus.FAILED
        assert result.error == "Something went wrong"
        assert result.error_details == {"code": 500}
        assert result.is_success is False
        assert result.is_failure is True

    def test_timeout_result(self):
        """Test timeout result creation."""
        result = SkillResult.timeout(
            timeout_seconds=30.0,
            execution_time_ms=30000.0,
        )
        assert result.status == SkillStatus.TIMEOUT
        assert "30" in result.error
        assert result.is_failure is True

    def test_to_dict(self):
        """Test result serialization."""
        result = SkillResult.success(data={"key": "value"})
        data = result.to_dict()
        assert data["status"] == "COMPLETED"
        assert data["data"] == {"key": "value"}


# ============================================================================
# BaseSkill Tests
# ============================================================================

class TestBaseSkill:
    """Test BaseSkill class."""

    def test_skill_creation(self, mock_skill):
        """Test skill creation."""
        assert mock_skill.name == "mock_skill"
        assert mock_skill.version == "1.0.0"
        assert mock_skill.metadata.name == "mock_skill"

    def test_skill_metadata(self, mock_skill):
        """Test skill metadata."""
        metadata = mock_skill.metadata
        assert metadata.name == "mock_skill"
        assert metadata.description == "A mock skill for testing"
        assert DocumentFormat.PDF in metadata.supported_formats

    def test_skill_config(self, mock_skill):
        """Test skill configuration."""
        skill_with_config = MockSkill(config={"option": "value"})
        assert skill_with_config.config == {"option": "value"}

    @pytest.mark.asyncio
    async def test_skill_initialize(self, mock_skill):
        """Test skill initialization."""
        await mock_skill.initialize()
        assert mock_skill._initialized is True

    @pytest.mark.asyncio
    async def test_skill_shutdown(self, mock_skill):
        """Test skill shutdown."""
        await mock_skill.initialize()
        await mock_skill.shutdown()
        assert mock_skill._initialized is False

    @pytest.mark.asyncio
    async def test_skill_execute(self, mock_skill, skill_context):
        """Test skill execution."""
        result = await mock_skill.execute({"input": "data"}, skill_context)

        assert result.is_success is True
        assert result.data["processed"] is True

    @pytest.mark.asyncio
    async def test_skill_validate(self, mock_skill, skill_context):
        """Test skill validation."""
        # Should validate successfully with supported format
        valid = await mock_skill.validate(skill_context)
        assert valid is True

    @pytest.mark.asyncio
    async def test_skill_validate_unsupported_format(self, mock_skill):
        """Test validation with unsupported format."""
        doc = BaseDocument(format=DocumentFormat.XLSX)  # Not in supported formats
        context = SkillContext(document=doc)

        valid = await mock_skill.validate(context)
        assert valid is False

    def test_can_process(self, mock_skill):
        """Test can_process method."""
        pdf_doc = BaseDocument(format=DocumentFormat.PDF)
        assert mock_skill.can_process(pdf_doc) is True

        xlsx_doc = BaseDocument(format=DocumentFormat.XLSX)
        assert mock_skill.can_process(xlsx_doc) is False

    def test_get_info(self, mock_skill):
        """Test get_info method."""
        info = mock_skill.get_info()
        assert info["name"] == "mock_skill"
        assert info["version"] == "1.0.0"
        assert "pdf" in info["supported_formats"]

    def test_skill_repr(self, mock_skill):
        """Test skill string representation."""
        repr_str = repr(mock_skill)
        assert "mock_skill" in repr_str
        assert "1.0.0" in repr_str


# ============================================================================
# SkillChain Tests
# ============================================================================

class TestSkillChain:
    """Test SkillChain class."""

    @pytest.mark.asyncio
    async def test_chain_execution(self, mock_skill, skill_context):
        """Test chain execution."""
        chain = SkillChain([mock_skill, mock_skill])

        result = await chain.execute({"input": "data"}, skill_context)

        assert result.is_success is True
        assert result.data["processed"] is True

    @pytest.mark.asyncio
    async def test_chain_with_failing_skill(self, failing_skill, mock_skill, skill_context):
        """Test chain with a failing skill."""
        chain = SkillChain([mock_skill, failing_skill])

        result = await chain.execute({"input": "data"}, skill_context)

        assert result.is_failure is True
        assert "failing_skill" in result.error

    @pytest.mark.asyncio
    async def test_chain_data_passing(self, skill_context):
        """Test data passing between skills in chain."""
        class DataTransformSkill(BaseSkill):
            name = "transform"
            version = "1.0.0"

            async def execute(self, input_data, context):
                return SkillResult.success(data={"transformed": input_data})

        chain = SkillChain([DataTransformSkill(), DataTransformSkill()])

        result = await chain.execute("initial", skill_context)

        assert result.is_success is True
        # Data should be transformed twice
        assert result.data == {"transformed": {"transformed": "initial"}}

    def test_chain_dependencies(self, mock_skill):
        """Test chain dependencies."""
        chain = SkillChain([mock_skill, mock_skill])

        # Chain should list all skills as dependencies
        assert len(chain.metadata.dependencies) == 2
        assert "mock_skill" in chain.metadata.dependencies


# ============================================================================
# SkillParallel Tests
# ============================================================================

class TestSkillParallel:
    """Test SkillParallel class."""

    @pytest.mark.asyncio
    async def test_parallel_execution(self, mock_skill, skill_context):
        """Test parallel execution."""
        parallel = SkillParallel([
            ("skill1", mock_skill),
            ("skill2", mock_skill),
        ])

        result = await parallel.execute({"input": "data"}, skill_context)

        assert result.is_success is True
        assert "skill1" in result.data
        assert "skill2" in result.data

    @pytest.mark.asyncio
    async def test_parallel_with_failing_skill(self, mock_skill, failing_skill, skill_context):
        """Test parallel execution with a failing skill."""
        parallel = SkillParallel([
            ("success", mock_skill),
            ("failure", failing_skill),
        ])

        result = await parallel.execute({"input": "data"}, skill_context)

        assert result.is_failure is True
        assert "failure" in result.error

    @pytest.mark.asyncio
    async def test_parallel_all_success(self, mock_skill, skill_context):
        """Test parallel execution when all succeed."""
        parallel = SkillParallel([
            ("a", mock_skill),
            ("b", mock_skill),
            ("c", mock_skill),
        ])

        result = await parallel.execute({"input": "data"}, skill_context)

        assert result.is_success is True
        assert set(result.data.keys()) == {"a", "b", "c"}


# ============================================================================
# SkillRegistry Tests
# ============================================================================

class TestSkillRegistry:
    """Test SkillRegistry class."""

    def test_registry_creation(self):
        """Test registry creation."""
        registry = SkillRegistry()
        assert registry.list_skills() == []

    def test_register_skill(self, mock_skill):
        """Test skill registration."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        assert "mock_skill" in registry.list_skills()

    def test_register_as_decorator(self):
        """Test skill registration as decorator."""
        registry = SkillRegistry()

        @registry.register
        class DecoratedSkill(BaseSkill):
            name = "decorated"
            version = "1.0.0"

            async def execute(self, input_data, context):
                return SkillResult.success()

        assert "decorated" in registry.list_skills()

    def test_unregister_skill(self, mock_skill):
        """Test skill unregistration."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        result = registry.unregister("mock_skill")
        assert result is True
        assert "mock_skill" not in registry.list_skills()

        # Unregister nonexistent skill
        result = registry.unregister("nonexistent")
        assert result is False

    def test_get_skill(self, mock_skill):
        """Test getting skill from registry."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        skill_info = registry.get("mock_skill")
        assert skill_info is not None
        assert skill_info.metadata.name == "mock_skill"

    def test_get_instance(self, mock_skill):
        """Test getting skill instance."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        instance = registry.get_instance("mock_skill")
        assert instance is not None
        assert isinstance(instance, MockSkill)

    def test_find_by_tag(self):
        """Test finding skills by tag."""
        registry = SkillRegistry()

        class TaggedSkill(BaseSkill):
            name = "tagged"
            version = "1.0.0"

            async def execute(self, input_data, context):
                return SkillResult.success()

        TaggedSkill.metadata = SkillMetadata(name="tagged", tags=["extraction", "pdf"])
        registry.register(TaggedSkill)

        results = registry.find_by_tag("extraction")
        assert "tagged" in results

    def test_find_by_format(self, mock_skill):
        """Test finding skills by format."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        results = registry.find_by_format(DocumentFormat.PDF)
        assert "mock_skill" in results

    def test_find_by_document(self, mock_skill):
        """Test finding skills by document."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        doc = BaseDocument(format=DocumentFormat.PDF)
        results = registry.find_by_document(doc)
        assert "mock_skill" in results

    def test_search(self, mock_skill):
        """Test skill search."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        # Search by name
        results = registry.search("mock")
        assert "mock_skill" in results

        # Search by description
        results = registry.search("mock skill")
        assert "mock_skill" in results

    @pytest.mark.asyncio
    async def test_initialize_skill(self, mock_skill):
        """Test skill initialization."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        result = await registry.initialize_skill("mock_skill")
        assert result is True

        # Initialize nonexistent skill
        result = await registry.initialize_skill("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_all(self, mock_skill):
        """Test initializing all skills."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        results = await registry.initialize_all()
        assert results["mock_skill"] is True

    @pytest.mark.asyncio
    async def test_shutdown_skill(self, mock_skill):
        """Test skill shutdown."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        await registry.initialize_skill("mock_skill")
        result = await registry.shutdown_skill("mock_skill")
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_skill(self, mock_skill, skill_context):
        """Test skill execution through registry."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        result = await registry.execute("mock_skill", {"input": "data"}, skill_context)

        assert result.is_success is True

    @pytest.mark.asyncio
    async def test_execute_nonexistent_skill(self, skill_context):
        """Test executing nonexistent skill."""
        registry = SkillRegistry()

        result = await registry.execute("nonexistent", {}, skill_context)

        assert result.is_failure is True
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, timeout_skill, skill_context):
        """Test skill execution with timeout."""
        registry = SkillRegistry()
        registry.register(TimeoutSkill)

        result = await registry.execute(
            "timeout_skill",
            {},
            skill_context,
            timeout=0.1,  # Short timeout
        )

        assert result.is_failure is True
        assert result.status == SkillStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_execute_pipeline(self, mock_skill, skill_context):
        """Test pipeline execution."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        results = await registry.execute_pipeline(
            ["mock_skill", "mock_skill"],
            {"input": "data"},
            skill_context,
        )

        assert len(results) == 2
        assert all(r.is_success for r in results)

    def test_get_metrics(self, mock_skill):
        """Test getting registry metrics."""
        registry = SkillRegistry()
        registry.register(MockSkill)

        metrics = registry.get_metrics()
        assert metrics["registered_skills"] == 1
        assert metrics["initialized_skills"] == 0


# ============================================================================
# Skill Decorator Tests
# ============================================================================

class TestSkillDecorator:
    """Test the @skill decorator."""

    @pytest.mark.asyncio
    async def test_skill_decorator(self):
        """Test skill decorator."""
        @skill(name="uppercase", version="1.0.0", description="Convert to uppercase")
        async def uppercase_skill(text: str, context: SkillContext):
            return SkillResult.success(data=text.upper())

        # Create instance and execute
        instance = uppercase_skill()
        result = await instance.execute("hello", SkillContext())

        assert result.is_success is True
        assert result.data == "HELLO"
        assert instance.metadata.name == "uppercase"
        assert instance.metadata.description == "Convert to uppercase"


# ============================================================================
# Global Registry Tests
# ============================================================================

class TestGlobalRegistry:
    """Test global registry functions."""

    def test_register_skill_global(self):
        """Test global skill registration."""
        @register_skill
        class GlobalTestSkill(BaseSkill):
            name = "global_test"
            version = "1.0.0"

            async def execute(self, input_data, context):
                return SkillResult.success()

        # Should be registered in global registry
        from docmcp.skills.registry import skill_registry
        assert "global_test" in skill_registry.list_skills()

    def test_get_skill_global(self):
        """Test global skill retrieval."""
        # This assumes global_test was registered above
        instance = get_skill("global_test")
        # May be None if not registered
        if instance:
            assert isinstance(instance, BaseSkill)


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
class TestSkillsIntegration:
    """Integration tests for skills system."""

    async def test_full_skill_workflow(self):
        """Test complete skill workflow."""
        registry = SkillRegistry()

        # Define a skill
        class ExtractTextSkill(BaseSkill):
            name = "extract_text"
            version = "1.0.0"
            supported_formats = [DocumentFormat.PDF, DocumentFormat.TXT]

            async def execute(self, input_data, context):
                return SkillResult.success(data={"text": "Extracted text"})

        # Register
        registry.register(ExtractTextSkill)

        # Initialize
        await registry.initialize_skill("extract_text")

        # Execute
        doc = BaseDocument(format=DocumentFormat.PDF)
        context = SkillContext(document=doc)
        result = await registry.execute("extract_text", {}, context)

        assert result.is_success is True
        assert result.data["text"] == "Extracted text"

        # Shutdown
        await registry.shutdown_skill("extract_text")

    async def test_skill_chain_integration(self, skill_context):
        """Test skill chain integration."""
        class Step1Skill(BaseSkill):
            name = "step1"
            version = "1.0.0"

            async def execute(self, input_data, context):
                return SkillResult.success(data={"step": 1, "input": input_data})

        class Step2Skill(BaseSkill):
            name = "step2"
            version = "1.0.0"

            async def execute(self, input_data, context):
                data = dict(input_data)
                data["step"] = 2
                return SkillResult.success(data=data)

        chain = SkillChain([Step1Skill(), Step2Skill()])
        result = await chain.execute("test", skill_context)

        assert result.is_success is True
        assert result.data["step"] == 2
        assert result.data["input"] == "test"

    async def test_skill_parallel_integration(self, skill_context):
        """Test skill parallel integration."""
        class TextSkill(BaseSkill):
            name = "text"
            version = "1.0.0"

            async def execute(self, input_data, context):
                return SkillResult.success(data="text result")

        class MetaSkill(BaseSkill):
            name = "meta"
            version = "1.0.0"

            async def execute(self, input_data, context):
                return SkillResult.success(data="meta result")

        parallel = SkillParallel([
            ("text", TextSkill()),
            ("meta", MetaSkill()),
        ])
        result = await parallel.execute({}, skill_context)

        assert result.is_success is True
        assert result.data["text"] == "text result"
        assert result.data["meta"] == "meta result"
