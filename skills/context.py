"""
Skills插件化系统 - 执行上下文模块

提供Skill执行时的上下文环境，包括依赖注入、资源共享和状态管理。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Type, Union
from datetime import datetime
from contextlib import contextmanager
import uuid
import threading
import copy


@dataclass
class ExecutionContext:
    """执行上下文数据"""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.now)
    timeout: float = 60.0
    retry_count: int = 0
    max_retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillContext:
    """
    Skill执行上下文
    
    提供Skill执行时的完整环境，包括：
    - 依赖注入
    - 资源共享
    - 状态管理
    - 配置访问
    - 日志记录
    
    示例:
        context = SkillContext(registry=registry, config=config)
        result = skill.run(context, param1="value1")
    """
    
    def __init__(
        self,
        registry: Optional["SkillRegistry"] = None,
        config: Optional[Dict[str, Any]] = None,
        parent: Optional["SkillContext"] = None,
        execution_context: Optional[ExecutionContext] = None
    ):
        """
        初始化上下文
        
        Args:
            registry: Skill注册中心
            config: 全局配置
            parent: 父上下文（用于子任务）
            execution_context: 执行上下文数据
        """
        self._registry = registry
        self._config = config or {}
        self._parent = parent
        self._execution = execution_context or ExecutionContext()
        
        # 资源存储
        self._resources: Dict[str, Any] = {}
        self._shared_data: Dict[str, Any] = {}
        self._local_data: Dict[str, Any] = {}
        
        # 依赖缓存
        self._dependency_cache: Dict[str, Any] = {}
        
        # 状态管理
        self._state: Dict[str, Any] = {}
        self._history: List[Dict[str, Any]] = []
        
        # 线程安全
        self._lock = threading.RLock()
        
        # 日志记录器
        self._logs: List[Dict[str, Any]] = []
        
        # 从父上下文继承数据
        if parent:
            self._shared_data = parent._shared_data
            self._config = {**parent._config, **(config or {})}
    
    @property
    def execution_id(self) -> str:
        """执行ID"""
        return self._execution.execution_id
    
    @property
    def registry(self) -> Optional["SkillRegistry"]:
        """Skill注册中心"""
        return self._registry
    
    @property
    def config(self) -> Dict[str, Any]:
        """全局配置"""
        return self._config
    
    @property
    def parent(self) -> Optional["SkillContext"]:
        """父上下文"""
        return self._parent
    
    @property
    def is_root(self) -> bool:
        """是否为根上下文"""
        return self._parent is None
    
    @property
    def depth(self) -> int:
        """上下文深度"""
        depth = 0
        current = self._parent
        while current:
            depth += 1
            current = current._parent
        return depth
    
    # ========== 配置管理 ==========
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键（支持点号分隔，如"database.host"）
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set_config(self, key: str, value: Any) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split(".")
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    # ========== 依赖注入 ==========
    
    def get_dependency(self, name: str) -> Optional["BaseSkill"]:
        """
        获取依赖的Skill
        
        Args:
            name: Skill名称
            
        Returns:
            Skill实例或None
        """
        # 检查缓存
        if name in self._dependency_cache:
            return self._dependency_cache[name]
        
        # 从注册中心获取
        if self._registry:
            skill = self._registry.get(name)
            if skill:
                self._dependency_cache[name] = skill
                return skill
        
        return None
    
    def require(self, name: str) -> "BaseSkill":
        """
        获取必需的依赖
        
        Args:
            name: Skill名称
            
        Returns:
            Skill实例
            
        Raises:
            SkillNotFoundError: 如果Skill未找到
        """
        skill = self.get_dependency(name)
        if skill is None:
            from .base import SkillNotFoundError
            raise SkillNotFoundError(f"依赖的Skill未找到: {name}")
        return skill
    
    def invoke(
        self,
        name: str,
        **kwargs
    ) -> "SkillResult":
        """
        调用其他Skill
        
        Args:
            name: Skill名称
            **kwargs: 执行参数
            
        Returns:
            执行结果
        """
        skill = self.require(name)
        
        # 创建子上下文
        child_context = self.create_child()
        
        # 记录调用
        self._log("invoke", {"skill": name, "params": kwargs})
        
        # 执行
        return skill.run(child_context, **kwargs)
    
    async def invoke_async(
        self,
        name: str,
        **kwargs
    ) -> "SkillResult":
        """
        异步调用其他Skill
        
        Args:
            name: Skill名称
            **kwargs: 执行参数
            
        Returns:
            执行结果
        """
        import asyncio
        
        skill = self.require(name)
        child_context = self.create_child()
        
        self._log("invoke_async", {"skill": name, "params": kwargs})
        
        # 如果Skill有异步execute方法
        if hasattr(skill.execute, '__code__') and skill.execute.__code__.co_flags & 0x80:
            return await skill.execute(child_context, **kwargs)
        else:
            # 在线程池中运行同步方法
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: skill.run(child_context, **kwargs)
            )
    
    # ========== 资源管理 ==========
    
    def register_resource(self, name: str, resource: Any) -> None:
        """
        注册资源
        
        Args:
            name: 资源名称
            resource: 资源对象
        """
        with self._lock:
            self._resources[name] = resource
    
    def get_resource(self, name: str) -> Optional[Any]:
        """
        获取资源
        
        Args:
            name: 资源名称
            
        Returns:
            资源对象或None
        """
        with self._lock:
            # 先检查本地资源
            if name in self._resources:
                return self._resources[name]
            
            # 检查父上下文
            if self._parent:
                return self._parent.get_resource(name)
            
            return None
    
    def require_resource(self, name: str) -> Any:
        """
        获取必需的资源
        
        Args:
            name: 资源名称
            
        Returns:
            资源对象
            
        Raises:
            KeyError: 如果资源未找到
        """
        resource = self.get_resource(name)
        if resource is None:
            raise KeyError(f"资源未找到: {name}")
        return resource
    
    def has_resource(self, name: str) -> bool:
        """
        检查资源是否存在
        
        Args:
            name: 资源名称
            
        Returns:
            是否存在
        """
        return self.get_resource(name) is not None
    
    # ========== 数据共享 ==========
    
    def set_shared(self, key: str, value: Any) -> None:
        """
        设置共享数据（对所有上下文可见）
        
        Args:
            key: 数据键
            value: 数据值
        """
        with self._lock:
            self._shared_data[key] = value
    
    def get_shared(self, key: str, default: Any = None) -> Any:
        """
        获取共享数据
        
        Args:
            key: 数据键
            default: 默认值
            
        Returns:
            数据值
        """
        return self._shared_data.get(key, default)
    
    def set_local(self, key: str, value: Any) -> None:
        """
        设置本地数据（仅当前上下文可见）
        
        Args:
            key: 数据键
            value: 数据值
        """
        with self._lock:
            self._local_data[key] = value
    
    def get_local(self, key: str, default: Any = None) -> Any:
        """
        获取本地数据
        
        Args:
            key: 数据键
            default: 默认值
            
        Returns:
            数据值
        """
        return self._local_data.get(key, default)
    
    # ========== 状态管理 ==========
    
    def set_state(self, key: str, value: Any) -> None:
        """
        设置状态
        
        Args:
            key: 状态键
            value: 状态值
        """
        with self._lock:
            self._state[key] = value
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """
        获取状态
        
        Args:
            key: 状态键
            default: 默认值
            
        Returns:
            状态值
        """
        return self._state.get(key, default)
    
    def update_state(self, updates: Dict[str, Any]) -> None:
        """
        批量更新状态
        
        Args:
            updates: 更新字典
        """
        with self._lock:
            self._state.update(updates)
    
    def clear_state(self) -> None:
        """清除所有状态"""
        with self._lock:
            self._state.clear()
    
    # ========== 历史记录 ==========
    
    def record(self, event: str, data: Dict[str, Any]) -> None:
        """
        记录事件
        
        Args:
            event: 事件类型
            data: 事件数据
        """
        with self._lock:
            self._history.append({
                "event": event,
                "data": data,
                "timestamp": datetime.now().isoformat()
            })
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        获取历史记录
        
        Returns:
            历史记录列表
        """
        return copy.deepcopy(self._history)
    
    # ========== 日志管理 ==========
    
    def _log(self, level: str, message: Union[str, Dict]) -> None:
        """
        记录日志
        
        Args:
            level: 日志级别
            message: 日志消息
        """
        with self._lock:
            self._logs.append({
                "level": level,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "execution_id": self.execution_id
            })
    
    def log_debug(self, message: str) -> None:
        """记录调试日志"""
        self._log("debug", message)
    
    def log_info(self, message: str) -> None:
        """记录信息日志"""
        self._log("info", message)
    
    def log_warning(self, message: str) -> None:
        """记录警告日志"""
        self._log("warning", message)
    
    def log_error(self, message: str) -> None:
        """记录错误日志"""
        self._log("error", message)
    
    def get_logs(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取日志
        
        Args:
            level: 日志级别过滤
            
        Returns:
            日志列表
        """
        with self._lock:
            if level:
                return [log for log in self._logs if log["level"] == level]
            return copy.deepcopy(self._logs)
    
    # ========== 上下文管理 ==========
    
    def create_child(self) -> "SkillContext":
        """
        创建子上下文
        
        Returns:
            子上下文实例
        """
        child_execution = ExecutionContext(
            parent_id=self.execution_id,
            timeout=self._execution.timeout,
            max_retries=self._execution.max_retries
        )
        
        return SkillContext(
            registry=self._registry,
            config=self._config,
            parent=self,
            execution_context=child_execution
        )
    
    @contextmanager
    def child_context(self):
        """
        子上下文管理器
        
        Yields:
            子上下文实例
        """
        child = self.create_child()
        try:
            yield child
        finally:
            # 子上下文清理
            pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            上下文信息字典
        """
        return {
            "execution_id": self.execution_id,
            "parent_id": self._execution.parent_id,
            "depth": self.depth,
            "is_root": self.is_root,
            "config_keys": list(self._config.keys()),
            "resources": list(self._resources.keys()),
            "shared_keys": list(self._shared_data.keys()),
            "local_keys": list(self._local_data.keys()),
            "state": self._state,
            "log_count": len(self._logs),
            "history_count": len(self._history)
        }
    
    def __repr__(self) -> str:
        return f"<SkillContext(execution_id={self.execution_id}, depth={self.depth})>"


class ContextManager:
    """
    上下文管理器
    
    管理多个执行上下文的生命周期。
    """
    
    def __init__(self):
        self._contexts: Dict[str, SkillContext] = {}
        self._lock = threading.RLock()
    
    def create(
        self,
        registry: Optional["SkillRegistry"] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> SkillContext:
        """
        创建新上下文
        
        Args:
            registry: Skill注册中心
            config: 全局配置
            
        Returns:
            新上下文实例
        """
        context = SkillContext(registry=registry, config=config)
        
        with self._lock:
            self._contexts[context.execution_id] = context
        
        return context
    
    def get(self, execution_id: str) -> Optional[SkillContext]:
        """
        获取上下文
        
        Args:
            execution_id: 执行ID
            
        Returns:
            上下文实例或None
        """
        with self._lock:
            return self._contexts.get(execution_id)
    
    def remove(self, execution_id: str) -> bool:
        """
        移除上下文
        
        Args:
            execution_id: 执行ID
            
        Returns:
            是否成功移除
        """
        with self._lock:
            if execution_id in self._contexts:
                del self._contexts[execution_id]
                return True
            return False
    
    def clear(self) -> None:
        """清除所有上下文"""
        with self._lock:
            self._contexts.clear()
    
    @property
    def count(self) -> int:
        """上下文数量"""
        with self._lock:
            return len(self._contexts)
