"""
Pipeline module for DocMCP document processing.

This module provides a flexible pipeline architecture for document processing,
allowing users to compose multiple processing stages into a processing pipeline.

Features:
    - Composable pipeline stages
    - Conditional stage execution
    - Parallel stage execution
    - Error handling and recovery
    - Progress tracking
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic, Union
from enum import Enum, auto

from docmcp.core.document import BaseDocument, DocumentContent

logger = logging.getLogger(__name__)


class StageStatus(Enum):
    """Status of a pipeline stage."""
    
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    SKIPPED = auto()
    FAILED = auto()


@dataclass
class PipelineContext:
    """
    Context passed through pipeline stages.
    
    This class holds the state and data that is passed from one stage
    to the next in the pipeline.
    
    Attributes:
        document: The document being processed
        data: Stage-specific data storage
        metadata: Pipeline metadata
        stage_results: Results from each stage
    """
    
    document: BaseDocument
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    stage_results: Dict[str, Any] = field(default_factory=dict)
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in the context data."""
        self.data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the context data."""
        return self.data.get(key, default)
    
    def set_stage_result(self, stage_name: str, result: Any) -> None:
        """Store the result of a stage."""
        self.stage_results[stage_name] = result
    
    def get_stage_result(self, stage_name: str) -> Any:
        """Get the result of a stage."""
        return self.stage_results.get(stage_name)


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""
    
    status: StageStatus
    output: Any = None
    error: Optional[Exception] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success(cls, output: Any = None, **metadata) -> StageResult:
        """Create a successful stage result."""
        return cls(
            status=StageStatus.COMPLETED,
            output=output,
            metadata=metadata
        )
    
    @classmethod
    def failure(cls, error: Exception, **metadata) -> StageResult:
        """Create a failed stage result."""
        return cls(
            status=StageStatus.FAILED,
            error=error,
            metadata=metadata
        )
    
    @classmethod
    def skipped(cls, reason: str = "") -> StageResult:
        """Create a skipped stage result."""
        return cls(
            status=StageStatus.SKIPPED,
            metadata={"skip_reason": reason}
        )


@dataclass
class PipelineResult:
    """Result of a complete pipeline execution."""
    
    success: bool
    context: PipelineContext
    stage_results: Dict[str, StageResult] = field(default_factory=dict)
    total_time_ms: float = 0.0
    error: Optional[Exception] = None
    
    @property
    def failed_stages(self) -> List[str]:
        """Get list of failed stage names."""
        return [
            name for name, result in self.stage_results.items()
            if result.status == StageStatus.FAILED
        ]
    
    @property
    def completed_stages(self) -> List[str]:
        """Get list of completed stage names."""
        return [
            name for name, result in self.stage_results.items()
            if result.status == StageStatus.COMPLETED
        ]


class PipelineStage(ABC):
    """
    Abstract base class for pipeline stages.
    
    A pipeline stage represents a single processing step in a document
    processing pipeline. Stages can be composed and executed sequentially
    or in parallel.
    
    Example:
        >>> class MyStage(PipelineStage):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_stage"
        ...     
        ...     async def execute(self, context: PipelineContext) -> StageResult:
        ...         # Process document
        ...         return StageResult.success(output=data)
    """
    
    def __init__(self, name: Optional[str] = None):
        self._name = name
    
    @property
    def name(self) -> str:
        """Get the stage name."""
        return self._name or self.__class__.__name__
    
    @abstractmethod
    async def execute(self, context: PipelineContext) -> StageResult:
        """
        Execute the pipeline stage.
        
        Args:
            context: Pipeline context containing document and data
            
        Returns:
            StageResult with execution status and output
        """
        pass
    
    def should_execute(self, context: PipelineContext) -> bool:
        """
        Determine if this stage should be executed.
        
        Override this method to implement conditional execution.
        
        Args:
            context: Pipeline context
            
        Returns:
            True if stage should execute, False otherwise
        """
        return True
    
    async def cleanup(self, context: PipelineContext) -> None:
        """
        Cleanup resources after stage execution.
        
        Override this method to implement resource cleanup.
        
        Args:
            context: Pipeline context
        """
        pass
    
    def __repr__(self) -> str:
        return f"PipelineStage(name={self.name})"


class Pipeline:
    """
    Document processing pipeline.
    
    A pipeline consists of multiple stages that are executed in sequence.
    Each stage can modify the context and pass data to subsequent stages.
    
    Attributes:
        name: Pipeline name
        stages: List of pipeline stages
        continue_on_error: Whether to continue on stage failure
        
    Example:
        >>> pipeline = Pipeline("my_pipeline")
        >>> pipeline.add_stage(ValidationStage())
        >>> pipeline.add_stage(ParsingStage())
        >>> pipeline.add_stage(ExtractionStage())
        >>> result = await pipeline.execute(document)
    """
    
    def __init__(
        self,
        name: str = "default",
        continue_on_error: bool = False,
    ):
        self.name = name
        self.stages: List[PipelineStage] = []
        self.continue_on_error = continue_on_error
        self._stage_map: Dict[str, PipelineStage] = {}
    
    def add_stage(self, stage: PipelineStage) -> Pipeline:
        """
        Add a stage to the pipeline.
        
        Args:
            stage: Pipeline stage to add
            
        Returns:
            Self for method chaining
        """
        self.stages.append(stage)
        self._stage_map[stage.name] = stage
        return self
    
    def add_stages(self, *stages: PipelineStage) -> Pipeline:
        """
        Add multiple stages to the pipeline.
        
        Args:
            *stages: Pipeline stages to add
            
        Returns:
            Self for method chaining
        """
        for stage in stages:
            self.add_stage(stage)
        return self
    
    def insert_stage(self, index: int, stage: PipelineStage) -> Pipeline:
        """
        Insert a stage at a specific position.
        
        Args:
            index: Position to insert at
            stage: Pipeline stage to insert
            
        Returns:
            Self for method chaining
        """
        self.stages.insert(index, stage)
        self._stage_map[stage.name] = stage
        return self
    
    def remove_stage(self, name: str) -> bool:
        """
        Remove a stage by name.
        
        Args:
            name: Name of stage to remove
            
        Returns:
            True if stage was removed, False otherwise
        """
        if name in self._stage_map:
            stage = self._stage_map.pop(name)
            self.stages.remove(stage)
            return True
        return False
    
    def get_stage(self, name: str) -> Optional[PipelineStage]:
        """Get a stage by name."""
        return self._stage_map.get(name)
    
    async def execute(self, document: BaseDocument) -> PipelineResult:
        """
        Execute the pipeline on a document.
        
        Args:
            document: Document to process
            
        Returns:
            PipelineResult with execution results
        """
        import time
        
        start_time = time.time()
        context = PipelineContext(document=document)
        stage_results: Dict[str, StageResult] = {}
        
        logger.info(f"Starting pipeline '{self.name}' with {len(self.stages)} stages")
        
        for stage in self.stages:
            # Check if stage should execute
            if not stage.should_execute(context):
                logger.debug(f"Skipping stage '{stage.name}'")
                stage_results[stage.name] = StageResult.skipped("condition not met")
                continue
            
            # Execute stage
            logger.debug(f"Executing stage '{stage.name}'")
            stage_start = time.time()
            
            try:
                result = await stage.execute(context)
                result.execution_time_ms = (time.time() - stage_start) * 1000
                stage_results[stage.name] = result
                
                # Store result in context
                context.set_stage_result(stage.name, result.output)
                
                # Handle failure
                if result.status == StageStatus.FAILED:
                    logger.error(f"Stage '{stage.name}' failed: {result.error}")
                    if not self.continue_on_error:
                        break
                
            except Exception as e:
                logger.exception(f"Stage '{stage.name}' execution error: {e}")
                result = StageResult.failure(e)
                result.execution_time_ms = (time.time() - stage_start) * 1000
                stage_results[stage.name] = result
                
                if not self.continue_on_error:
                    break
            
            finally:
                # Cleanup
                try:
                    await stage.cleanup(context)
                except Exception as e:
                    logger.warning(f"Stage '{stage.name}' cleanup error: {e}")
        
        total_time_ms = (time.time() - start_time) * 1000
        success = all(
            r.status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
            for r in stage_results.values()
        )
        
        logger.info(
            f"Pipeline '{self.name}' completed in {total_time_ms:.2f}ms "
            f"(success={success})"
        )
        
        return PipelineResult(
            success=success,
            context=context,
            stage_results=stage_results,
            total_time_ms=total_time_ms,
        )
    
    async def execute_parallel(
        self,
        documents: List[BaseDocument],
        max_concurrency: int = 5,
    ) -> List[PipelineResult]:
        """
        Execute the pipeline on multiple documents in parallel.
        
        Args:
            documents: List of documents to process
            max_concurrency: Maximum number of concurrent executions
            
        Returns:
            List of PipelineResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def process_with_limit(doc: BaseDocument) -> PipelineResult:
            async with semaphore:
                return await self.execute(doc)
        
        tasks = [process_with_limit(doc) for doc in documents]
        return await asyncio.gather(*tasks)
    
    def __repr__(self) -> str:
        return f"Pipeline(name={self.name}, stages={len(self.stages)})"


# Built-in pipeline stages

class ValidationStage(PipelineStage):
    """Pipeline stage for document validation."""
    
    def __init__(self, validators: Optional[List[Callable]] = None):
        super().__init__("validation")
        self.validators = validators or []
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """Validate the document."""
        document = context.document
        errors = []
        
        # Basic validation
        if document.format.value == "unknown":
            errors.append("Unknown document format")
        
        # Run custom validators
        for validator in self.validators:
            try:
                result = validator(document)
                if hasattr(result, 'is_valid') and not result.is_valid:
                    errors.extend(getattr(result, 'errors', []))
            except Exception as e:
                errors.append(f"Validator error: {e}")
        
        if errors:
            return StageResult.failure(
                ValueError(f"Validation failed: {'; '.join(errors)}")
            )
        
        return StageResult.success(metadata={"validators_run": len(self.validators)})


class ParsingStage(PipelineStage):
    """Pipeline stage for document parsing."""
    
    def __init__(self, parser: Optional[Callable] = None):
        super().__init__("parsing")
        self.parser = parser
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """Parse the document."""
        document = context.document
        
        if self.parser:
            try:
                content = await asyncio.get_event_loop().run_in_executor(
                    None, self.parser, document
                )
                context.set("parsed_content", content)
                return StageResult.success(output=content)
            except Exception as e:
                return StageResult.failure(e)
        
        # If document already has extracted content
        if document.extracted_content:
            return StageResult.success(output=document.extracted_content)
        
        return StageResult.skipped("No parser available")


class TransformationStage(PipelineStage):
    """Pipeline stage for content transformation."""
    
    def __init__(
        self,
        transformations: Optional[List[Callable]] = None,
        name: str = "transformation",
    ):
        super().__init__(name)
        self.transformations = transformations or []
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """Apply transformations to the content."""
        content = context.get("parsed_content") or context.document.extracted_content
        
        if not content:
            return StageResult.skipped("No content to transform")
        
        try:
            for transform in self.transformations:
                content = await asyncio.get_event_loop().run_in_executor(
                    None, transform, content
                )
            
            context.set("transformed_content", content)
            return StageResult.success(
                output=content,
                metadata={"transformations_applied": len(self.transformations)}
            )
        except Exception as e:
            return StageResult.failure(e)


class OutputStage(PipelineStage):
    """Pipeline stage for generating output."""
    
    def __init__(
        self,
        output_format: str = "json",
        include_metadata: bool = True,
    ):
        super().__init__("output")
        self.output_format = output_format
        self.include_metadata = include_metadata
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """Generate output from processed content."""
        content = (
            context.get("transformed_content") or
            context.get("parsed_content") or
            context.document.extracted_content
        )
        
        if not content:
            return StageResult.failure(ValueError("No content available for output"))
        
        output = {
            "format": self.output_format,
            "content": content.to_dict() if hasattr(content, 'to_dict') else content,
        }
        
        if self.include_metadata:
            output["metadata"] = context.document.metadata.to_dict()
        
        return StageResult.success(output=output)
