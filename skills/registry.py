"""
Skills插件化系统 - 注册中心模块

提供Skill的注册、发现、查询和管理功能。
"""

from typing import Any, Callable, Dict, List, Optional, Set, Type, Union
from dataclasses import dataclass, field
from datetime import datetime
import threading
import fnmatch
import re

from .base import (
    BaseSkill,
    SkillMetadata,
    SkillStatus,
    SkillResult,
    SkillNotFoundError,
    SkillDependencyError
)


@dataclass
class RegisteredSkill:
    """注册的Skill信息"""
    name: str
    skill_class: Type[BaseSkill]
    metadata: SkillMetadata
    instance: Optional[BaseSkill] = None
    status: SkillStatus = SkillStatus.UNLOADED
    registered_at: datetime = field(default_factory=datetime.now)
    loaded_at: Optional[datetime] = None
    error_message: Optional[str] = None
    tags: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "status": self.status.name,
            "metadata": self.metadata.to_dict(),
            "registered_at": self.registered_at.isoformat(),
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "error_message": self.error_message,
            "tags": list(self.tags),
            "has_instance": self.instance is not None
        }


class SkillRegistry:
    """
    Skill注册中心

    管理所有Skill的注册、发现和生命周期。

    功能：
    - Skill注册和注销
    - Skill发现和查询
    - 依赖解析
    - 生命周期管理
    - 事件通知

    示例:
        registry = SkillRegistry()

        # 注册Skill
        registry.register(MySkill)

        # 获取Skill
        skill = registry.get("my_skill")

        # 查询Skill
        skills = registry.find_by_category("document_processing")
    """

    def __init__(self):
        """初始化注册中心"""
        # 存储注册的Skill类
        self._skill_classes: Dict[str, Type[BaseSkill]] = {}

        # 存储Skill元数据
        self._metadata: Dict[str, SkillMetadata] = {}

        # 存储Skill实例
        self._instances: Dict[str, BaseSkill] = {}

        # 存储注册信息
        self._registered: Dict[str, RegisteredSkill] = {}

        # 按分类索引
        self._by_category: Dict[str, Set[str]] = {}

        # 按标签索引
        self._by_tag: Dict[str, Set[str]] = {}

        # 依赖图
        self._dependency_graph: Dict[str, Set[str]] = {}

        # 事件监听器
        self._listeners: Dict[str, List[Callable]] = {
            "register": [],
            "unregister": [],
            "load": [],
            "unload": [],
            "error": []
        }

        # 线程安全
        self._lock = threading.RLock()

        # 统计信息
        self._stats = {
            "registered_count": 0,
            "loaded_count": 0,
            "error_count": 0
        }

    # ========== 注册管理 ==========

    def register(
        self,
        skill_class: Type[BaseSkill],
        metadata: Optional[SkillMetadata] = None
    ) -> RegisteredSkill:
        """
        注册Skill类

        Args:
            skill_class: Skill类
            metadata: 元数据（可选，默认从类创建）

        Returns:
            注册信息

        Raises:
            ValueError: 如果skill_class不是有效的Skill类
        """
        if not issubclass(skill_class, BaseSkill):
            raise ValueError(f"{skill_class.__name__} 必须继承 BaseSkill")

        # 获取或创建元数据
        if metadata is None:
            # 尝试从类属性获取
            if hasattr(skill_class, '_metadata'):
                metadata = skill_class._metadata
            else:
                # 创建默认元数据 - 使用snake_case命名
                import re
                name = skill_class.__name__
                # CamelCase to snake_case
                s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
                s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
                snake_name = s2.lower()
                metadata = SkillMetadata(
                    name=snake_name,
                    description=skill_class.__doc__ or ""
                )

        name = metadata.name

        with self._lock:
            # 检查是否已注册
            if name in self._skill_classes:
                raise ValueError(f"Skill '{name}' 已注册")

            # 创建注册信息
            registered = RegisteredSkill(
                name=name,
                skill_class=skill_class,
                metadata=metadata,
                tags=set(metadata.tags)
            )

            # 存储
            self._skill_classes[name] = skill_class
            self._metadata[name] = metadata
            self._registered[name] = registered

            # 更新索引
            self._update_indexes(name, metadata)

            # 更新依赖图
            self._dependency_graph[name] = set(metadata.dependencies)

            # 更新统计
            self._stats["registered_count"] += 1

            # 触发事件
            self._emit("register", registered)

            return registered

    def unregister(self, name: str) -> bool:
        """
        注销Skill

        Args:
            name: Skill名称

        Returns:
            是否成功注销
        """
        with self._lock:
            if name not in self._registered:
                return False

            # 检查是否有其他Skill依赖此Skill
            dependents = self._get_dependents(name)
            if dependents:
                raise SkillDependencyError(
                    f"无法注销 '{name}'，以下Skill依赖它: {dependents}"
                )

            # 卸载实例
            if name in self._instances:
                self.unload(name)

            # 获取注册信息
            registered = self._registered[name]

            # 移除索引
            self._remove_indexes(name)

            # 移除存储
            del self._skill_classes[name]
            del self._metadata[name]
            del self._registered[name]
            del self._dependency_graph[name]

            # 更新统计
            self._stats["registered_count"] -= 1

            # 触发事件
            self._emit("unregister", registered)

            return True

    def _update_indexes(self, name: str, metadata: SkillMetadata) -> None:
        """更新索引"""
        # 分类索引
        category = metadata.category
        if category not in self._by_category:
            self._by_category[category] = set()
        self._by_category[category].add(name)

        # 标签索引
        for tag in metadata.tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = set()
            self._by_tag[tag].add(name)

    def _remove_indexes(self, name: str) -> None:
        """移除索引"""
        metadata = self._metadata.get(name)
        if metadata:
            # 移除分类索引
            category = metadata.category
            if category in self._by_category:
                self._by_category[category].discard(name)

            # 移除标签索引
            for tag in metadata.tags:
                if tag in self._by_tag:
                    self._by_tag[tag].discard(name)

    def _get_dependents(self, name: str) -> List[str]:
        """获取依赖指定Skill的所有Skill"""
        dependents = []
        for skill_name, deps in self._dependency_graph.items():
            if name in deps:
                dependents.append(skill_name)
        return dependents

    # ========== 实例管理 ==========

    def load(
        self,
        name: str,
        context: "SkillContext",
        config: Optional[Dict[str, Any]] = None
    ) -> BaseSkill:
        """
        加载Skill实例

        Args:
            name: Skill名称
            context: 执行上下文
            config: 实例配置

        Returns:
            Skill实例

        Raises:
            SkillNotFoundError: 如果Skill未注册
        """
        with self._lock:
            if name not in self._skill_classes:
                raise SkillNotFoundError(f"Skill未注册: {name}")

            # 检查是否已加载
            if name in self._instances:
                return self._instances[name]

            # 获取注册信息
            registered = self._registered[name]
            registered.status = SkillStatus.LOADING

            try:
                # 解析依赖
                self._resolve_dependencies(name, context)

                # 创建实例
                skill_class = self._skill_classes[name]
                instance = skill_class()

                # 应用配置
                if config:
                    instance.configure(config)

                # 初始化
                registered.status = SkillStatus.INITIALIZING
                result = instance.initialize(context)

                if not result.success:
                    registered.status = SkillStatus.ERROR
                    registered.error_message = result.error
                    self._stats["error_count"] += 1
                    self._emit("error", registered, result.error)
                    raise SkillExecutionError(f"初始化失败: {result.error}")

                # 存储实例
                self._instances[name] = instance
                registered.instance = instance
                registered.status = SkillStatus.READY
                registered.loaded_at = datetime.now()

                # 更新统计
                self._stats["loaded_count"] += 1

                # 触发事件
                self._emit("load", registered)

                return instance

            except Exception as e:
                registered.status = SkillStatus.ERROR
                registered.error_message = str(e)
                self._stats["error_count"] += 1
                self._emit("error", registered, str(e))
                raise

    def unload(self, name: str, context: "SkillContext") -> bool:
        """
        卸载Skill实例

        Args:
            name: Skill名称
            context: 执行上下文

        Returns:
            是否成功卸载
        """
        with self._lock:
            if name not in self._instances:
                return False

            registered = self._registered.get(name)
            if registered:
                registered.status = SkillStatus.UNLOADING

                try:
                    instance = self._instances[name]
                    instance.shutdown(context)
                except Exception as e:
                    # 记录错误但继续卸载
                    if registered:
                        registered.error_message = str(e)

                # 移除实例
                del self._instances[name]
                registered.instance = None
                registered.status = SkillStatus.UNLOADED
                registered.loaded_at = None

                # 更新统计
                self._stats["loaded_count"] -= 1

                # 触发事件
                self._emit("unload", registered)

            return True

    def _resolve_dependencies(self, name: str, context: "SkillContext") -> None:
        """解析并加载依赖"""
        metadata = self._metadata[name]

        for dep_name in metadata.dependencies:
            if dep_name not in self._instances:
                # 递归加载依赖
                self.load(dep_name, context)

    def get(self, name: str) -> Optional[BaseSkill]:
        """
        获取Skill实例

        Args:
            name: Skill名称

        Returns:
            Skill实例或None
        """
        with self._lock:
            return self._instances.get(name)

    def require(self, name: str) -> BaseSkill:
        """
        获取必需的Skill实例

        Args:
            name: Skill名称

        Returns:
            Skill实例

        Raises:
            SkillNotFoundError: 如果Skill未找到
        """
        skill = self.get(name)
        if skill is None:
            raise SkillNotFoundError(f"Skill未加载: {name}")
        return skill

    # ========== 查询功能 ==========

    def list_skills(self) -> List[str]:
        """
        列出所有注册的Skill名称

        Returns:
            Skill名称列表
        """
        with self._lock:
            return list(self._registered.keys())

    def list_loaded(self) -> List[str]:
        """
        列出所有已加载的Skill名称

        Returns:
            Skill名称列表
        """
        with self._lock:
            return list(self._instances.keys())

    def find_by_category(self, category: str) -> List[RegisteredSkill]:
        """
        按分类查找Skill

        Args:
            category: 分类名称

        Returns:
            Skill注册信息列表
        """
        with self._lock:
            names = self._by_category.get(category, set())
            return [self._registered[name] for name in names if name in self._registered]

    def find_by_tag(self, tag: str) -> List[RegisteredSkill]:
        """
        按标签查找Skill

        Args:
            tag: 标签名称

        Returns:
            Skill注册信息列表
        """
        with self._lock:
            names = self._by_tag.get(tag, set())
            return [self._registered[name] for name in names if name in self._registered]

    def find_by_pattern(self, pattern: str) -> List[RegisteredSkill]:
        """
        按模式查找Skill（支持通配符）

        Args:
            pattern: 匹配模式，如 "text_*" 或 "*.processor"

        Returns:
            Skill注册信息列表
        """
        with self._lock:
            matches = []
            for name in self._registered:
                if fnmatch.fnmatch(name, pattern):
                    matches.append(self._registered[name])
            return matches

    def search(self, query: str) -> List[RegisteredSkill]:
        """
        搜索Skill（名称、描述、标签）

        Args:
            query: 搜索关键词

        Returns:
            Skill注册信息列表
        """
        with self._lock:
            results = []
            query_lower = query.lower()

            for name, registered in self._registered.items():
                metadata = registered.metadata

                # 搜索名称
                if query_lower in name.lower():
                    results.append(registered)
                    continue

                # 搜索描述
                if query_lower in metadata.description.lower():
                    results.append(registered)
                    continue

                # 搜索标签
                if any(query_lower in tag.lower() for tag in metadata.tags):
                    results.append(registered)
                    continue

                # 搜索分类
                if query_lower in metadata.category.lower():
                    results.append(registered)
                    continue

            return results

    def get_metadata(self, name: str) -> Optional[SkillMetadata]:
        """
        获取Skill元数据

        Args:
            name: Skill名称

        Returns:
            元数据或None
        """
        with self._lock:
            return self._metadata.get(name)

    def get_registered(self, name: str) -> Optional[RegisteredSkill]:
        """
        获取Skill注册信息

        Args:
            name: Skill名称

        Returns:
            注册信息或None
        """
        with self._lock:
            return self._registered.get(name)

    # ========== 依赖分析 ==========

    def check_circular_dependencies(self) -> List[List[str]]:
        """
        检查循环依赖

        Returns:
            循环依赖列表，每个循环是一个Skill名称列表
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self._dependency_graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # 发现循环
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        with self._lock:
            for node in self._dependency_graph:
                if node not in visited:
                    dfs(node, [])

        return cycles

    def get_dependency_order(self, name: str) -> List[str]:
        """
        获取Skill的依赖执行顺序

        Args:
            name: Skill名称

        Returns:
            依赖顺序列表（包含自身）
        """
        order = []
        visited = set()

        def visit(n: str):
            if n in visited:
                return
            visited.add(n)

            # 先访问依赖
            for dep in self._dependency_graph.get(n, set()):
                visit(dep)

            order.append(n)

        with self._lock:
            visit(name)

        return order

    # ========== 事件系统 ==========

    def on(self, event: str, callback: Callable) -> None:
        """
        注册事件监听器

        Args:
            event: 事件类型（register/unregister/load/unload/error）
            callback: 回调函数
        """
        if event in self._listeners:
            self._listeners[event].append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """
        移除事件监听器

        Args:
            event: 事件类型
            callback: 回调函数
        """
        if event in self._listeners:
            self._listeners[event] = [
                cb for cb in self._listeners[event] if cb != callback
            ]

    def _emit(self, event: str, *args, **kwargs) -> None:
        """触发事件"""
        for callback in self._listeners.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception:
                # 忽略监听器错误
                pass

    # ========== 批量操作 ==========

    def load_all(
        self,
        context: "SkillContext",
        config: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, SkillResult]:
        """
        加载所有已注册的Skill

        Args:
            context: 执行上下文
            config: Skill配置字典

        Returns:
            加载结果字典
        """
        results = {}
        config = config or {}

        # 按依赖顺序排序
        sorted_names = self._topological_sort()

        for name in sorted_names:
            try:
                skill_config = config.get(name, {})
                self.load(name, context, skill_config)
                results[name] = SkillResult.success_result()
            except Exception as e:
                results[name] = SkillResult.error_result(str(e))

        return results

    def unload_all(self, context: "SkillContext") -> Dict[str, bool]:
        """
        卸载所有已加载的Skill

        Args:
            context: 执行上下文

        Returns:
            卸载结果字典
        """
        results = {}

        # 反向依赖顺序卸载
        sorted_names = self._topological_sort()

        for name in reversed(sorted_names):
            try:
                results[name] = self.unload(name, context)
            except Exception as e:
                results[name] = False

        return results

    def _topological_sort(self) -> List[str]:
        """拓扑排序（按依赖顺序）"""
        in_degree = {name: 0 for name in self._registered}

        # 计算入度
        for name, deps in self._dependency_graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] += 1

        # 初始化队列
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # 更新入度
            for name, deps in self._dependency_graph.items():
                if node in deps:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        # 添加没有依赖关系的节点
        for name in self._registered:
            if name not in result:
                result.append(name)

        return result

    # ========== 统计信息 ==========

    @property
    def stats(self) -> Dict[str, Any]:
        """统计信息"""
        with self._lock:
            return {
                **self._stats,
                "total_registered": len(self._registered),
                "total_loaded": len(self._instances),
                "categories": list(self._by_category.keys()),
                "tags": list(self._by_tag.keys())
            }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        with self._lock:
            return {
                "skills": {
                    name: registered.to_dict()
                    for name, registered in self._registered.items()
                },
                "stats": self.stats,
                "categories": {
                    cat: list(names)
                    for cat, names in self._by_category.items()
                },
                "tags": {
                    tag: list(names)
                    for tag, names in self._by_tag.items()
                }
            }


# 全局注册中心实例
_default_registry: Optional[SkillRegistry] = None


def get_default_registry() -> SkillRegistry:
    """获取默认注册中心实例"""
    global _default_registry
    if _default_registry is None:
        _default_registry = SkillRegistry()
    return _default_registry


def set_default_registry(registry: SkillRegistry) -> None:
    """设置默认注册中心实例"""
    global _default_registry
    _default_registry = registry
