"""
Skills插件化系统 - 调度器模块

提供Skill的执行调度、任务管理和执行控制功能。
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from queue import PriorityQueue, Queue
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import uuid

from .base import BaseSkill, SkillResult, SkillStatus, ExecutionMode, SkillExecutionError
from .context import SkillContext


class TaskStatus(Enum):
    """任务状态"""
    PENDING = auto()       # 等待中
    SCHEDULED = auto()     # 已调度
    RUNNING = auto()       # 运行中
    COMPLETED = auto()     # 已完成
    FAILED = auto()        # 失败
    CANCELLED = auto()     # 已取消
    TIMEOUT = auto()       # 超时


@dataclass
class TaskInfo:
    """任务信息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    skill_name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[SkillResult] = None
    error: Optional[str] = None
    parent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.SYNC
    timeout: float = 60.0
    retry_count: int = 0
    max_retries: int = 0

    @property
    def execution_time(self) -> float:
        """执行时间（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def wait_time(self) -> float:
        """等待时间（秒）"""
        if self.created_at and self.started_at:
            return (self.started_at - self.created_at).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "skill_name": self.skill_name,
            "status": self.status.name,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time": self.execution_time,
            "wait_time": self.wait_time,
            "result": self.result.to_dict() if self.result else None,
            "error": self.error,
            "parent_id": self.parent_id,
            "dependencies": self.dependencies
        }


class Task:
    """任务包装器"""

    def __init__(self, info: TaskInfo, skill: BaseSkill, context: SkillContext):
        self.info = info
        self.skill = skill
        self.context = context
        self._future: Optional[asyncio.Future] = None
        self._cancelled = False

    def run(self) -> SkillResult:
        """执行任务"""
        if self._cancelled:
            return SkillResult.error_result("任务已取消")

        self.info.status = TaskStatus.RUNNING
        self.info.started_at = datetime.now()

        try:
            result = self.skill.run(self.context, **self.info.params)
            self.info.result = result
            self.info.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
            self.info.error = result.error
            return result
        except Exception as e:
            error_msg = str(e)
            self.info.error = error_msg
            self.info.status = TaskStatus.FAILED
            return SkillResult.error_result(error_msg)
        finally:
            self.info.completed_at = datetime.now()

    async def run_async(self) -> SkillResult:
        """异步执行任务"""
        if self._cancelled:
            return SkillResult.error_result("任务已取消")

        self.info.status = TaskStatus.RUNNING
        self.info.started_at = datetime.now()

        try:
            # 在线程池中执行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.skill.run(self.context, **self.info.params)
            )
            self.info.result = result
            self.info.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
            self.info.error = result.error
            return result
        except Exception as e:
            error_msg = str(e)
            self.info.error = error_msg
            self.info.status = TaskStatus.FAILED
            return SkillResult.error_result(error_msg)
        finally:
            self.info.completed_at = datetime.now()

    def cancel(self) -> bool:
        """取消任务"""
        if self.info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return False

        self._cancelled = True
        self.info.status = TaskStatus.CANCELLED
        return True


class SkillScheduler:
    """
    Skill调度器

    功能：
    - 任务调度（同步/异步/并行）
    - 执行顺序控制
    - 超时控制
    - 优先级管理
    - 依赖管理

    示例:
        scheduler = SkillScheduler(registry)

        # 提交任务
        task_id = scheduler.submit("my_skill", param1="value1")

        # 执行所有任务
        results = scheduler.run_all()

        # 并行执行
        results = scheduler.run_parallel(["skill1", "skill2"])
    """

    def __init__(
        self,
        registry: "SkillRegistry",
        max_workers: int = 4,
        default_timeout: float = 60.0
    ):
        """
        初始化调度器

        Args:
            registry: Skill注册中心
            max_workers: 最大工作线程数
            default_timeout: 默认超时时间
        """
        self._registry = registry
        self._max_workers = max_workers
        self._default_timeout = default_timeout

        # 任务存储
        self._tasks: Dict[str, Task] = {}
        self._task_queue: PriorityQueue = PriorityQueue()

        # 执行器
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        # 事件监听
        self._listeners: Dict[str, List[Callable]] = {
            "submit": [],
            "start": [],
            "complete": [],
            "error": [],
            "timeout": []
        }

        # 线程安全
        self._lock = threading.RLock()

        # 统计
        self._stats = {
            "submitted": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "timeout": 0
        }

    # ========== 任务提交 ==========

    def submit(
        self,
        skill_name: str,
        params: Optional[Dict[str, Any]] = None,
        priority: int = 5,
        timeout: Optional[float] = None,
        dependencies: Optional[List[str]] = None,
        parent_id: Optional[str] = None,
        context: Optional[SkillContext] = None
    ) -> str:
        """
        提交任务

        Args:
            skill_name: Skill名称
            params: 执行参数
            priority: 优先级（1-10，数字越小优先级越高）
            timeout: 超时时间
            dependencies: 依赖任务ID列表
            parent_id: 父任务ID
            context: 执行上下文

        Returns:
            任务ID
        """
        # 获取Skill
        skill = self._registry.require(skill_name)

        # 创建任务信息
        task_info = TaskInfo(
            skill_name=skill_name,
            params=params or {},
            priority=priority,
            timeout=timeout or self._default_timeout,
            dependencies=dependencies or [],
            parent_id=parent_id,
            execution_mode=skill.metadata.execution_mode,
            max_retries=skill.metadata.retry_count
        )

        # 创建上下文
        if context is None:
            context = SkillContext(registry=self._registry)

        # 创建任务
        task = Task(task_info, skill, context)

        with self._lock:
            self._tasks[task_info.id] = task
            self._task_queue.put((priority, task_info.created_at, task_info.id))
            self._stats["submitted"] += 1

        # 触发事件
        self._emit("submit", task_info)

        return task_info.id

    def submit_batch(
        self,
        tasks: List[Tuple[str, Dict[str, Any]]],
        priority: int = 5
    ) -> List[str]:
        """
        批量提交任务

        Args:
            tasks: 任务列表 [(skill_name, params), ...]
            priority: 优先级

        Returns:
            任务ID列表
        """
        task_ids = []
        for skill_name, params in tasks:
            task_id = self.submit(skill_name, params, priority)
            task_ids.append(task_id)
        return task_ids

    # ========== 任务执行 ==========

    def run(self, task_id: str) -> SkillResult:
        """
        执行单个任务

        Args:
            task_id: 任务ID

        Returns:
            执行结果
        """
        with self._lock:
            if task_id not in self._tasks:
                raise ValueError(f"任务不存在: {task_id}")

            task = self._tasks[task_id]

        # 检查依赖
        if task.info.dependencies:
            for dep_id in task.info.dependencies:
                dep_task = self._tasks.get(dep_id)
                if dep_task and dep_task.info.status != TaskStatus.COMPLETED:
                    # 等待依赖完成
                    self.run(dep_id)

        # 执行任务
        self._emit("start", task.info)

        result = task.run()

        if result.success:
            self._stats["completed"] += 1
            self._emit("complete", task.info, result)
        else:
            self._stats["failed"] += 1
            self._emit("error", task.info, result.error)

        return result

    def run_with_timeout(self, task_id: str, timeout: float) -> SkillResult:
        """
        带超时的任务执行

        Args:
            task_id: 任务ID
            timeout: 超时时间

        Returns:
            执行结果
        """
        import concurrent.futures

        with self._lock:
            if task_id not in self._tasks:
                raise ValueError(f"任务不存在: {task_id}")

            task = self._tasks[task_id]

        # 使用线程池执行
        future = self._executor.submit(task.run)

        try:
            result = future.result(timeout=timeout)
            return result
        except concurrent.futures.TimeoutError:
            task.info.status = TaskStatus.TIMEOUT
            self._stats["timeout"] += 1
            self._emit("timeout", task.info)
            return SkillResult.error_result(f"任务执行超时（{timeout}秒）")

    def run_all(self) -> Dict[str, SkillResult]:
        """
        执行所有任务（按优先级顺序）

        Returns:
            执行结果字典 {任务ID: 结果}
        """
        results = {}

        while not self._task_queue.empty():
            try:
                _, _, task_id = self._task_queue.get()
                result = self.run(task_id)
                results[task_id] = result
            except Exception as e:
                results[task_id] = SkillResult.error_result(str(e))

        return results

    def run_parallel(
        self,
        task_ids: Optional[List[str]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, SkillResult]:
        """
        并行执行任务

        Args:
            task_ids: 任务ID列表（None表示所有任务）
            timeout: 超时时间

        Returns:
            执行结果字典
        """
        if task_ids is None:
            with self._lock:
                task_ids = list(self._tasks.keys())

        # 提交到线程池
        futures = {}
        for task_id in task_ids:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                future = self._executor.submit(task.run)
                futures[future] = task_id

        # 收集结果
        results = {}
        timeout = timeout or self._default_timeout

        for future in as_completed(futures, timeout=timeout):
            task_id = futures[future]
            try:
                result = future.result()
                results[task_id] = result
            except Exception as e:
                results[task_id] = SkillResult.error_result(str(e))

        return results

    # ========== 异步执行 ==========

    async def run_async(self, task_id: str) -> SkillResult:
        """
        异步执行任务

        Args:
            task_id: 任务ID

        Returns:
            执行结果
        """
        with self._lock:
            if task_id not in self._tasks:
                raise ValueError(f"任务不存在: {task_id}")

            task = self._tasks[task_id]

        self._emit("start", task.info)

        result = await task.run_async()

        if result.success:
            self._stats["completed"] += 1
        else:
            self._stats["failed"] += 1

        return result

    async def run_all_async(self) -> Dict[str, SkillResult]:
        """
        异步执行所有任务

        Returns:
            执行结果字典
        """
        with self._lock:
            task_ids = list(self._tasks.keys())

        tasks = [self.run_async(task_id) for task_id in task_ids]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for task_id, result in zip(task_ids, results_list):
            if isinstance(result, Exception):
                results[task_id] = SkillResult.error_result(str(result))
            else:
                results[task_id] = result

        return results

    # ========== 管道执行 ==========

    def run_pipeline(
        self,
        skill_names: List[str],
        initial_input: Any = None,
        context: Optional[SkillContext] = None
    ) -> SkillResult:
        """
        管道执行（前一个Skill的输出作为后一个Skill的输入）

        Args:
            skill_names: Skill名称列表
            initial_input: 初始输入
            context: 执行上下文

        Returns:
            最终结果
        """
        if context is None:
            context = SkillContext(registry=self._registry)

        current_data = initial_input

        for skill_name in skill_names:
            skill = self._registry.require(skill_name)

            # 将前一个输出作为输入
            params = {"input": current_data} if current_data is not None else {}

            result = skill.run(context, **params)

            if not result.success:
                return result

            current_data = result.data

        return SkillResult.success_result(data=current_data)

    # ========== 任务管理 ==========

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """
        获取任务信息

        Args:
            task_id: 任务ID

        Returns:
            任务信息或None
        """
        with self._lock:
            task = self._tasks.get(task_id)
            return task.info if task else None

    def cancel(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False

            if task.cancel():
                self._stats["cancelled"] += 1
                return True
            return False

    def cancel_all(self) -> int:
        """
        取消所有任务

        Returns:
            取消的任务数
        """
        cancelled = 0
        with self._lock:
            for task in self._tasks.values():
                if task.cancel():
                    cancelled += 1

        self._stats["cancelled"] += cancelled
        return cancelled

    def remove(self, task_id: str) -> bool:
        """
        移除任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功移除
        """
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    def clear(self) -> None:
        """清除所有任务"""
        with self._lock:
            self._tasks.clear()
            self._task_queue = PriorityQueue()

    # ========== 事件系统 ==========

    def on(self, event: str, callback: Callable) -> None:
        """
        注册事件监听器

        Args:
            event: 事件类型
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

    # ========== 统计信息 ==========

    @property
    def stats(self) -> Dict[str, Any]:
        """统计信息"""
        with self._lock:
            return {
                **self._stats,
                "pending": sum(
                    1 for t in self._tasks.values()
                    if t.info.status == TaskStatus.PENDING
                ),
                "running": sum(
                    1 for t in self._tasks.values()
                    if t.info.status == TaskStatus.RUNNING
                ),
                "completed": sum(
                    1 for t in self._tasks.values()
                    if t.info.status == TaskStatus.COMPLETED
                ),
                "failed": sum(
                    1 for t in self._tasks.values()
                    if t.info.status == TaskStatus.FAILED
                ),
                "total": len(self._tasks)
            }

    def get_all_tasks(self) -> List[TaskInfo]:
        """
        获取所有任务信息

        Returns:
            任务信息列表
        """
        with self._lock:
            return [task.info for task in self._tasks.values()]

    def shutdown(self, wait: bool = True) -> None:
        """
        关闭调度器

        Args:
            wait: 是否等待任务完成
        """
        self._executor.shutdown(wait=wait)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


class ExecutionPlan:
    """
    执行计划

    预定义的执行计划，支持复杂的执行流程。
    """

    def __init__(self, scheduler: SkillScheduler):
        self._scheduler = scheduler
        self._steps: List[Dict[str, Any]] = []

    def add_step(
        self,
        skill_name: str,
        params: Optional[Dict[str, Any]] = None,
        depends_on: Optional[List[int]] = None
    ) -> "ExecutionPlan":
        """
        添加执行步骤

        Args:
            skill_name: Skill名称
            params: 参数
            depends_on: 依赖的步骤索引

        Returns:
            自身（链式调用）
        """
        self._steps.append({
            "skill_name": skill_name,
            "params": params or {},
            "depends_on": depends_on or []
        })
        return self

    def execute(self, context: Optional[SkillContext] = None) -> List[SkillResult]:
        """
        执行计划

        Args:
            context: 执行上下文

        Returns:
            执行结果列表
        """
        if context is None:
            context = SkillContext(registry=self._scheduler._registry)

        results = []
        task_ids = []

        for i, step in enumerate(self._steps):
            # 获取依赖任务ID
            dep_ids = [task_ids[j] for j in step.get("depends_on", [])]

            # 提交任务
            task_id = self._scheduler.submit(
                step["skill_name"],
                step["params"],
                dependencies=dep_ids,
                context=context
            )
            task_ids.append(task_id)

            # 执行
            result = self._scheduler.run(task_id)
            results.append(result)

            # 如果失败，停止执行
            if not result.success:
                break

        return results
