"""
Base classes for the Skills plugin system.

This module defines the core abstractions for Skills, including:
    - BaseSkill: Abstract base class for all skills
    - SkillContext: Execution context for skills
    - SkillResult: Result wrapper for skill execution
    - SkillMetadata: Metadata descriptor for skills
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Callable, TypeVar, Generic

from docmcp.core.document import BaseDocument, DocumentFormat


class SkillStatus(Enum):
    """Status of a skill execution."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    TIMEOUT = auto()


@dataclass
class SkillMetadata:
    """
    Metadata for a Skill.

    Attributes:
        name: Unique skill name
        version: Semantic version string
        description: Human-readable description
        author: Skill author
        tags: List of tags for categorization
        supported_formats: Document formats this skill supports
        dependencies: List of required skill dependencies
        config_schema: JSON schema for skill configuration
        entry_point: Module entry point for dynamic loading
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    tags: List[str] = field(default_factory=list)
    supported_formats: List[DocumentFormat] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    entry_point: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "supported_formats": [f.value for f in self.supported_formats],
            "dependencies": self.dependencies,
            "config_schema": self.config_schema,
            "entry_point": self.entry_point,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SkillMetadata:
        """Create metadata from dictionary."""
        formats = [
            DocumentFormat(f) for f in data.get("supported_formats", [])
        ]
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            tags=data.get("tags", []),
            supported_formats=formats,
            dependencies=data.get("dependencies", []),
            config_schema=data.get("config_schema"),
            entry_point=data.get("entry_point"),
        )


@dataclass
class SkillContext:
    """
    Execution context for Skills.

    Provides access to resources, configuration, and state during
    skill execution.

    Attributes:
        document: Document being processed (if applicable)
        config: Skill configuration
        variables: Runtime variables
        metadata: Execution metadata
        user_id: ID of the user executing the skill
        request_id: Unique request identifier
        parent_context: Parent skill context (for nested execution)
    """

    document: Optional[BaseDocument] = None
    config: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    request_id: str = field(default_factory=lambda: f"req_{int(time.time() * 1000)}")
    parent_context: Optional[SkillContext] = None
    _start_time: float = field(default_factory=time.time)

    @property
    def elapsed_time(self) -> float:
        """Time elapsed since context creation."""
        return time.time() - self._start_time

    def get(self, key: str, default: Any = None) -> Any:
        """Get a variable value."""
        return self.variables.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a variable value."""
        self.variables[key] = value

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(key, default)

    def child_context(self, **kwargs) -> SkillContext:
        """Create a child context."""
        return SkillContext(
            document=kwargs.get("document", self.document),
            config={**self.config, **kwargs.get("config", {})},
            variables=dict(self.variables),
            metadata={**self.metadata, **kwargs.get("metadata", {})},
            user_id=kwargs.get("user_id", self.user_id),
            request_id=self.request_id,
            parent_context=self,
        )


@dataclass
class SkillResult:
    """
    Result of skill execution.

    Attributes:
        status: Execution status
        data: Result data
        error: Error message (if failed)
        error_details: Detailed error information
        execution_time_ms: Execution time in milliseconds
        metadata: Additional result metadata
    """

    status: SkillStatus
    data: Any = None
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if execution was successful."""
        return self.status == SkillStatus.COMPLETED

    @property
    def is_failure(self) -> bool:
        """Check if execution failed."""
        return self.status in (SkillStatus.FAILED, SkillStatus.TIMEOUT)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "status": self.status.name,
            "data": self.data,
            "error": self.error,
            "error_details": self.error_details,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def success(
        cls,
        data: Any = None,
        execution_time_ms: float = 0.0,
        **metadata,
    ) -> SkillResult:
        """Create a successful result."""
        return cls(
            status=SkillStatus.COMPLETED,
            data=data,
            execution_time_ms=execution_time_ms,
            metadata=metadata,
        )

    @classmethod
    def failure(
        cls,
        error: str,
        error_details: Optional[Dict[str, Any]] = None,
        execution_time_ms: float = 0.0,
    ) -> SkillResult:
        """Create a failed result."""
        return cls(
            status=SkillStatus.FAILED,
            error=error,
            error_details=error_details,
            execution_time_ms=execution_time_ms,
        )

    @classmethod
    def timeout(
        cls,
        timeout_seconds: float,
        execution_time_ms: float = 0.0,
    ) -> SkillResult:
        """Create a timeout result."""
        return cls(
            status=SkillStatus.TIMEOUT,
            error=f"Execution timed out after {timeout_seconds}s",
            execution_time_ms=execution_time_ms,
        )


class BaseSkill(ABC):
    """
    Abstract base class for all Skills.

    Skills are modular processing units that can be dynamically loaded
    and executed. Each skill has a unique name, version, and can declare
    its supported document formats and dependencies.

    Attributes:
        name: Unique skill name (class attribute)
        version: Skill version (class attribute)
        metadata: Skill metadata

    Example:
        >>> class TextExtractionSkill(BaseSkill):
        ...     name = "text_extraction"
        ...     version = "1.0.0"
        ...
        ...     def __init__(self):
        ...         super().__init__()
        ...         self.metadata.supported_formats = [DocumentFormat.PDF, DocumentFormat.DOCX]
        ...
        ...     async def execute(self, input_data, context):
        ...         # Extract text from document
        ...         document = context.document
        ...         text = await self._extract_text(document)
        ...         return SkillResult.success(data={"text": text})
        ...
        ...     async def validate(self, context):
        ...         # Validate skill can execute
        ...         if not context.document:
        ...             return False
        ...         return context.document.format in self.metadata.supported_formats
    """

    # Class attributes to be overridden by subclasses
    name: str = ""
    version: str = "1.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the skill.

        Args:
            config: Skill configuration
        """
        self._config = config or {}
        self._metadata = self._create_metadata()
        self._initialized = False

    def _create_metadata(self) -> SkillMetadata:
        """Create metadata from class attributes."""
        return SkillMetadata(
            name=self.name or self.__class__.__name__,
            version=self.version,
            description=getattr(self, "description", ""),
            author=getattr(self, "author", ""),
            tags=getattr(self, "tags", []),
            supported_formats=getattr(self, "supported_formats", []),
            dependencies=getattr(self, "dependencies", []),
        )

    @property
    def metadata(self) -> SkillMetadata:
        """Get skill metadata."""
        return self._metadata

    @property
    def config(self) -> Dict[str, Any]:
        """Get skill configuration."""
        return self._config

    async def initialize(self) -> None:
        """
        Initialize the skill.

        Override this method to perform one-time initialization.
        """
        self._initialized = True

    async def shutdown(self) -> None:
        """
        Shutdown the skill.

        Override this method to perform cleanup.
        """
        self._initialized = False

    @abstractmethod
    async def execute(
        self,
        input_data: Any,
        context: SkillContext,
    ) -> SkillResult:
        """
        Execute the skill.

        Args:
            input_data: Input data for the skill
            context: Execution context

        Returns:
            SkillResult with execution result
        """
        pass

    async def validate(self, context: SkillContext) -> bool:
        """
        Validate if the skill can execute in the given context.

        Override this method to implement custom validation logic.

        Args:
            context: Execution context

        Returns:
            True if skill can execute, False otherwise
        """
        # Check document format support
        if context.document and self.metadata.supported_formats:
            if context.document.format not in self.metadata.supported_formats:
                return False

        return True

    def can_process(self, document: BaseDocument) -> bool:
        """
        Check if this skill can process the given document.

        Args:
            document: Document to check

        Returns:
            True if skill can process the document
        """
        if not self.metadata.supported_formats:
            return True
        return document.format in self.metadata.supported_formats

    def get_info(self) -> Dict[str, Any]:
        """Get skill information."""
        return {
            "name": self.metadata.name,
            "version": self.metadata.version,
            "description": self.metadata.description,
            "author": self.metadata.author,
            "tags": self.metadata.tags,
            "supported_formats": [f.value for f in self.metadata.supported_formats],
            "dependencies": self.metadata.dependencies,
            "initialized": self._initialized,
        }

    def __repr__(self) -> str:
        return f"Skill({self.metadata.name}@{self.metadata.version})"


# Decorator for creating simple skills

def skill(
    name: Optional[str] = None,
    version: str = "1.0.0",
    description: str = "",
    supported_formats: Optional[List[DocumentFormat]] = None,
):
    """
    Decorator for creating simple skills from functions.

    Args:
        name: Skill name (defaults to function name)
        version: Skill version
        description: Skill description
        supported_formats: List of supported document formats

    Example:
        >>> @skill(name="uppercase", version="1.0.0")
        ... async def uppercase_skill(text: str, context: SkillContext):
        ...     return SkillResult.success(data=text.upper())
    """
    def decorator(func: Callable) -> type[BaseSkill]:
        skill_name = name or func.__name__
        skill_formats = supported_formats or []

        class FunctionSkill(BaseSkill):
            name = skill_name
            version = version
            description = description or func.__doc__ or ""
            supported_formats = skill_formats

            async def execute(self, input_data: Any, context: SkillContext) -> SkillResult:
                return await func(input_data, context)

        # Preserve function metadata
        FunctionSkill.__doc__ = func.__doc__
        FunctionSkill.__module__ = func.__module__

        return FunctionSkill

    return decorator


# Skill composition utilities

class SkillChain(BaseSkill):
    """
    Chain multiple skills together.

    Executes skills sequentially, passing the output of each skill
    as input to the next.

    Example:
        >>> chain = SkillChain([
        ...     TextExtractionSkill(),
        ...     TextCleaningSkill(),
        ...     TextAnalysisSkill(),
        ... ])
        >>> result = await chain.execute(document, context)
    """

    name = "skill_chain"
    version = "1.0.0"

    def __init__(self, skills: List[BaseSkill], config: Optional[Dict] = None):
        super().__init__(config)
        self.skills = skills
        self.metadata.dependencies = [s.metadata.name for s in skills]

    async def execute(self, input_data: Any, context: SkillContext) -> SkillResult:
        """Execute skills in sequence."""
        current_data = input_data
        total_time = 0.0

        for skill in self.skills:
            start = time.time()
            result = await skill.execute(current_data, context)
            elapsed = (time.time() - start) * 1000
            total_time += elapsed

            if result.is_failure:
                return SkillResult.failure(
                    error=f"Skill '{skill.metadata.name}' failed: {result.error}",
                    error_details={"failed_skill": skill.metadata.name},
                    execution_time_ms=total_time,
                )

            current_data = result.data

        return SkillResult.success(
            data=current_data,
            execution_time_ms=total_time,
            skills_executed=len(self.skills),
        )


class SkillParallel(BaseSkill):
    """
    Execute multiple skills in parallel.

    Executes all skills concurrently and returns combined results.

    Example:
        >>> parallel = SkillParallel([
        ...     ("text", TextExtractionSkill()),
        ...     ("metadata", MetadataExtractionSkill()),
        ... ])
        >>> result = await parallel.execute(document, context)
        >>> # result.data = {"text": ..., "metadata": ...}
    """

    name = "skill_parallel"
    version = "1.0.0"

    def __init__(
        self,
        skills: List[tuple[str, BaseSkill]],
        config: Optional[Dict] = None,
    ):
        super().__init__(config)
        self.skills = skills
        self.metadata.dependencies = [name for name, _ in skills]

    async def execute(self, input_data: Any, context: SkillContext) -> SkillResult:
        """Execute skills in parallel."""
        import asyncio

        start = time.time()

        # Create tasks for all skills
        tasks = []
        for name, skill in self.skills:
            task = asyncio.create_task(
                skill.execute(input_data, context),
                name=f"skill_{name}"
            )
            tasks.append((name, task))

        # Wait for all to complete
        results = {}
        errors = {}

        for name, task in tasks:
            try:
                result = await task
                if result.is_success:
                    results[name] = result.data
                else:
                    errors[name] = result.error
            except Exception as e:
                errors[name] = str(e)

        elapsed = (time.time() - start) * 1000

        if errors:
            return SkillResult.failure(
                error=f"Some skills failed: {errors}",
                error_details={"errors": errors, "successes": results},
                execution_time_ms=elapsed,
            )

        return SkillResult.success(
            data=results,
            execution_time_ms=elapsed,
        )
