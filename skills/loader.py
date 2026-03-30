"""
Skills插件化系统 - 动态加载器模块

提供Skill的动态加载、热更新和模块管理功能。
"""

import os
import sys
import importlib
import importlib.util
import inspect
import pkgutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union
from dataclasses import dataclass, field
from datetime import datetime
import threading
import hashlib
import json

from .base import BaseSkill, SkillStatus, SkillResult, SkillConfigurationError
from .decorators import is_skill_class


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    path: str
    modified_time: float
    size: int
    hash: str
    skills: List[str] = field(default_factory=list)
    loaded_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "path": self.path,
            "modified_time": self.modified_time,
            "size": self.size,
            "hash": self.hash,
            "skills": self.skills,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "error": self.error
        }


class SkillLoader:
    """
    Skill动态加载器

    功能：
    - 从文件/目录加载Skill模块
    - 热更新支持
    - 模块缓存管理
    - 依赖追踪

    示例:
        loader = SkillLoader(registry)

        # 从目录加载
        loader.load_from_directory("/path/to/skills")

        # 从文件加载
        loader.load_from_file("/path/to/skill.py")

        # 热更新检查
        loader.check_updates()
    """

    def __init__(
        self,
        registry: "SkillRegistry",
        hot_reload: bool = True,
        cache_enabled: bool = True
    ):
        """
        初始化加载器

        Args:
            registry: Skill注册中心
            hot_reload: 是否启用热更新
            cache_enabled: 是否启用缓存
        """
        self._registry = registry
        self._hot_reload = hot_reload
        self._cache_enabled = cache_enabled

        # 模块信息
        self._modules: Dict[str, ModuleInfo] = {}

        # 模块对象缓存
        self._module_cache: Dict[str, Any] = {}

        # 加载路径
        self._load_paths: Set[str] = set()

        # 线程安全
        self._lock = threading.RLock()

        # 监听器
        self._listeners: Dict[str, List[Callable]] = {
            "load": [],
            "unload": [],
            "reload": [],
            "error": []
        }

        # 热更新线程
        self._watcher_thread: Optional[threading.Thread] = None
        self._watcher_running = False
        self._watch_interval = 5.0  # 秒

    # ========== 加载方法 ==========

    def load_from_file(
        self,
        file_path: Union[str, Path],
        module_name: Optional[str] = None
    ) -> List[Type[BaseSkill]]:
        """
        从文件加载Skill

        Args:
            file_path: 文件路径
            module_name: 模块名称（可选）

        Returns:
            加载的Skill类列表
        """
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if not file_path.suffix == ".py":
            raise ValueError(f"不支持的文件类型: {file_path.suffix}")

        # 生成模块名
        if module_name is None:
            module_name = file_path.stem

        # 计算文件哈希
        file_hash = self._compute_file_hash(file_path)

        with self._lock:
            # 检查缓存
            if self._cache_enabled and module_name in self._module_cache:
                cached_info = self._modules.get(module_name)
                if cached_info and cached_info.hash == file_hash:
                    return self._get_skill_classes_from_module(
                        self._module_cache[module_name]
                    )

            # 加载模块
            try:
                spec = importlib.util.spec_from_file_location(
                    module_name,
                    file_path
                )
                if spec is None or spec.loader is None:
                    raise ImportError(f"无法加载模块: {file_path}")

                module = importlib.util.module_from_spec(spec)

                # 添加到sys.modules
                sys.modules[module_name] = module

                # 执行模块
                spec.loader.exec_module(module)

                # 缓存模块
                if self._cache_enabled:
                    self._module_cache[module_name] = module

                # 提取Skill类
                skill_classes = self._get_skill_classes_from_module(module)

                # 记录模块信息
                stat = file_path.stat()
                module_info = ModuleInfo(
                    name=module_name,
                    path=str(file_path),
                    modified_time=stat.st_mtime,
                    size=stat.st_size,
                    hash=file_hash,
                    skills=[cls.__name__ for cls in skill_classes],
                    loaded_at=datetime.now()
                )
                self._modules[module_name] = module_info

                # 触发事件
                self._emit("load", module_info, skill_classes)

                return skill_classes

            except Exception as e:
                error_msg = f"加载模块失败 {file_path}: {str(e)}"
                module_info = ModuleInfo(
                    name=module_name,
                    path=str(file_path),
                    modified_time=0,
                    size=0,
                    hash="",
                    error=error_msg
                )
                self._modules[module_name] = module_info
                self._emit("error", module_info, e)
                raise SkillConfigurationError(error_msg) from e

    def load_from_directory(
        self,
        directory: Union[str, Path],
        recursive: bool = True,
        pattern: str = "*.py"
    ) -> Dict[str, List[Type[BaseSkill]]]:
        """
        从目录加载Skill

        Args:
            directory: 目录路径
            recursive: 是否递归加载
            pattern: 文件匹配模式

        Returns:
            加载结果字典 {模块名: Skill类列表}
        """
        directory = Path(directory).resolve()

        if not directory.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")

        if not directory.is_dir():
            raise NotADirectoryError(f"不是目录: {directory}")

        results = {}

        # 添加到加载路径
        self._add_to_path(directory)

        # 查找Python文件
        if recursive:
            files = list(directory.rglob(pattern))
        else:
            files = list(directory.glob(pattern))

        # 排除__pycache__和测试文件
        files = [
            f for f in files
            if "__pycache__" not in str(f) and not f.name.startswith("test_")
        ]

        for file_path in files:
            try:
                # 计算相对模块名
                rel_path = file_path.relative_to(directory)
                module_parts = list(rel_path.parent.parts) + [rel_path.stem]
                module_name = ".".join(module_parts)

                skill_classes = self.load_from_file(file_path, module_name)
                results[module_name] = skill_classes

            except Exception as e:
                # 记录错误但继续加载其他文件
                results[module_name] = []
                self._emit("error", None, e)

        return results

    def load_from_package(
        self,
        package_name: str
    ) -> List[Type[BaseSkill]]:
        """
        从包加载Skill

        Args:
            package_name: 包名称

        Returns:
            加载的Skill类列表
        """
        try:
            # 导入包
            package = importlib.import_module(package_name)
            package_path = Path(package.__file__).parent

            # 遍历子模块
            skill_classes = []

            for _, name, is_pkg in pkgutil.iter_modules([str(package_path)]):
                full_name = f"{package_name}.{name}"

                try:
                    if is_pkg:
                        # 递归加载子包
                        skill_classes.extend(self.load_from_package(full_name))
                    else:
                        # 加载模块
                        module = importlib.import_module(full_name)
                        skill_classes.extend(
                            self._get_skill_classes_from_module(module)
                        )
                except Exception as e:
                    self._emit("error", None, e)

            return skill_classes

        except ImportError as e:
            raise SkillConfigurationError(f"无法导入包: {package_name}") from e

    def unload_module(self, module_name: str) -> bool:
        """
        卸载模块

        Args:
            module_name: 模块名称

        Returns:
            是否成功卸载
        """
        with self._lock:
            if module_name not in self._modules:
                return False

            module_info = self._modules[module_name]

            # 注销模块中的Skill
            for skill_name in module_info.skills:
                try:
                    self._registry.unregister(skill_name.lower().replace("skill", ""))
                except Exception:
                    pass

            # 从sys.modules移除
            if module_name in sys.modules:
                del sys.modules[module_name]

            # 从缓存移除
            if module_name in self._module_cache:
                del self._module_cache[module_name]

            # 从模块列表移除
            del self._modules[module_name]

            # 触发事件
            self._emit("unload", module_info)

            return True

    # ========== 热更新 ==========

    def check_updates(self) -> Dict[str, bool]:
        """
        检查并应用更新

        Returns:
            更新结果字典 {模块名: 是否更新}
        """
        updates = {}

        with self._lock:
            for module_name, module_info in list(self._modules.items()):
                try:
                    file_path = Path(module_info.path)

                    if not file_path.exists():
                        # 文件被删除
                        self.unload_module(module_name)
                        updates[module_name] = True
                        continue

                    # 检查修改时间
                    stat = file_path.stat()
                    if stat.st_mtime > module_info.modified_time:
                        # 文件已修改，重新加载
                        self._reload_module(module_name)
                        updates[module_name] = True
                    else:
                        updates[module_name] = False

                except Exception as e:
                    updates[module_name] = False
                    self._emit("error", module_info, e)

        return updates

    def _reload_module(self, module_name: str) -> List[Type[BaseSkill]]:
        """重新加载模块"""
        module_info = self._modules[module_name]
        file_path = Path(module_info.path)

        # 卸载旧模块
        self.unload_module(module_name)

        # 重新加载
        skill_classes = self.load_from_file(file_path, module_name)

        # 触发事件
        self._emit("reload", self._modules[module_name], skill_classes)

        return skill_classes

    def start_watcher(self, interval: Optional[float] = None) -> None:
        """
        启动热更新监视器

        Args:
            interval: 检查间隔（秒）
        """
        if not self._hot_reload:
            return

        if self._watcher_running:
            return

        self._watch_interval = interval or self._watch_interval
        self._watcher_running = True

        def watch_loop():
            import time
            while self._watcher_running:
                try:
                    self.check_updates()
                except Exception:
                    pass
                time.sleep(self._watch_interval)

        self._watcher_thread = threading.Thread(
            target=watch_loop,
            daemon=True,
            name="SkillLoaderWatcher"
        )
        self._watcher_thread.start()

    def stop_watcher(self) -> None:
        """停止热更新监视器"""
        self._watcher_running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=1.0)
            self._watcher_thread = None

    # ========== 辅助方法 ==========

    def _compute_file_hash(self, file_path: Path) -> str:
        """计算文件哈希"""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _get_skill_classes_from_module(self, module) -> List[Type[BaseSkill]]:
        """从模块中提取Skill类"""
        skill_classes = []

        for name in dir(module):
            obj = getattr(module, name)

            # 检查是否为Skill类
            if (isinstance(obj, type) and
                issubclass(obj, BaseSkill) and
                obj is not BaseSkill and
                not name.startswith("_")):
                skill_classes.append(obj)

        return skill_classes

    def _add_to_path(self, directory: Path) -> None:
        """添加目录到Python路径"""
        str_path = str(directory)
        if str_path not in sys.path:
            sys.path.insert(0, str_path)
            self._load_paths.add(str_path)

    # ========== 事件系统 ==========

    def on(self, event: str, callback: Callable) -> None:
        """
        注册事件监听器

        Args:
            event: 事件类型（load/unload/reload/error）
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
                pass

    # ========== 查询方法 ==========

    def get_loaded_modules(self) -> List[str]:
        """
        获取已加载的模块列表

        Returns:
            模块名称列表
        """
        with self._lock:
            return list(self._modules.keys())

    def get_module_info(self, module_name: str) -> Optional[ModuleInfo]:
        """
        获取模块信息

        Args:
            module_name: 模块名称

        Returns:
            模块信息或None
        """
        with self._lock:
            return self._modules.get(module_name)

    def get_module_for_skill(self, skill_name: str) -> Optional[str]:
        """
        获取Skill所在的模块

        Args:
            skill_name: Skill名称

        Returns:
            模块名称或None
        """
        with self._lock:
            for module_name, module_info in self._modules.items():
                if skill_name in module_info.skills:
                    return module_name
            return None

    # ========== 统计信息 ==========

    @property
    def stats(self) -> Dict[str, Any]:
        """统计信息"""
        with self._lock:
            return {
                "total_modules": len(self._modules),
                "cached_modules": len(self._module_cache),
                "load_paths": list(self._load_paths),
                "hot_reload": self._hot_reload,
                "watcher_running": self._watcher_running
            }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        with self._lock:
            return {
                "modules": {
                    name: info.to_dict()
                    for name, info in self._modules.items()
                },
                "stats": self.stats
            }


class SkillImporter:
    """
    Skill导入器

    简化Skill导入和注册的辅助类。
    """

    def __init__(self, registry: "SkillRegistry", loader: Optional[SkillLoader] = None):
        """
        初始化导入器

        Args:
            registry: Skill注册中心
            loader: 加载器（可选）
        """
        self._registry = registry
        self._loader = loader or SkillLoader(registry)

    def import_from_file(self, file_path: Union[str, Path]) -> List[str]:
        """
        从文件导入Skill

        Args:
            file_path: 文件路径

        Returns:
            注册的Skill名称列表
        """
        skill_classes = self._loader.load_from_file(file_path)

        registered = []
        for skill_class in skill_classes:
            self._registry.register(skill_class)
            # 获取Skill名称
            instance = skill_class()
            registered.append(instance.name)

        return registered

    def import_from_directory(
        self,
        directory: Union[str, Path],
        recursive: bool = True
    ) -> Dict[str, List[str]]:
        """
        从目录导入Skill

        Args:
            directory: 目录路径
            recursive: 是否递归

        Returns:
            导入结果字典 {模块名: Skill名称列表}
        """
        results = self._loader.load_from_directory(directory, recursive)

        registered = {}
        for module_name, skill_classes in results.items():
            skill_names = []
            for skill_class in skill_classes:
                self._registry.register(skill_class)
                instance = skill_class()
                skill_names.append(instance.name)
            registered[module_name] = skill_names

        return registered

    def import_from_package(self, package_name: str) -> List[str]:
        """
        从包导入Skill

        Args:
            package_name: 包名称

        Returns:
            注册的Skill名称列表
        """
        skill_classes = self._loader.load_from_package(package_name)

        registered = []
        for skill_class in skill_classes:
            self._registry.register(skill_class)
            instance = skill_class()
            registered.append(instance.name)

        return registered
