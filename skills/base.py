"""
Skills插件化系统 - 基础类和接口定义

提供Skill基类、元数据定义和核心接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union
from datetime import datetime
import uuid
import inspect


class SkillStatus(Enum):
    """Skill状态枚举"""
    UNLOADED = auto()      # 未加载
    LOADING = auto()       # 加载中
    LOADED = auto()        # 已加载
    INITIALIZING = auto()  # 初始化中
    READY = auto()         # 就绪
    RUNNING = auto()       # 运行中
    ERROR = auto()         # 错误状态
    UNLOADING = auto()     # 卸载中


class ExecutionMode(Enum):
    """执行模式枚举"""
    SYNC = auto()          # 同步执行
    ASYNC = auto()         # 异步执行
    PARALLEL = auto()      # 并行执行
    PIPELINE = auto()      # 管道执行


@dataclass
class SkillParameter:
    """Skill参数定义"""
    name: str
    type: Type = Any
    description: str = ""
    required: bool = True
    default: Any = None
    choices: Optional[List[Any]] = None

    def validate(self, value: Any) -> tuple[bool, str]:
        """验证参数值"""
        if value is None:
            if self.required and self.default is None:
                return False, f"参数 '{self.name}' 是必需的"
            value = self.default

        if self.choices and value not in self.choices:
            return False, f"参数 '{self.name}' 必须是以下之一: {self.choices}"

        if value is not None and self.type != Any:
            try:
                # 尝试类型转换
                if not isinstance(value, self.type):
                    self.type(value)
            except (TypeError, ValueError):
                return False, f"参数 '{self.name}' 类型错误，期望 {self.type.__name__}"

        return True, ""


@dataclass
class SkillMetadata:
    """Skill元数据"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    parameters: List[SkillParameter] = field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.SYNC
    timeout: float = 60.0
    retry_count: int = 0
    enabled: bool = True
    permissions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type.__name__ if p.type != Any else "Any",
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "choices": p.choices
                }
                for p in self.parameters
            ],
            "execution_mode": self.execution_mode.name,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "enabled": self.enabled,
            "permissions": self.permissions,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillMetadata":
        """从字典创建"""
        params = []
        for p in data.get("parameters", []):
            param = SkillParameter(
                name=p["name"],
                type=eval(p["type"]) if p["type"] != "Any" else Any,
                description=p.get("description", ""),
                required=p.get("required", True),
                default=p.get("default"),
                choices=p.get("choices")
            )
            params.append(param)

        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            dependencies=data.get("dependencies", []),
            parameters=params,
            execution_mode=ExecutionMode[data.get("execution_mode", "SYNC")],
            timeout=data.get("timeout", 60.0),
            retry_count=data.get("retry_count", 0),
            enabled=data.get("enabled", True),
            permissions=data.get("permissions", [])
        )


@dataclass
class SkillResult:
    """Skill执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_result(cls, data: Any = None, **kwargs) -> "SkillResult":
        """创建成功结果"""
        return cls(success=True, data=data, **kwargs)

    @classmethod
    def error_result(cls, error: str, **kwargs) -> "SkillResult":
        """创建错误结果"""
        return cls(success=False, error=error, **kwargs)


class BaseSkill(ABC):
    """
    Skill基类

    所有Skill必须继承此类，并实现execute方法。

    示例:
        class MySkill(BaseSkill):
            def __init__(self):
                super().__init__(
                    metadata=SkillMetadata(
                        name="my_skill",
                        description="我的Skill"
                    )
                )

            def execute(self, context, **kwargs):
                # 实现逻辑
                return SkillResult.success_result(data=result)
    """

    def __init__(self, metadata: Optional[SkillMetadata] = None):
        """
        初始化Skill

        Args:
            metadata: Skill元数据，如果为None则自动从类属性创建
        """
        self._id = str(uuid.uuid4())
        self._status = SkillStatus.UNLOADED
        self._metadata = metadata or self._create_default_metadata()
        self._instance_config: Dict[str, Any] = {}
        self._created_at = datetime.now()
        self._last_executed: Optional[datetime] = None
        self._execution_count = 0
        self._error_count = 0

    def _create_default_metadata(self) -> SkillMetadata:
        """创建默认元数据"""
        return SkillMetadata(
            name=self.__class__.__name__.lower().replace("skill", ""),
            description=self.__doc__ or ""
        )

    @property
    def id(self) -> str:
        """Skill实例ID"""
        return self._id

    @property
    def status(self) -> SkillStatus:
        """当前状态"""
        return self._status

    @property
    def metadata(self) -> SkillMetadata:
        """Skill元数据"""
        return self._metadata

    @property
    def name(self) -> str:
        """Skill名称"""
        return self._metadata.name

    @property
    def version(self) -> str:
        """Skill版本"""
        return self._metadata.version

    @property
    def dependencies(self) -> List[str]:
        """依赖列表"""
        return self._metadata.dependencies

    @property
    def is_ready(self) -> bool:
        """是否就绪"""
        return self._status == SkillStatus.READY

    @property
    def stats(self) -> Dict[str, Any]:
        """统计信息"""
        return {
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "success_rate": (
                (self._execution_count - self._error_count) / self._execution_count * 100
                if self._execution_count > 0 else 100.0
            ),
            "last_executed": self._last_executed.isoformat() if self._last_executed else None,
            "created_at": self._created_at.isoformat()
        }

    def set_status(self, status: SkillStatus) -> None:
        """设置状态"""
        self._status = status

    def configure(self, config: Dict[str, Any]) -> None:
        """
        配置Skill

        Args:
            config: 配置字典
        """
        self._instance_config.update(config)
        self._on_configure(config)

    def _on_configure(self, config: Dict[str, Any]) -> None:
        """
        配置回调，子类可重写

        Args:
            config: 配置字典
        """
        pass

    def initialize(self, context: "SkillContext") -> SkillResult:
        """
        初始化Skill

        Args:
            context: 执行上下文

        Returns:
            SkillResult: 初始化结果
        """
        self.set_status(SkillStatus.INITIALIZING)
        try:
            result = self._on_initialize(context)
            if result.success:
                self.set_status(SkillStatus.READY)
            else:
                self.set_status(SkillStatus.ERROR)
            return result
        except Exception as e:
            self.set_status(SkillStatus.ERROR)
            return SkillResult.error_result(f"初始化失败: {str(e)}")

    def _on_initialize(self, context: "SkillContext") -> SkillResult:
        """
        初始化回调，子类可重写

        Args:
            context: 执行上下文

        Returns:
            SkillResult: 初始化结果
        """
        return SkillResult.success_result()

    def shutdown(self, context: "SkillContext") -> SkillResult:
        """
        关闭Skill

        Args:
            context: 执行上下文

        Returns:
            SkillResult: 关闭结果
        """
        self.set_status(SkillStatus.UNLOADING)
        try:
            result = self._on_shutdown(context)
            self.set_status(SkillStatus.UNLOADED)
            return result
        except Exception as e:
            return SkillResult.error_result(f"关闭失败: {str(e)}")

    def _on_shutdown(self, context: "SkillContext") -> SkillResult:
        """
        关闭回调，子类可重写

        Args:
            context: 执行上下文

        Returns:
            SkillResult: 关闭结果
        """
        return SkillResult.success_result()

    def validate_parameters(self, **kwargs) -> tuple[bool, str]:
        """
        验证参数

        Args:
            **kwargs: 参数

        Returns:
            tuple[bool, str]: (是否有效, 错误信息)
        """
        for param in self._metadata.parameters:
            value = kwargs.get(param.name)
            valid, error = param.validate(value)
            if not valid:
                return False, error
        return True, ""

    @abstractmethod
    def execute(self, context: "SkillContext", **kwargs) -> SkillResult:
        """
        执行Skill（子类必须实现）

        Args:
            context: 执行上下文
            **kwargs: 执行参数

        Returns:
            SkillResult: 执行结果
        """
        pass

    def run(self, context: "SkillContext", **kwargs) -> SkillResult:
        """
        运行Skill（包含参数验证和状态管理）

        Args:
            context: 执行上下文
            **kwargs: 执行参数

        Returns:
            SkillResult: 执行结果
        """
        import time

        # 验证状态
        if not self.is_ready:
            return SkillResult.error_result(f"Skill未就绪，当前状态: {self._status.name}")

        # 验证参数
        valid, error = self.validate_parameters(**kwargs)
        if not valid:
            return SkillResult.error_result(error)

        # 执行
        self._status = SkillStatus.RUNNING
        self._execution_count += 1
        self._last_executed = datetime.now()

        start_time = time.time()
        try:
            result = self.execute(context, **kwargs)
            result.execution_time = time.time() - start_time

            if not result.success:
                self._error_count += 1

        except Exception as e:
            self._error_count += 1
            result = SkillResult.error_result(
                f"执行异常: {str(e)}",
                execution_time=time.time() - start_time
            )
        finally:
            self._status = SkillStatus.READY

        return result

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self._id,
            "name": self.name,
            "version": self.version,
            "status": self._status.name,
            "metadata": self._metadata.to_dict(),
            "stats": self.stats,
            "config": self._instance_config
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', version='{self.version}', status={self._status.name})>"


class SkillError(Exception):
    """Skill异常基类"""
    pass


class SkillNotFoundError(SkillError):
    """Skill未找到异常"""
    pass


class SkillDependencyError(SkillError):
    """Skill依赖异常"""
    pass


class SkillExecutionError(SkillError):
    """Skill执行异常"""
    pass


class SkillConfigurationError(SkillError):
    """Skill配置异常"""
    pass
