"""
Skills插件化系统

一个完整的插件化Skill管理系统，支持动态加载、依赖注入、调度执行等功能。

基本用法:
    from docmcp.skills import (
        BaseSkill, SkillRegistry, SkillLoader,
        SkillScheduler, SkillContext, skill, parameter
    )

    # 定义Skill
    @skill(name="my_skill", description="我的Skill")
    @parameter("input", str, "输入文本", required=True)
    class MySkill(BaseSkill):
        def execute(self, context, **kwargs):
            text = kwargs.get("input")
            return SkillResult.success_result(data=text.upper())

    # 注册并执行
    registry = SkillRegistry()
    registry.register(MySkill)

    context = SkillContext(registry=registry)
    skill_instance = registry.load("my_skill", context)
    result = skill_instance.run(context, input="hello")

    print(result.data)  # HELLO

核心组件:
    - BaseSkill: Skill基类
    - SkillRegistry: 注册中心
    - SkillLoader: 动态加载器
    - SkillScheduler: 调度器
    - SkillContext: 执行上下文
    - decorators: 装饰器模块

内置Skills:
    - extract_text: 文本提取
    - convert_format: 格式转换
    - analyze_document: 文档分析
    - merge_documents: 文档合并
"""

__version__ = "1.0.0"
__author__ = "DocMCP Team"

# 基础类和枚举
from .base import (
    BaseSkill,
    SkillMetadata,
    SkillParameter,
    SkillResult,
    SkillStatus,
    ExecutionMode,
    SkillError,
    SkillNotFoundError,
    SkillDependencyError,
    SkillExecutionError,
    SkillConfigurationError,
)

# 装饰器
from .decorators import (
    skill,
    parameter,
    require,
    async_skill,
    pipeline_skill,
    retry,
    timeout,
    permission,
    tag,
    category,
    version,
    simple_skill,
    is_skill_class,
    get_skill_info,
)

# 上下文
from .context import (
    SkillContext,
    ContextManager,
)

# 注册中心
from .registry import (
    SkillRegistry,
    RegisteredSkill,
    get_default_registry,
    set_default_registry,
)

# 加载器
from .loader import (
    SkillLoader,
    SkillImporter,
    ModuleInfo,
)

# 调度器
from .scheduler import (
    SkillScheduler,
    TaskInfo,
    TaskStatus,
    Task,
    ExecutionPlan,
)

# 内置Skills
from .builtins import (
    ExtractTextSkill,
    ConvertFormatSkill,
    AnalyzeDocumentSkill,
    MergeDocumentsSkill,
)

__all__ = [
    # 版本信息
    "__version__",
    "__author__",

    # 基础类
    "BaseSkill",
    "SkillMetadata",
    "SkillParameter",
    "SkillResult",
    "SkillStatus",
    "ExecutionMode",
    "ExecutionContext",

    # 异常
    "SkillError",
    "SkillNotFoundError",
    "SkillDependencyError",
    "SkillExecutionError",
    "SkillConfigurationError",

    # 装饰器
    "skill",
    "parameter",
    "require",
    "async_skill",
    "pipeline_skill",
    "retry",
    "timeout",
    "permission",
    "tag",
    "category",
    "version",
    "simple_skill",
    "is_skill_class",
    "get_skill_info",

    # 上下文
    "SkillContext",
    "ContextManager",

    # 注册中心
    "SkillRegistry",
    "RegisteredSkill",
    "get_default_registry",
    "set_default_registry",

    # 加载器
    "SkillLoader",
    "SkillImporter",
    "ModuleInfo",

    # 调度器
    "SkillScheduler",
    "TaskInfo",
    "TaskStatus",
    "Task",
    "ExecutionPlan",

    # 内置Skills
    "ExtractTextSkill",
    "ConvertFormatSkill",
    "AnalyzeDocumentSkill",
    "MergeDocumentsSkill",
]


def create_skill_system(
    config: dict = None,
    auto_discover: bool = True,
    hot_reload: bool = False
) -> tuple:
    """
    创建完整的Skill系统

    Args:
        config: 配置字典
        auto_discover: 是否自动发现内置Skills
        hot_reload: 是否启用热更新

    Returns:
        (registry, loader, scheduler, context) 元组
    """
    from .registry import SkillRegistry
    from .loader import SkillLoader
    from .scheduler import SkillScheduler
    from .context import SkillContext

    # 创建组件
    registry = SkillRegistry()
    loader = SkillLoader(registry, hot_reload=hot_reload)
    scheduler = SkillScheduler(registry)
    context = SkillContext(registry=registry, config=config or {})

    # 自动发现内置Skills
    if auto_discover:
        # 注册内置Skills
        from .builtins import (
            ExtractTextSkill,
            ConvertFormatSkill,
            AnalyzeDocumentSkill,
            MergeDocumentsSkill,
        )

        for skill_class in [
            ExtractTextSkill,
            ConvertFormatSkill,
            AnalyzeDocumentSkill,
            MergeDocumentsSkill,
        ]:
            try:
                registry.register(skill_class)
            except Exception:
                pass

    return registry, loader, scheduler, context


def quick_execute(
    skill_name: str,
    params: dict = None,
    registry: "SkillRegistry" = None,
    config: dict = None
) -> "SkillResult":
    """
    快速执行Skill

    Args:
        skill_name: Skill名称
        params: 执行参数
        registry: 注册中心（可选）
        config: 配置（可选）

    Returns:
        执行结果
    """
    if registry is None:
        registry = get_default_registry()

    context = SkillContext(registry=registry, config=config or {})
    skill = registry.require(skill_name)

    return skill.run(context, **(params or {}))
