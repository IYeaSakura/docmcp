"""
Skill registry for managing and executing skills.

This module provides the SkillRegistry class for registering, discovering,
and executing skills in a centralized manner.

Features:
    - Centralized skill registration
    - Skill discovery and search
    - Dependency resolution
    - Version management
    - Execution with automatic dependency injection
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Type, Callable, TypeVar
from collections import defaultdict

from docmcp.skills.base import (
    BaseSkill,
    SkillContext,
    SkillResult,
    SkillStatus,
    SkillMetadata,
)
from docmcp.core.document import BaseDocument, DocumentFormat

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseSkill)


@dataclass
class RegisteredSkill:
    """Information about a registered skill."""
    
    skill_class: Type[BaseSkill]
    instance: Optional[BaseSkill] = None
    metadata: SkillMetadata = field(default_factory=lambda: SkillMetadata(name=""))
    registered_at: float = field(default_factory=time.time)
    execution_count: int = 0
    total_execution_time_ms: float = 0.0
    error_count: int = 0
    
    @property
    def average_execution_time_ms(self) -> float:
        """Average execution time."""
        if self.execution_count == 0:
            return 0.0
        return self.total_execution_time_ms / self.execution_count
    
    def get_or_create_instance(self, config: Optional[Dict] = None) -> BaseSkill:
        """Get existing instance or create new one."""
        if self.instance is None:
            self.instance = self.skill_class(config)
        return self.instance


class SkillRegistry:
    """
    Central registry for skills.
    
    The SkillRegistry provides a centralized way to manage skills,
    including registration, discovery, and execution.
    
    Features:
        - Register skills by class or decorator
        - Discover skills by name, tag, or format
        - Execute skills with automatic dependency resolution
        - Track skill usage metrics
    
    Example:
        >>> registry = SkillRegistry()
        >>> 
        >>> # Register a skill class
        >>> registry.register(MySkill)
        >>> 
        >>> # Register with decorator
        >>> @registry.register
        >>> class AnotherSkill(BaseSkill):
        ...     pass
        >>> 
        >>> # Execute a skill
        >>> result = await registry.execute("my_skill", input_data, context)
        >>> 
        >>> # Find skills by format
        >>> pdf_skills = registry.find_by_format(DocumentFormat.PDF)
    """
    
    def __init__(self):
        self._skills: Dict[str, RegisteredSkill] = {}
        self._tags: Dict[str, Set[str]] = defaultdict(set)
        self._formats: Dict[DocumentFormat, Set[str]] = defaultdict(set)
        self._initialized: Set[str] = set()
        self._lock = asyncio.Lock()
    
    def register(
        self,
        skill_class: Type[T],
        name: Optional[str] = None,
    ) -> Type[T]:
        """
        Register a skill class.
        
        Can be used as a decorator or function call.
        
        Args:
            skill_class: Skill class to register
            name: Optional custom name (defaults to skill_class.name)
            
        Returns:
            The registered skill class (for decorator use)
            
        Example:
            >>> # As decorator
            >>> @registry.register
            >>> class MySkill(BaseSkill):
            ...     name = "my_skill"
            >>> 
            >>> # As function
            >>> registry.register(MySkill)
        """
        skill_name = name or skill_class.name or skill_class.__name__
        
        if not skill_name:
            raise ValueError("Skill must have a name")
        
        if skill_name in self._skills:
            logger.warning(f"Overwriting existing skill: {skill_name}")
        
        # Create temporary instance to get metadata
        temp_instance = skill_class()
        metadata = temp_instance.metadata
        
        # Register skill
        self._skills[skill_name] = RegisteredSkill(
            skill_class=skill_class,
            metadata=metadata,
        )
        
        # Index by tags
        for tag in metadata.tags:
            self._tags[tag].add(skill_name)
        
        # Index by formats
        for fmt in metadata.supported_formats:
            self._formats[fmt].add(skill_name)
        
        logger.info(f"Registered skill: {skill_name}@{metadata.version}")
        return skill_class
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a skill.
        
        Args:
            name: Name of skill to unregister
            
        Returns:
            True if skill was unregistered, False if not found
        """
        if name not in self._skills:
            return False
        
        skill_info = self._skills.pop(name)
        
        # Remove from tags index
        for tag in skill_info.metadata.tags:
            self._tags[tag].discard(name)
        
        # Remove from formats index
        for fmt in skill_info.metadata.supported_formats:
            self._formats[fmt].discard(name)
        
        # Remove from initialized set
        self._initialized.discard(name)
        
        logger.info(f"Unregistered skill: {name}")
        return True
    
    def get(self, name: str) -> Optional[RegisteredSkill]:
        """
        Get a registered skill by name.
        
        Args:
            name: Skill name
            
        Returns:
            RegisteredSkill or None if not found
        """
        return self._skills.get(name)
    
    def get_instance(self, name: str, config: Optional[Dict] = None) -> Optional[BaseSkill]:
        """
        Get a skill instance by name.
        
        Args:
            name: Skill name
            config: Optional configuration for skill
            
        Returns:
            Skill instance or None if not found
        """
        skill_info = self._skills.get(name)
        if skill_info is None:
            return None
        return skill_info.get_or_create_instance(config)
    
    def list_skills(self) -> List[str]:
        """Get list of all registered skill names."""
        return list(self._skills.keys())
    
    def get_all_skills(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered skills."""
        return {
            name: {
                "metadata": info.metadata.to_dict(),
                "registered_at": info.registered_at,
                "execution_count": info.execution_count,
                "average_execution_time_ms": info.average_execution_time_ms,
                "error_count": info.error_count,
            }
            for name, info in self._skills.items()
        }
    
    def find_by_tag(self, tag: str) -> List[str]:
        """
        Find skills by tag.
        
        Args:
            tag: Tag to search for
            
        Returns:
            List of skill names with the tag
        """
        return list(self._tags.get(tag, set()))
    
    def find_by_format(self, fmt: DocumentFormat) -> List[str]:
        """
        Find skills that support a document format.
        
        Args:
            fmt: Document format
            
        Returns:
            List of skill names supporting the format
        """
        return list(self._formats.get(fmt, set()))
    
    def find_by_document(self, document: BaseDocument) -> List[str]:
        """
        Find skills that can process a document.
        
        Args:
            document: Document to process
            
        Returns:
            List of skill names that can process the document
        """
        return self.find_by_format(document.format)
    
    def search(self, query: str) -> List[str]:
        """
        Search skills by name, description, or tags.
        
        Args:
            query: Search query
            
        Returns:
            List of matching skill names
        """
        query = query.lower()
        results = []
        
        for name, info in self._skills.items():
            # Search in name
            if query in name.lower():
                results.append(name)
                continue
            
            # Search in description
            if query in info.metadata.description.lower():
                results.append(name)
                continue
            
            # Search in tags
            for tag in info.metadata.tags:
                if query in tag.lower():
                    results.append(name)
                    break
        
        return results
    
    async def initialize_skill(self, name: str, config: Optional[Dict] = None) -> bool:
        """
        Initialize a skill.
        
        Args:
            name: Skill name
            config: Optional configuration
            
        Returns:
            True if initialized successfully
        """
        async with self._lock:
            if name in self._initialized:
                return True
            
            skill_info = self._skills.get(name)
            if skill_info is None:
                logger.error(f"Skill not found: {name}")
                return False
            
            try:
                instance = skill_info.get_or_create_instance(config)
                await instance.initialize()
                self._initialized.add(name)
                logger.info(f"Initialized skill: {name}")
                return True
            except Exception as e:
                logger.exception(f"Failed to initialize skill {name}: {e}")
                return False
    
    async def initialize_all(self, config: Optional[Dict[str, Dict]] = None) -> Dict[str, bool]:
        """
        Initialize all registered skills.
        
        Args:
            config: Optional configuration map for skills
            
        Returns:
            Dictionary of skill names to initialization results
        """
        results = {}
        for name in self._skills:
            skill_config = config.get(name) if config else None
            results[name] = await self.initialize_skill(name, skill_config)
        return results
    
    async def shutdown_skill(self, name: str) -> bool:
        """
        Shutdown a skill.
        
        Args:
            name: Skill name
            
        Returns:
            True if shutdown successfully
        """
        async with self._lock:
            skill_info = self._skills.get(name)
            if skill_info is None or skill_info.instance is None:
                return False
            
            try:
                await skill_info.instance.shutdown()
                skill_info.instance = None
                self._initialized.discard(name)
                logger.info(f"Shutdown skill: {name}")
                return True
            except Exception as e:
                logger.exception(f"Failed to shutdown skill {name}: {e}")
                return False
    
    async def shutdown_all(self) -> Dict[str, bool]:
        """
        Shutdown all initialized skills.
        
        Returns:
            Dictionary of skill names to shutdown results
        """
        results = {}
        for name in list(self._initialized):
            results[name] = await self.shutdown_skill(name)
        return results
    
    async def execute(
        self,
        name: str,
        input_data: Any,
        context: Optional[SkillContext] = None,
        config: Optional[Dict] = None,
        timeout: Optional[float] = None,
    ) -> SkillResult:
        """
        Execute a skill by name.
        
        Args:
            name: Skill name
            input_data: Input data for the skill
            context: Optional execution context
            config: Optional skill configuration
            timeout: Optional execution timeout
            
        Returns:
            SkillResult with execution result
            
        Example:
            >>> result = await registry.execute(
            ...     "text_extraction",
            ...     document,
            ...     context=SkillContext(document=document)
            ... )
        """
        start_time = time.time()
        
        # Get skill
        skill_info = self._skills.get(name)
        if skill_info is None:
            return SkillResult.failure(
                error=f"Skill not found: {name}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        
        # Initialize if needed
        if name not in self._initialized:
            success = await self.initialize_skill(name, config)
            if not success:
                return SkillResult.failure(
                    error=f"Failed to initialize skill: {name}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        
        # Get instance
        instance = skill_info.get_or_create_instance(config)
        
        # Create context if not provided
        if context is None:
            context = SkillContext()
        
        # Validate
        if not await instance.validate(context):
            return SkillResult.failure(
                error=f"Skill '{name}' validation failed",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        
        # Execute with timeout
        try:
            exec_timeout = timeout or 60.0
            result = await asyncio.wait_for(
                instance.execute(input_data, context),
                timeout=exec_timeout,
            )
            
            # Update metrics
            elapsed_ms = (time.time() - start_time) * 1000
            skill_info.execution_count += 1
            skill_info.total_execution_time_ms += elapsed_ms
            
            if result.is_failure:
                skill_info.error_count += 1
            
            return result
            
        except asyncio.TimeoutError:
            skill_info.error_count += 1
            elapsed_ms = (time.time() - start_time) * 1000
            return SkillResult.timeout(
                timeout_seconds=exec_timeout,
                execution_time_ms=elapsed_ms,
            )
            
        except Exception as e:
            skill_info.error_count += 1
            elapsed_ms = (time.time() - start_time) * 1000
            logger.exception(f"Skill execution error for {name}: {e}")
            return SkillResult.failure(
                error=str(e),
                error_details={"exception_type": type(e).__name__},
                execution_time_ms=elapsed_ms,
            )
    
    async def execute_pipeline(
        self,
        skill_names: List[str],
        input_data: Any,
        context: Optional[SkillContext] = None,
        stop_on_error: bool = True,
    ) -> List[SkillResult]:
        """
        Execute multiple skills in a pipeline.
        
        Args:
            skill_names: List of skill names to execute
            input_data: Initial input data
            context: Optional execution context
            stop_on_error: Whether to stop on first error
            
        Returns:
            List of skill results
        """
        results = []
        current_data = input_data
        
        for name in skill_names:
            result = await self.execute(name, current_data, context)
            results.append(result)
            
            if result.is_failure and stop_on_error:
                break
            
            current_data = result.data
        
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get registry metrics."""
        total_executions = sum(s.execution_count for s in self._skills.values())
        total_errors = sum(s.error_count for s in self._skills.values())
        
        return {
            "registered_skills": len(self._skills),
            "initialized_skills": len(self._initialized),
            "total_executions": total_executions,
            "total_errors": total_errors,
            "error_rate": total_errors / total_executions if total_executions > 0 else 0,
            "skills": {
                name: {
                    "execution_count": info.execution_count,
                    "error_count": info.error_count,
                    "average_execution_time_ms": info.average_execution_time_ms,
                }
                for name, info in self._skills.items()
            },
        }


# Global registry instance
skill_registry = SkillRegistry()


def register_skill(
    skill_class: Optional[Type[T]] = None,
    *,
    name: Optional[str] = None,
) -> Callable:
    """
    Decorator or function to register a skill with the global registry.
    
    Args:
        skill_class: Skill class to register
        name: Optional custom name
        
    Returns:
        Decorator function or registered class
        
    Example:
        >>> @register_skill
        >>> class MySkill(BaseSkill):
        ...     pass
        >>> 
        >>> # Or as function
        >>> register_skill(MySkill)
    """
    def decorator(cls: Type[T]) -> Type[T]:
        return skill_registry.register(cls, name)
    
    if skill_class is not None:
        return decorator(skill_class)
    
    return decorator


def get_skill(name: str) -> Optional[BaseSkill]:
    """Get a skill instance from the global registry."""
    return skill_registry.get_instance(name)


async def execute_skill(
    name: str,
    input_data: Any,
    context: Optional[SkillContext] = None,
    **kwargs,
) -> SkillResult:
    """Execute a skill from the global registry."""
    return await skill_registry.execute(name, input_data, context, **kwargs)
