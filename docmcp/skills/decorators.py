"""
Skills插件化系统 - 装饰器模块

提供用于定义和配置Skill的装饰器。
"""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union
import inspect

from .base import (
    BaseSkill,
    SkillMetadata,
    SkillContext,
    SkillResult,
)


# 定义ExecutionMode
from enum import Enum


class ExecutionMode(Enum):
    """执行模式"""
    SYNC = "sync"
    ASYNC = "async"


class SkillParameter:
    """Skill参数定义"""
    
    def __init__(
        self,
        name: str,
        type: str = "string",
        description: str = "",
        required: bool = True,
        default: Any = None
    ):
        self.name = name
        self.type = type
        self.description = description
        self.required = required
        self.default = default


def skill(
    name: Optional[str] = None,
    version: str = "1.0.0",
    description: str = "",
    author: str = "",
    category: str = "general",
    tags: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    execution_mode: ExecutionMode = ExecutionMode.SYNC,
    timeout: float = 60.0,
    retry_count: int = 0,
    permissions: Optional[List[str]] = None
):
    """
    Skill装饰器
    
    用于将函数标记为Skill。
    
    Args:
        name: Skill名称
        version: 版本号
        description: 描述
        author: 作者
        category: 分类
        tags: 标签列表
        dependencies: 依赖列表
        execution_mode: 执行模式
        timeout: 超时时间
        retry_count: 重试次数
        permissions: 权限列表
    """
    def decorator(func: Callable) -> Callable:
        # 创建Skill元数据
        metadata = SkillMetadata(
            name=name or func.__name__,
            version=version,
            description=description or func.__doc__ or "",
            author=author,
            category=category,
            tags=tags or [],
            dependencies=dependencies or [],
        )
        
        # 将元数据附加到函数
        func._skill_metadata = metadata
        func._skill_execution_mode = execution_mode
        func._skill_timeout = timeout
        func._skill_retry_count = retry_count
        func._skill_permissions = permissions or []
        
        return func
    
    return decorator


def parameter(
    name: str,
    type: str = "string",
    description: str = "",
    required: bool = True,
    default: Any = None
):
    """
    参数装饰器
    
    用于定义Skill的参数。
    
    Args:
        name: 参数名称
        type: 参数类型
        description: 参数描述
        required: 是否必需
        default: 默认值
    """
    def decorator(func: Callable) -> Callable:
        # 获取或创建参数列表
        if not hasattr(func, '_skill_parameters'):
            func._skill_parameters = []
        
        # 添加参数定义
        func._skill_parameters.append(SkillParameter(
            name=name,
            type=type,
            description=description,
            required=required,
            default=default
        ))
        
        return func
    
    return decorator
