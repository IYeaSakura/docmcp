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
    SkillParameter,
    ExecutionMode
)


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
    Skill类装饰器
    
    用于快速定义Skill类和元数据。
    
    Args:
        name: Skill名称，默认为类名
        version: 版本号
        description: 描述
        author: 作者
        category: 分类
        tags: 标签列表
        dependencies: 依赖列表
        execution_mode: 执行模式
        timeout: 超时时间（秒）
        retry_count: 重试次数
        permissions: 权限列表
        
    Returns:
        装饰后的类
        
    示例:
        @skill(
            name="text_extractor",
            description="提取文本内容",
            version="1.0.0"
        )
        class TextExtractorSkill(BaseSkill):
            def execute(self, context, **kwargs):
                # 实现逻辑
                pass
    """
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        # 保存原始__init__
        original_init = cls.__init__
        
        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            # 创建元数据
            metadata = SkillMetadata(
                name=name or cls.__name__.lower().replace("skill", ""),
                version=version,
                description=description or cls.__doc__ or "",
                author=author,
                category=category,
                tags=tags or [],
                dependencies=dependencies or [],
                parameters=getattr(cls, '_skill_parameters', []),
                execution_mode=execution_mode,
                timeout=timeout,
                retry_count=retry_count,
                permissions=permissions or []
            )
            
            # 调用父类__init__
            BaseSkill.__init__(self, metadata=metadata)
            
            # 调用原始__init__
            original_init(self, *args, **kwargs)
        
        cls.__init__ = new_init
        cls._is_skill = True  # 标记为Skill类
        cls._skill_name = name or cls.__name__.lower().replace("skill", "")
        cls._skill_version = version
        cls._skill_description = description or cls.__doc__ or ""
        cls._skill_category = category
        cls._skill_tags = tags or []
        cls._skill_dependencies = dependencies or []
        cls._skill_permissions = permissions or []
        
        return cls
    
    return decorator


def parameter(
    name: str,
    param_type: Type = Any,
    description: str = "",
    required: bool = True,
    default: Any = None,
    choices: Optional[List[Any]] = None
):
    """
    参数装饰器
    
    用于为Skill定义参数。
    
    Args:
        name: 参数名
        param_type: 参数类型
        description: 描述
        required: 是否必需
        default: 默认值
        choices: 可选值列表
        
    Returns:
        装饰器函数
        
    示例:
        @skill(name="my_skill")
        @parameter("input_file", str, "输入文件路径", required=True)
        @parameter("output_format", str, "输出格式", default="txt", choices=["txt", "json"])
        class MySkill(BaseSkill):
            pass
    """
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        # 获取或创建参数列表
        if not hasattr(cls, '_skill_parameters'):
            cls._skill_parameters = []
        
        # 创建参数定义
        param = SkillParameter(
            name=name,
            type=param_type,
            description=description,
            required=required,
            default=default,
            choices=choices
        )
        
        # 检查是否已存在同名参数
        existing = [p for p in cls._skill_parameters if p.name == name]
        if existing:
            cls._skill_parameters.remove(existing[0])
        
        cls._skill_parameters.append(param)
        
        return cls
    
    return decorator


def require(*skill_names: str):
    """
    依赖声明装饰器
    
    声明Skill依赖的其他Skill。
    
    Args:
        *skill_names: 依赖的Skill名称列表
        
    Returns:
        装饰器函数
        
    示例:
        @skill(name="advanced_processor")
        @require("text_extractor", "formatter")
        class AdvancedProcessorSkill(BaseSkill):
            pass
    """
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        if not hasattr(cls, '_skill_dependencies'):
            cls._skill_dependencies = []
        
        cls._skill_dependencies.extend(skill_names)
        
        # 更新元数据中的依赖
        original_init = cls.__init__
        
        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            if hasattr(cls, '_skill_dependencies'):
                self._metadata.dependencies = list(set(
                    self._metadata.dependencies + cls._skill_dependencies
                ))
        
        cls.__init__ = new_init
        
        return cls
    
    return decorator


def async_skill(cls: Type[BaseSkill]) -> Type[BaseSkill]:
    """
    异步Skill装饰器
    
    将Skill标记为异步执行模式。
    
    Args:
        cls: Skill类
        
    Returns:
        装饰后的类
        
    示例:
        @async_skill
        @skill(name="async_processor")
        class AsyncProcessorSkill(BaseSkill):
            async def execute(self, context, **kwargs):
                # 异步实现
                pass
    """
    cls._execution_mode = ExecutionMode.ASYNC
    return cls


def pipeline_skill(*steps: str):
    """
    管道Skill装饰器
    
    将多个Skill组合成管道执行。
    
    Args:
        *steps: 步骤Skill名称列表
        
    Returns:
        装饰器函数
        
    示例:
        @pipeline_skill("extract", "transform", "load")
        @skill(name="etl_pipeline")
        class ETLPipelineSkill(BaseSkill):
            pass
    """
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        cls._pipeline_steps = steps
        cls._execution_mode = ExecutionMode.PIPELINE
        return cls
    
    return decorator


def retry(max_retries: int = 3, exceptions: Optional[tuple] = None):
    """
    重试装饰器
    
    为Skill执行添加重试机制。
    
    Args:
        max_retries: 最大重试次数
        exceptions: 触发重试的异常类型
        
    Returns:
        装饰器函数
        
    示例:
        @skill(name="unstable_skill")
        @retry(max_retries=3, exceptions=(ConnectionError, TimeoutError))
        class UnstableSkill(BaseSkill):
            pass
    """
    exceptions = exceptions or (Exception,)
    
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        original_execute = cls.execute
        
        @wraps(original_execute)
        def execute_with_retry(self, context, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return original_execute(self, context, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries:
                        import time
                        time.sleep(0.5 * (attempt + 1))  # 指数退避
            
            from .base import SkillResult
            return SkillResult.error_result(
                f"执行失败，已重试{max_retries}次: {str(last_error)}"
            )
        
        cls.execute = execute_with_retry
        return cls
    
    return decorator


def timeout(seconds: float):
    """
    超时装饰器
    
    为Skill执行设置超时限制。
    
    Args:
        seconds: 超时时间（秒）
        
    Returns:
        装饰器函数
        
    示例:
        @skill(name="slow_skill")
        @timeout(30.0)
        class SlowSkill(BaseSkill):
            pass
    """
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        cls._timeout = seconds
        return cls
    
    return decorator


def permission(*perms: str):
    """
    权限装饰器
    
    为Skill声明所需权限。
    
    Args:
        *perms: 权限列表
        
    Returns:
        装饰器函数
        
    示例:
        @skill(name="admin_skill")
        @permission("admin", "write")
        class AdminSkill(BaseSkill):
            pass
    """
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        if not hasattr(cls, '_skill_permissions'):
            cls._skill_permissions = []
        
        cls._skill_permissions.extend(perms)
        return cls
    
    return decorator


def tag(*tags: str):
    """
    标签装饰器
    
    为Skill添加标签。
    
    Args:
        *tags: 标签列表
        
    Returns:
        装饰器函数
        
    示例:
        @skill(name="processor")
        @tag("document", "text", "core")
        class ProcessorSkill(BaseSkill):
            pass
    """
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        if not hasattr(cls, '_skill_tags'):
            cls._skill_tags = []
        
        cls._skill_tags.extend(tags)
        return cls
    
    return decorator


def category(cat: str):
    """
    分类装饰器
    
    为Skill设置分类。
    
    Args:
        cat: 分类名称
        
    Returns:
        装饰器函数
        
    示例:
        @skill(name="processor")
        @category("document_processing")
        class ProcessorSkill(BaseSkill):
            pass
    """
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        cls._skill_category = cat
        return cls
    
    return decorator


def version(ver: str):
    """
    版本装饰器
    
    为Skill设置版本号。
    
    Args:
        ver: 版本号
        
    Returns:
        装饰器函数
        
    示例:
        @skill(name="processor")
        @version("2.0.0")
        class ProcessorSkill(BaseSkill):
            pass
    """
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        cls._skill_version = ver
        return cls
    
    return decorator


# 便捷组合装饰器
def simple_skill(
    name: str,
    description: str = "",
    **kwargs
):
    """
    简单Skill装饰器组合
    
    快速创建一个简单的Skill。
    
    Args:
        name: Skill名称
        description: 描述
        **kwargs: 其他参数
        
    Returns:
        装饰后的类
        
    示例:
        @simple_skill("my_processor", "处理文本")
        class MyProcessor(BaseSkill):
            def execute(self, context, text=""):
                return SkillResult.success_result(text.upper())
    """
    def decorator(cls: Type[BaseSkill]) -> Type[BaseSkill]:
        # 应用skill装饰器
        cls = skill(
            name=name,
            description=description,
            **kwargs
        )(cls)
        
        return cls
    
    return decorator


def is_skill_class(cls: Type) -> bool:
    """
    检查类是否为Skill类
    
    Args:
        cls: 要检查的类
        
    Returns:
        是否为Skill类
    """
    return (
        isinstance(cls, type) and
        issubclass(cls, BaseSkill) and
        getattr(cls, '_is_skill', False)
    )


def get_skill_info(cls: Type[BaseSkill]) -> Dict[str, Any]:
    """
    获取Skill类信息
    
    Args:
        cls: Skill类
        
    Returns:
        Skill信息字典
    """
    info = {
        "name": getattr(cls, '_skill_name', cls.__name__),
        "version": getattr(cls, '_skill_version', "1.0.0"),
        "description": cls.__doc__ or "",
        "category": getattr(cls, '_skill_category', "general"),
        "tags": getattr(cls, '_skill_tags', []),
        "dependencies": getattr(cls, '_skill_dependencies', []),
        "permissions": getattr(cls, '_skill_permissions', []),
        "parameters": [
            {
                "name": p.name,
                "type": p.type.__name__ if p.type != Any else "Any",
                "description": p.description,
                "required": p.required,
                "default": p.default
            }
            for p in getattr(cls, '_skill_parameters', [])
        ]
    }
    return info
