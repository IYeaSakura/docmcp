"""
Processing engine module for DocMCP.

This module provides the core processing engine that orchestrates document
processing tasks with support for:
    - Asynchronous processing with asyncio
    - Concurrent task execution with worker pools
    - Pipeline-based processing stages
    - Error handling and retry mechanisms
    - Progress tracking and monitoring

The engine is designed for high throughput and reliability, with built-in
support for task queuing, prioritization, and resource management.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Generic
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

from docmcp.core.document import BaseDocument, DocumentFormat, DocumentContent

# Configure logging
logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Status of a document processing task."""

    PENDING = auto()      # Task is queued and waiting
    VALIDATING = auto()   # Validating document format and content
    PARSING = auto()      # Parsing document structure
    PROCESSING = auto()   # Applying processing logic
    COMPLETED = auto()    # Processing completed successfully
    FAILED = auto()       # Processing failed
    CANCELLED = auto()    # Task was cancelled
    TIMEOUT = auto()      # Task exceeded time limit


class ValidationStatus(Enum):
    """Validation result status."""

    VALID = auto()        # Document is valid
    INVALID = auto()      # Document is invalid
    SUSPICIOUS = auto()   # Document may be suspicious (e.g., contains macros)
    UNKNOWN = auto()      # Validation could not determine status


@dataclass
class ValidationResult:
    """Result of document validation."""

    status: ValidationStatus
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def valid(cls, **metadata) -> ValidationResult:
        """Create a valid validation result."""
        return cls(
            status=ValidationStatus.VALID,
            is_valid=True,
            metadata=metadata
        )

    @classmethod
    def invalid(cls, errors: List[str], **metadata) -> ValidationResult:
        """Create an invalid validation result."""
        return cls(
            status=ValidationStatus.INVALID,
            is_valid=False,
            errors=errors,
            metadata=metadata
        )


@dataclass
class ProcessingContext:
    """
    Context for document processing.

    This class holds all contextual information needed during processing,
    including configuration, user information, and processing options.

    Attributes:
        request_id: Unique request identifier for tracing
        user_id: ID of the user making the request
        tenant_id: ID of the tenant (for multi-tenant deployments)
        options: Processing options and configuration
        priority: Task priority (higher = more important)
        timeout_seconds: Maximum processing time
        max_retries: Maximum number of retry attempts
        retry_count: Current retry count
        metadata: Additional context metadata
    """

    request_id: str = field(default_factory=lambda: f"req_{int(time.time() * 1000)}")
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, higher = more important
    timeout_seconds: float = 300.0  # 5 minutes default
    max_retries: int = 3
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time since processing started."""
        return time.time() - self.start_time

    def should_retry(self) -> bool:
        """Check if the task should be retried."""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1


@dataclass
class ProcessingResult:
    """
    Result of document processing.

    This class encapsulates the outcome of a processing task, including
    the processed document, status, timing information, and any errors.

    Attributes:
        document_id: ID of the processed document
        status: Final processing status
        content: Extracted document content (if successful)
        validation_result: Validation result
        processing_time_ms: Total processing time in milliseconds
        error_message: Error message (if failed)
        error_details: Detailed error information
        context: Processing context
        metadata: Additional result metadata
    """

    document_id: str
    status: ProcessingStatus
    content: Optional[DocumentContent] = None
    validation_result: Optional[ValidationResult] = None
    processing_time_ms: float = 0.0
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    context: Optional[ProcessingContext] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if processing was successful."""
        return self.status == ProcessingStatus.COMPLETED

    @property
    def is_failure(self) -> bool:
        """Check if processing failed."""
        return self.status in (ProcessingStatus.FAILED, ProcessingStatus.TIMEOUT)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "document_id": self.document_id,
            "status": self.status.name,
            "is_success": self.is_success,
            "processing_time_ms": self.processing_time_ms,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


# Type variable for generic result types
T = TypeVar('T')


class ProcessingTask:
    """
    Represents a document processing task.

    This class encapsulates all information about a processing task,
    including the document, context, and result.
    """

    def __init__(
        self,
        document: BaseDocument,
        context: ProcessingContext,
        callback: Optional[Callable[[ProcessingResult], None]] = None,
    ):
        self.id = context.request_id
        self.document = document
        self.context = context
        self.callback = callback
        self.status = ProcessingStatus.PENDING
        self.result: Optional[ProcessingResult] = None
        self._future: Optional[asyncio.Future] = None
        self._created_at = time.time()
        self._started_at: Optional[float] = None
        self._completed_at: Optional[float] = None

    @property
    def wait_time(self) -> float:
        """Time spent waiting in queue."""
        if self._started_at:
            return self._started_at - self._created_at
        return time.time() - self._created_at

    @property
    def processing_time(self) -> float:
        """Time spent processing."""
        if self._started_at and self._completed_at:
            return self._completed_at - self._started_at
        return 0.0

    def start(self) -> None:
        """Mark task as started."""
        self._started_at = time.time()
        self.status = ProcessingStatus.PROCESSING

    def complete(self, result: ProcessingResult) -> None:
        """Mark task as completed."""
        self._completed_at = time.time()
        self.result = result
        self.status = result.status

        if self.callback:
            try:
                self.callback(result)
            except Exception as e:
                logger.error(f"Callback error for task {self.id}: {e}")


class ProcessingEngine:
    """
    High-performance document processing engine.

    This engine provides asynchronous document processing with support for:
        - Concurrent task execution
        - Priority-based task scheduling
        - Automatic retry on failure
        - Timeout handling
        - Progress monitoring
        - Resource management

    Attributes:
        max_workers: Maximum number of concurrent workers
        max_queue_size: Maximum task queue size
        enable_retry: Whether to enable automatic retry
        enable_metrics: Whether to collect metrics

    Example:
        >>> engine = ProcessingEngine(max_workers=10)
        >>> await engine.start()
        >>> result = await engine.process(document, context)
        >>> await engine.stop()
    """

    def __init__(
        self,
        max_workers: int = 4,
        max_queue_size: int = 1000,
        enable_retry: bool = True,
        enable_metrics: bool = True,
    ):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.enable_retry = enable_retry
        self.enable_metrics = enable_metrics

        # Task queue (priority queue)
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=max_queue_size
        )

        # Worker management
        self._workers: List[asyncio.Task] = []
        self._executor: Optional[ThreadPoolExecutor] = None

        # State
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Metrics
        self._metrics = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "total_processing_time_ms": 0.0,
        }

        # Adapters registry
        self._adapters: Dict[DocumentFormat, Any] = {}

        # Validators registry
        self._validators: List[Callable[[BaseDocument], ValidationResult]] = []

        logger.info(f"ProcessingEngine initialized (max_workers={max_workers})")

    async def start(self) -> None:
        """Start the processing engine."""
        if self._running:
            logger.warning("Engine is already running")
            return

        self._running = True
        self._shutdown_event.clear()
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(
                self._worker_loop(f"worker-{i}"),
                name=f"docmcp-worker-{i}"
            )
            self._workers.append(worker)

        logger.info(f"ProcessingEngine started with {self.max_workers} workers")

    async def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the processing engine gracefully.

        Args:
            timeout: Maximum time to wait for pending tasks
        """
        if not self._running:
            return

        logger.info("Stopping ProcessingEngine...")
        self._running = False
        self._shutdown_event.set()

        # Cancel all workers
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=True)

        self._workers.clear()
        logger.info("ProcessingEngine stopped")

    async def _worker_loop(self, worker_id: str) -> None:
        """
        Main worker loop that processes tasks from the queue.

        Args:
            worker_id: Unique identifier for this worker
        """
        logger.debug(f"Worker {worker_id} started")

        while self._running:
            try:
                # Wait for task with timeout
                priority, task = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )

                await self._process_task(task)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.debug(f"Worker {worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

        logger.debug(f"Worker {worker_id} stopped")

    async def _process_task(self, task: ProcessingTask) -> None:
        """
        Process a single task.

        Args:
            task: The processing task to execute
        """
        task.start()
        start_time = time.time()

        try:
            # Validate document
            task.status = ProcessingStatus.VALIDATING
            validation_result = await self._validate_document(task.document)

            if not validation_result.is_valid:
                result = ProcessingResult(
                    document_id=task.document.id,
                    status=ProcessingStatus.FAILED,
                    validation_result=validation_result,
                    error_message="Document validation failed",
                    error_details={"errors": validation_result.errors},
                    context=task.context,
                )
                task.complete(result)
                return

            # Parse and process document
            task.status = ProcessingStatus.PARSING
            content = await self._parse_document(task.document)

            # Create result
            processing_time_ms = (time.time() - start_time) * 1000
            result = ProcessingResult(
                document_id=task.document.id,
                status=ProcessingStatus.COMPLETED,
                content=content,
                validation_result=validation_result,
                processing_time_ms=processing_time_ms,
                context=task.context,
            )

            # Update metrics
            if self.enable_metrics:
                self._metrics["tasks_completed"] += 1
                self._metrics["total_processing_time_ms"] += processing_time_ms

            task.complete(result)

        except asyncio.TimeoutError:
            processing_time_ms = (time.time() - start_time) * 1000
            result = ProcessingResult(
                document_id=task.document.id,
                status=ProcessingStatus.TIMEOUT,
                processing_time_ms=processing_time_ms,
                error_message=f"Processing timed out after {task.context.timeout_seconds}s",
                context=task.context,
            )
            task.complete(result)

            if self.enable_metrics:
                self._metrics["tasks_failed"] += 1

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            logger.exception(f"Task {task.id} processing error: {e}")

            # Check if should retry
            if self.enable_retry and task.context.should_retry():
                task.context.increment_retry()
                if self.enable_metrics:
                    self._metrics["tasks_retried"] += 1

                # Re-queue with lower priority
                await self._submit_task(task, priority=task.context.priority - 1)
                return

            result = ProcessingResult(
                document_id=task.document.id,
                status=ProcessingStatus.FAILED,
                processing_time_ms=processing_time_ms,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                context=task.context,
            )
            task.complete(result)

            if self.enable_metrics:
                self._metrics["tasks_failed"] += 1

    async def _validate_document(self, document: BaseDocument) -> ValidationResult:
        """
        Validate a document.

        Args:
            document: Document to validate

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # Check format
        if document.format == DocumentFormat.UNKNOWN:
            errors.append("Unknown document format")

        # Check content
        if document.content is None:
            errors.append("Document content is empty")

        # Run registered validators
        for validator in self._validators:
            try:
                result = validator(document)
                if not result.is_valid:
                    errors.extend(result.errors)
                warnings.extend(result.warnings)
            except Exception as e:
                logger.warning(f"Validator error: {e}")

        if errors:
            return ValidationResult.invalid(errors)

        return ValidationResult.valid(warnings=warnings)

    async def _parse_document(self, document: BaseDocument) -> DocumentContent:
        """
        Parse a document and extract content.

        Args:
            document: Document to parse

        Returns:
            Extracted DocumentContent

        Raises:
            NotImplementedError: If no adapter is available for the format
        """
        adapter = self._adapters.get(document.format)

        if adapter is None:
            raise NotImplementedError(
                f"No adapter available for format: {document.format}"
            )

        # Run adapter in thread pool for blocking operations
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(
            self._executor,
            adapter.parse,
            document
        )

        return content

    async def _submit_task(
        self,
        task: ProcessingTask,
        priority: Optional[int] = None,
    ) -> None:
        """
        Submit a task to the processing queue.

        Args:
            task: Task to submit
            priority: Task priority (uses context priority if not specified)
        """
        priority = priority or task.context.priority
        # Negate priority for min-heap behavior (higher priority = lower number)
        await self._task_queue.put((-priority, task))

    async def process(
        self,
        document: BaseDocument,
        context: Optional[ProcessingContext] = None,
        callback: Optional[Callable[[ProcessingResult], None]] = None,
    ) -> ProcessingResult:
        """
        Process a document asynchronously.

        Args:
            document: Document to process
            context: Processing context (created with defaults if not provided)
            callback: Optional callback function for result notification

        Returns:
            ProcessingResult

        Example:
            >>> engine = ProcessingEngine()
            >>> await engine.start()
            >>> result = await engine.process(document)
            >>> print(result.status)
        """
        if not self._running:
            raise RuntimeError("Engine is not running. Call start() first.")

        context = context or ProcessingContext()
        task = ProcessingTask(document, context, callback)

        if self.enable_metrics:
            self._metrics["tasks_submitted"] += 1

        # Create future for async result
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        task._future = future

        # Submit to queue
        await self._submit_task(task)

        # Wait for completion with timeout
        try:
            await asyncio.wait_for(
                future,
                timeout=context.timeout_seconds + 10  # Add buffer
            )
        except asyncio.TimeoutError:
            pass

        # Return result (may be None if timeout)
        if task.result is None:
            return ProcessingResult(
                document_id=document.id,
                status=ProcessingStatus.TIMEOUT,
                error_message="Task did not complete in time",
                context=context,
            )

        return task.result

    def register_adapter(self, format: DocumentFormat, adapter: Any) -> None:
        """
        Register a document adapter for a specific format.

        Args:
            format: Document format
            adapter: Adapter instance with parse() method
        """
        self._adapters[format] = adapter
        logger.info(f"Registered adapter for {format.value}")

    def register_validator(
        self,
        validator: Callable[[BaseDocument], ValidationResult]
    ) -> None:
        """
        Register a document validator.

        Args:
            validator: Validator function
        """
        self._validators.append(validator)
        logger.info(f"Registered validator: {validator.__name__}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get engine metrics."""
        metrics = self._metrics.copy()

        if metrics["tasks_completed"] > 0:
            metrics["average_processing_time_ms"] = (
                metrics["total_processing_time_ms"] / metrics["tasks_completed"]
            )
        else:
            metrics["average_processing_time_ms"] = 0.0

        metrics["queue_size"] = self._task_queue.qsize()
        metrics["is_running"] = self._running

        return metrics

    def __repr__(self) -> str:
        return (
            f"ProcessingEngine("
            f"workers={self.max_workers}, "
            f"running={self._running}, "
            f"queue_size={self._task_queue.qsize()}"
            f")"
        )

    # 测试兼容性方法
    def get_supported_types(self) -> list:
        """获取支持的文档类型列表（用于测试兼容性）"""
        return list(self._adapters.keys())

    def get_supported_extensions(self) -> list:
        """获取支持的文件扩展名列表（用于测试兼容性）"""
        extensions = []
        for fmt in self._adapters.keys():
            extensions.extend(fmt.extensions)
        return extensions

    def can_handle(self, file_path: Union[str, Path]) -> bool:
        """检查是否能处理指定文件（用于测试兼容性）"""
        ext = Path(file_path).suffix.lower()
        return ext in self.get_supported_extensions()

    def get_handler_by_type(self, doc_type: DocumentType) -> Any:
        """根据文档类型获取处理器（用于测试兼容性）"""
        # 将 DocumentType 映射到 DocumentFormat
        from .document import DocumentType as DT
        type_to_format = {
            DT.PDF: DocumentFormat.PDF,
            DT.WORD_PROCESSING: DocumentFormat.DOCX,
            DT.SPREADSHEET: DocumentFormat.XLSX,
            DT.PRESENTATION: DocumentFormat.PPTX,
            DT.TEXT: DocumentFormat.TXT,
        }
        fmt = type_to_format.get(doc_type)
        return self._adapters.get(fmt) if fmt else None


# 全局引擎实例（用于测试兼容性）
_engine_instance: Optional[ProcessingEngine] = None

def get_engine() -> ProcessingEngine:
    """获取全局引擎实例（用于测试兼容性）"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProcessingEngine()
    return _engine_instance

def reset_engine() -> None:
    """重置全局引擎实例（用于测试兼容性）"""
    global _engine_instance
    _engine_instance = None
