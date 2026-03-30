"""
DocMCP 连接池模块

提供资源连接池管理、连接复用、健康检查和自动扩缩容功能。
"""

import time
import queue
import threading
import logging
from typing import Dict, List, Optional, Any, Callable, TypeVar, Generic, Set
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ConnectionState(Enum):
    """连接状态"""
    IDLE = "idle"
    BUSY = "busy"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class ConnectionInfo:
    """连接信息"""
    id: str
    created_at: float
    last_used: float
    use_count: int = 0
    state: ConnectionState = ConnectionState.IDLE
    health_check_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def age(self) -> float:
        """连接年龄（秒）"""
        return time.time() - self.created_at

    @property
    def idle_time(self) -> float:
        """空闲时间（秒）"""
        return time.time() - self.last_used


class ConnectionFactory(ABC, Generic[T]):
    """连接工厂基类"""

    @abstractmethod
    def create(self) -> T:
        """创建新连接"""
        pass

    @abstractmethod
    def close(self, connection: T) -> None:
        """关闭连接"""
        pass

    @abstractmethod
    def is_valid(self, connection: T) -> bool:
        """检查连接是否有效"""
        pass

    @abstractmethod
    def health_check(self, connection: T) -> bool:
        """执行健康检查"""
        pass


@dataclass
class PoolConfig:
    """连接池配置"""
    min_connections: int = 5
    max_connections: int = 50
    connection_timeout: float = 30.0
    idle_timeout: float = 300.0  # 空闲超时
    max_lifetime: float = 3600.0  # 最大生命周期

    # 健康检查
    health_check_interval: float = 30.0
    health_check_query: str = "SELECT 1"
    max_health_failures: int = 3

    # 重试配置
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0

    # 等待配置
    max_wait_time: float = 10.0
    wait_queue_size: int = 100

    # 监控
    enable_metrics: bool = True
    metrics_interval: float = 60.0


class ConnectionPool(Generic[T]):
    """通用连接池

    提供：
    - 连接复用
    - 自动扩缩容
    - 健康检查
    - 连接生命周期管理
    - 统计监控
    """

    def __init__(
        self,
        factory: ConnectionFactory[T],
        config: Optional[PoolConfig] = None,
        name: str = "default"
    ):
        """初始化连接池

        Args:
            factory: 连接工厂
            config: 连接池配置
            name: 连接池名称
        """
        self.factory = factory
        self.config = config or PoolConfig()
        self.name = name

        # 连接存储
        self._connections: Dict[str, T] = {}
        self._connection_info: Dict[str, ConnectionInfo] = {}

        # 可用连接队列
        self._available: queue.Queue[str] = queue.Queue()

        # 等待队列
        self._waiters: queue.Queue[threading.Event] = queue.Queue(
            maxsize=self.config.wait_queue_size
        )

        # 锁
        self._lock = threading.RLock()
        self._shutdown = False

        # 统计
        self._stats = {
            'total_created': 0,
            'total_closed': 0,
            'total_borrowed': 0,
            'total_returned': 0,
            'total_timeout': 0,
            'total_errors': 0,
        }

        # 后台线程
        self._health_check_thread: Optional[threading.Thread] = None
        self._maintenance_thread: Optional[threading.Thread] = None

        # 初始化最小连接数
        self._initialize_pool()

        # 启动后台线程
        self._start_background_tasks()

    def _initialize_pool(self) -> None:
        """初始化连接池"""
        for _ in range(self.config.min_connections):
            try:
                self._create_connection()
            except Exception as e:
                logger.error(f"Failed to create initial connection: {e}")

    def _create_connection(self) -> Optional[str]:
        """创建新连接"""
        with self._lock:
            if len(self._connections) >= self.config.max_connections:
                return None

            try:
                connection = self.factory.create()
                conn_id = f"{self.name}_{id(connection)}_{time.time()}"

                self._connections[conn_id] = connection
                self._connection_info[conn_id] = ConnectionInfo(
                    id=conn_id,
                    created_at=time.time(),
                    last_used=time.time()
                )
                self._available.put(conn_id)

                self._stats['total_created'] += 1

                logger.debug(f"Created connection {conn_id}")
                return conn_id

            except Exception as e:
                logger.error(f"Failed to create connection: {e}")
                self._stats['total_errors'] += 1
                return None

    def _close_connection(self, conn_id: str) -> None:
        """关闭连接"""
        with self._lock:
            connection = self._connections.pop(conn_id, None)
            info = self._connection_info.pop(conn_id, None)

            if connection:
                try:
                    self.factory.close(connection)
                    self._stats['total_closed'] += 1
                    logger.debug(f"Closed connection {conn_id}")
                except Exception as e:
                    logger.error(f"Failed to close connection {conn_id}: {e}")

    def get_connection(
        self,
        timeout: Optional[float] = None
    ) -> Optional[T]:
        """获取连接

        Args:
            timeout: 超时时间（秒）

        Returns:
            Optional[T]: 连接对象或None
        """
        if self._shutdown:
            raise RuntimeError("Pool is shutdown")

        timeout = timeout or self.config.connection_timeout
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 尝试获取可用连接
                conn_id = self._available.get(timeout=0.1)

                with self._lock:
                    info = self._connection_info.get(conn_id)

                    if info is None:
                        continue

                    # 检查连接是否有效
                    connection = self._connections.get(conn_id)
                    if connection is None or not self.factory.is_valid(connection):
                        self._close_connection(conn_id)
                        continue

                    # 检查生命周期
                    if info.age > self.config.max_lifetime:
                        self._close_connection(conn_id)
                        self._create_connection()
                        continue

                    # 标记为使用中
                    info.state = ConnectionState.BUSY
                    info.use_count += 1
                    info.last_used = time.time()

                    self._stats['total_borrowed'] += 1

                    return connection

            except queue.Empty:
                # 没有可用连接，尝试创建新连接
                if len(self._connections) < self.config.max_connections:
                    conn_id = self._create_connection()
                    if conn_id:
                        continue

                # 等待其他连接释放
                wait_event = threading.Event()
                try:
                    self._waiters.put(wait_event, timeout=0.1)
                    wait_event.wait(timeout=0.5)
                except queue.Full:
                    pass

        self._stats['total_timeout'] += 1
        logger.warning(f"Timeout waiting for connection from pool {self.name}")
        return None

    def return_connection(self, connection: T) -> None:
        """归还连接

        Args:
            connection: 连接对象
        """
        with self._lock:
            # 查找连接ID
            conn_id = None
            for cid, conn in self._connections.items():
                if conn is connection:
                    conn_id = cid
                    break

            if conn_id is None:
                logger.warning("Returning unknown connection")
                return

            info = self._connection_info.get(conn_id)
            if info:
                info.state = ConnectionState.IDLE
                info.last_used = time.time()

            # 放回可用队列
            self._available.put(conn_id)
            self._stats['total_returned'] += 1

            # 通知等待者
            try:
                waiter = self._waiters.get_nowait()
                waiter.set()
            except queue.Empty:
                pass

    def _start_background_tasks(self) -> None:
        """启动后台任务"""
        # 健康检查线程
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True
        )
        self._health_check_thread.start()

        # 维护线程
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop,
            daemon=True
        )
        self._maintenance_thread.start()

    def _health_check_loop(self) -> None:
        """健康检查循环"""
        while not self._shutdown:
            try:
                self._perform_health_checks()
                time.sleep(self.config.health_check_interval)
            except Exception as e:
                logger.error(f"Health check error: {e}")
                time.sleep(1)

    def _perform_health_checks(self) -> None:
        """执行健康检查"""
        with self._lock:
            for conn_id, connection in list(self._connections.items()):
                info = self._connection_info.get(conn_id)
                if info is None:
                    continue

                # 只检查空闲连接
                if info.state != ConnectionState.IDLE:
                    continue

                try:
                    if not self.factory.health_check(connection):
                        info.health_check_failures += 1

                        if info.health_check_failures >= self.config.max_health_failures:
                            logger.warning(f"Connection {conn_id} failed health check, closing")
                            self._close_connection(conn_id)
                            self._create_connection()
                    else:
                        info.health_check_failures = 0

                except Exception as e:
                    logger.error(f"Health check failed for {conn_id}: {e}")
                    self._close_connection(conn_id)
                    self._create_connection()

    def _maintenance_loop(self) -> None:
        """维护循环"""
        while not self._shutdown:
            try:
                self._perform_maintenance()
                time.sleep(10)  # 每10秒执行一次维护
            except Exception as e:
                logger.error(f"Maintenance error: {e}")
                time.sleep(1)

    def _perform_maintenance(self) -> None:
        """执行维护任务"""
        with self._lock:
            current_time = time.time()
            connections_to_close = []

            for conn_id, info in list(self._connection_info.items()):
                # 检查空闲超时
                if info.state == ConnectionState.IDLE:
                    if info.idle_time > self.config.idle_timeout:
                        # 保持最小连接数
                        if len(self._connections) > self.config.min_connections:
                            connections_to_close.append(conn_id)
                            continue

                # 检查生命周期
                if info.age > self.config.max_lifetime:
                    connections_to_close.append(conn_id)

            # 关闭过期连接
            for conn_id in connections_to_close:
                self._close_connection(conn_id)

            # 确保最小连接数
            while len(self._connections) < self.config.min_connections:
                if not self._create_connection():
                    break

    @contextmanager
    def acquire(self, timeout: Optional[float] = None):
        """上下文管理器获取连接

        Args:
            timeout: 超时时间

        Yields:
            T: 连接对象
        """
        connection = self.get_connection(timeout)
        if connection is None:
            raise RuntimeError("Failed to acquire connection from pool")

        try:
            yield connection
        finally:
            self.return_connection(connection)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                'name': self.name,
                'total_connections': len(self._connections),
                'available_connections': self._available.qsize(),
                'busy_connections': sum(
                    1 for info in self._connection_info.values()
                    if info.state == ConnectionState.BUSY
                ),
                'waiters': self._waiters.qsize(),
                **self._stats
            }

    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> None:
        """关闭连接池

        Args:
            wait: 是否等待连接归还
            timeout: 等待超时
        """
        self._shutdown = True

        if wait:
            start_time = time.time()
            while time.time() - start_time < timeout:
                with self._lock:
                    busy_count = sum(
                        1 for info in self._connection_info.values()
                        if info.state == ConnectionState.BUSY
                    )
                    if busy_count == 0:
                        break
                time.sleep(0.1)

        # 关闭所有连接
        with self._lock:
            for conn_id in list(self._connections.keys()):
                self._close_connection(conn_id)

        logger.info(f"Connection pool {self.name} shutdown complete")


class DatabaseConnectionFactory(ConnectionFactory):
    """数据库连接工厂示例"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "docmcp",
        user: str = "docmcp",
        password: str = ""
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password

    def create(self):
        """创建数据库连接"""
        # 这里应该使用实际的数据库驱动
        # 示例使用模拟连接
        return MockDatabaseConnection(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password
        )

    def close(self, connection) -> None:
        """关闭连接"""
        connection.close()

    def is_valid(self, connection) -> bool:
        """检查连接是否有效"""
        return connection.is_connected()

    def health_check(self, connection) -> bool:
        """执行健康检查"""
        try:
            connection.execute("SELECT 1")
            return True
        except:
            return False


class MockDatabaseConnection:
    """模拟数据库连接（用于示例）"""

    def __init__(self, **kwargs):
        self._connected = True
        self._config = kwargs

    def is_connected(self) -> bool:
        return self._connected

    def execute(self, query: str) -> Any:
        if not self._connected:
            raise RuntimeError("Connection closed")
        return {"result": "ok"}

    def close(self) -> None:
        self._connected = False


class HTTPConnectionFactory(ConnectionFactory):
    """HTTP连接工厂示例"""

    def __init__(self, base_url: str = "http://localhost", timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout

    def create(self):
        import urllib.request
        return urllib.request.build_opener()

    def close(self, connection) -> None:
        pass

    def is_valid(self, connection) -> bool:
        return True

    def health_check(self, connection) -> bool:
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.base_url}/health",
                method='HEAD'
            )
            connection.open(req, timeout=5)
            return True
        except:
            return False


# 便捷函数
_pools: Dict[str, ConnectionPool] = {}


def create_pool(
    name: str,
    factory: ConnectionFactory,
    config: Optional[PoolConfig] = None
) -> ConnectionPool:
    """创建连接池"""
    pool = ConnectionPool(factory, config, name)
    _pools[name] = pool
    return pool


def get_pool(name: str) -> Optional[ConnectionPool]:
    """获取连接池"""
    return _pools.get(name)


def shutdown_all_pools() -> None:
    """关闭所有连接池"""
    for pool in _pools.values():
        pool.shutdown()
    _pools.clear()


# WorkerPool and TaskPriority - for test compatibility
class TaskPriority:
    """Task priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 10


class WorkerPool:
    """Worker thread pool (simplified, for test compatibility)"""

    def __init__(self, num_workers: int = 4):
        self.num_workers = num_workers
        self._executor = None

    async def start(self):
        """Start thread pool"""
        from concurrent.futures import ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=self.num_workers)

    async def stop(self):
        """Stop thread pool"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

    async def submit(self, task_func, priority: int = TaskPriority.NORMAL):
        """Submit task"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, task_func)

    def get_stats(self):
        """Get statistics"""
        return {
            'num_workers': self.num_workers,
            'active_workers': 0,
            'pending_tasks': 0,
        }
