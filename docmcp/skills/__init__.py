"""
Skills plugin system for DocMCP.

This module provides a flexible plugin system for extending document
processing capabilities through Skills - modular, reusable processing units.

Features:
    - Dynamic skill loading and unloading
    - Skill versioning and dependency management
    - Secure sandboxed execution
    - Skill composition and chaining
    - Hot-reloading for development

Example:
    >>> from docmcp.skills import SkillRegistry, BaseSkill
    >>> 
    >>> # Register a custom skill
    >>> @skill_registry.register
    >>> class MySkill(BaseSkill):
    ...     name = "my_skill"
    ...     version = "1.0.0"
    ...     
    ...     async def execute(self, input_data, context):
    ...         return {"result": "processed"}
    >>> 
    >>> # Execute skill
    >>> result = await skill_registry.execute("my_skill", input_data)
"""

from __future__ import annotations

from docmcp.skills.base import (
    BaseSkill,
    SkillContext,
    SkillResult,
    SkillStatus,
    SkillMetadata,
)
from docmcp.skills.registry import (
    SkillRegistry,
    skill_registry,
)
from docmcp.skills.loader import (
    SkillLoader,
    PluginManager,
)
from docmcp.skills.sandbox import (
    SandboxExecutor,
    ResourceLimiter,
)

__all__ = [
    # Base classes
    "BaseSkill",
    "SkillContext",
    "SkillResult",
    "SkillStatus",
    "SkillMetadata",
    # Registry
    "SkillRegistry",
    "skill_registry",
    # Loader
    "SkillLoader",
    "PluginManager",
    # Sandbox
    "SandboxExecutor",
    "ResourceLimiter",
]
