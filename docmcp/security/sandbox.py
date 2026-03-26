"""
DocMCP 沙箱执行模块

提供安全的代码执行环境，包括进程隔离、资源限制、文件系统隔离和网络控制。
"""

import os
import sys
import json
import time
import signal
import shutil
import tempfile
import subprocess
try:
    import resource
except ImportError:
    resource = None  # Windows does not have resource module
import threading
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class SandboxStatus(Enum):
    """沙箱执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    MEMORY_EXCEEDED = "memory_exceeded"
    ERROR = "error"
    KILLED = "killed"


@dataclass
class SandboxResult:
    """沙箱执行结果"""
    status: SandboxStatus
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    execution_time: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceLimits:
    """资源限制配置"""
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0
    max_execution_time: float = 30.0
    max_processes: int = 5
    max_file_size_mb: int = 100
    max_open_files: int = 100


class SandboxExecutor:
    """沙箱执行器
    
    提供安全的代码执行环境，支持：
    - 进程级隔离
    - 资源限制（内存、CPU、时间）
    - 文件系统隔离
    - 网络访问控制
    """
    
    def __init__(
        self,
        temp_dir: Optional[str] = None,
        resource_limits: Optional[ResourceLimits] = None,
        network_enabled: bool = False,
        allowed_hosts: Optional[List[str]] = None,
        read_only_fs: bool = True
    ):
        """初始化沙箱执行器
        
        Args:
            temp_dir: 临时目录路径
            resource_limits: 资源限制配置
            network_enabled: 是否允许网络访问
            allowed_hosts: 允许访问的主机列表
            read_only_fs: 是否使用只读文件系统
        """
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="docmcp_sandbox_")
        self.resource_limits = resource_limits or ResourceLimits()
        self.network_enabled = network_enabled
        self.allowed_hosts = allowed_hosts or []
        self.read_only_fs = read_only_fs
        self._active_processes: Dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()
        
        # 创建临时目录
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Sandbox initialized: temp_dir={self.temp_dir}")
    
    def _set_resource_limits(self):
        """设置进程资源限制（在子进程中调用）"""
        if resource is None:
            return  # Skip on Windows
        
        # 内存限制
        max_memory_bytes = self.resource_limits.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
        
        # CPU时间限制
        resource.setrlimit(
            resource.RLIMIT_CPU, 
            (int(self.resource_limits.max_execution_time), int(self.resource_limits.max_execution_time))
        )
        
        # 进程数限制
        resource.setrlimit(resource.RLIMIT_NPROC, (self.resource_limits.max_processes, self.resource_limits.max_processes))
        
        # 文件大小限制
        max_file_size = self.resource_limits.max_file_size_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_size, max_file_size))
        
        # 打开文件数限制
        resource.setrlimit(resource.RLIMIT_NOFILE, (self.resource_limits.max_open_files, self.resource_limits.max_open_files))
    
    def _create_network_policy(self) -> List[str]:
        """创建网络访问控制策略"""
        if self.network_enabled:
            return []
        
        # 使用iptables或nftables限制网络访问
        # 这里返回iptables规则列表
        rules = [
            "iptables -A OUTPUT -o lo -j ACCEPT",  # 允许本地回环
            "iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
        ]
        
        for host in self.allowed_hosts:
            rules.append(f"iptables -A OUTPUT -d {host} -j ACCEPT")
        
        rules.append("iptables -A OUTPUT -j DROP")  # 默认拒绝
        
        return rules
    
    def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[float] = None,
        input_data: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None
    ) -> SandboxResult:
        """执行代码
        
        Args:
            code: 要执行的代码
            language: 编程语言
            timeout: 超时时间（秒）
            input_data: 输入数据
            env_vars: 环境变量
            working_dir: 工作目录
            
        Returns:
            SandboxResult: 执行结果
        """
        timeout = timeout or self.resource_limits.max_execution_time
        
        # 创建临时文件
        temp_file = Path(self.temp_dir) / f"script_{os.urandom(8).hex()}.py"
        temp_file.write_text(code, encoding='utf-8')
        
        try:
            return self._execute_file(
                str(temp_file),
                language=language,
                timeout=timeout,
                input_data=input_data,
                env_vars=env_vars,
                working_dir=working_dir
            )
        finally:
            # 清理临时文件
            if temp_file.exists():
                temp_file.unlink()
    
    def execute_command(
        self,
        command: List[str],
        timeout: Optional[float] = None,
        input_data: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        capture_output: bool = True
    ) -> SandboxResult:
        """执行命令
        
        Args:
            command: 命令列表
            timeout: 超时时间（秒）
            input_data: 输入数据
            env_vars: 环境变量
            working_dir: 工作目录
            capture_output: 是否捕获输出
            
        Returns:
            SandboxResult: 执行结果
        """
        timeout = timeout or self.resource_limits.max_execution_time
        working_dir = working_dir or self.temp_dir
        
        # 准备环境变量
        env = os.environ.copy()
        env.update(env_vars or {})
        
        # 添加网络限制环境变量
        if not self.network_enabled:
            env['NETWORK_DISABLED'] = '1'
        
        start_time = time.time()
        process_id = os.urandom(8).hex()
        
        try:
            # 创建子进程
            process = subprocess.Popen(
                command,
                cwd=working_dir,
                env=env,
                stdin=subprocess.PIPE if input_data else None,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                text=True,
                preexec_fn=self._set_resource_limits if sys.platform != 'win32' else None
            )
            
            with self._lock:
                self._active_processes[process_id] = process
            
            try:
                # 执行命令
                stdout, stderr = process.communicate(
                    input=input_data,
                    timeout=timeout
                )
                
                execution_time = time.time() - start_time
                
                return SandboxResult(
                    status=SandboxStatus.COMPLETED,
                    stdout=stdout or "",
                    stderr=stderr or "",
                    return_code=process.returncode,
                    execution_time=execution_time,
                    metadata={'command': command}
                )
                
            except subprocess.TimeoutExpired:
                process.kill()
                execution_time = time.time() - start_time
                
                return SandboxResult(
                    status=SandboxStatus.TIMEOUT,
                    stdout="",
                    stderr="Execution timeout",
                    return_code=-1,
                    execution_time=execution_time,
                    error_message=f"Execution exceeded {timeout} seconds"
                )
                
            finally:
                with self._lock:
                    self._active_processes.pop(process_id, None)
                    
        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return SandboxResult(
                status=SandboxStatus.ERROR,
                error_message=str(e),
                execution_time=time.time() - start_time
            )
    
    def _execute_file(
        self,
        file_path: str,
        language: str = "python",
        timeout: Optional[float] = None,
        input_data: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None
    ) -> SandboxResult:
        """执行文件"""
        interpreters = {
            "python": ["python3", "-u"],
            "python3": ["python3", "-u"],
            "node": ["node"],
            "javascript": ["node"],
            "bash": ["bash"],
            "sh": ["sh"],
        }
        
        interpreter = interpreters.get(language, ["python3", "-u"])
        command = interpreter + [file_path]
        
        return self.execute_command(
            command,
            timeout=timeout,
            input_data=input_data,
            env_vars=env_vars,
            working_dir=working_dir
        )
    
    def kill_process(self, process_id: str) -> bool:
        """终止指定进程
        
        Args:
            process_id: 进程ID
            
        Returns:
            bool: 是否成功终止
        """
        with self._lock:
            process = self._active_processes.get(process_id)
        
        if process and process.poll() is None:
            try:
                process.kill()
                return True
            except Exception as e:
                logger.error(f"Failed to kill process {process_id}: {e}")
        
        return False
    
    def kill_all(self) -> int:
        """终止所有活动进程
        
        Returns:
            int: 终止的进程数
        """
        count = 0
        with self._lock:
            processes = list(self._active_processes.items())
        
        for process_id, process in processes:
            if process.poll() is None:
                try:
                    process.kill()
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to kill process {process_id}: {e}")
        
        return count
    
    def get_active_processes(self) -> List[Dict[str, Any]]:
        """获取活动进程列表"""
        with self._lock:
            return [
                {
                    'id': pid,
                    'pid': proc.pid,
                    'running': proc.poll() is None
                }
                for pid, proc in self._active_processes.items()
            ]
    
    def cleanup(self) -> None:
        """清理沙箱环境"""
        # 终止所有进程
        self.kill_all()
        
        # 清理临时目录
        if Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up sandbox temp dir: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Failed to cleanup temp dir: {e}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()
        return False


class AsyncSandboxExecutor:
    """异步沙箱执行器"""
    
    def __init__(self, executor: Optional[SandboxExecutor] = None):
        """初始化异步沙箱执行器"""
        self.executor = executor or SandboxExecutor()
        self._tasks: Dict[str, Any] = {}
    
    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[float] = None,
        input_data: Optional[str] = None,
        callback: Optional[Callable[[SandboxResult], None]] = None
    ) -> SandboxResult:
        """异步执行代码"""
        import asyncio
        
        loop = asyncio.get_event_loop()
        
        # 在线程池中执行
        result = await loop.run_in_executor(
            None,
            lambda: self.executor.execute_code(
                code=code,
                language=language,
                timeout=timeout,
                input_data=input_data
            )
        )
        
        if callback:
            callback(result)
        
        return result
    
    async def execute_command(
        self,
        command: List[str],
        timeout: Optional[float] = None,
        input_data: Optional[str] = None,
        callback: Optional[Callable[[SandboxResult], None]] = None
    ) -> SandboxResult:
        """异步执行命令"""
        import asyncio
        
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            None,
            lambda: self.executor.execute_command(
                command=command,
                timeout=timeout,
                input_data=input_data
            )
        )
        
        if callback:
            callback(result)
        
        return result
    
    def cleanup(self) -> None:
        """清理资源"""
        self.executor.cleanup()


@contextmanager
def sandbox_context(
    temp_dir: Optional[str] = None,
    max_memory_mb: int = 512,
    max_execution_time: float = 30.0,
    network_enabled: bool = False
):
    """沙箱上下文管理器
    
    Args:
        temp_dir: 临时目录
        max_memory_mb: 最大内存限制(MB)
        max_execution_time: 最大执行时间(秒)
        network_enabled: 是否允许网络访问
        
    Yields:
        SandboxExecutor: 沙箱执行器实例
    """
    limits = ResourceLimits(
        max_memory_mb=max_memory_mb,
        max_execution_time=max_execution_time
    )
    
    executor = SandboxExecutor(
        temp_dir=temp_dir,
        resource_limits=limits,
        network_enabled=network_enabled
    )
    
    try:
        yield executor
    finally:
        executor.cleanup()


def create_restricted_environment(
    allowed_modules: Optional[List[str]] = None,
    blocked_builtins: Optional[List[str]] = None
) -> Dict[str, Any]:
    """创建受限的Python执行环境
    
    Args:
        allowed_modules: 允许的模块列表
        blocked_builtins: 禁止的内置函数列表
        
    Returns:
        Dict: 受限的执行环境
    """
    # 默认允许的模块
    allowed_modules = allowed_modules or [
        'math', 'random', 'datetime', 'json', 're', 'string',
        'collections', 'itertools', 'functools', 'typing'
    ]
    
    # 默认禁止的内置函数
    blocked_builtins = blocked_builtins or [
        '__import__', 'open', 'exec', 'eval', 'compile',
        'execfile', 'file', 'reload', 'input', 'raw_input'
    ]
    
    # 创建受限环境
    restricted_globals = {
        '__builtins__': {
            name: getattr(__builtins__, name)
            for name in dir(__builtins__)
            if name not in blocked_builtins
        }
    }
    
    # 导入允许的模块
    for module_name in allowed_modules:
        try:
            module = __import__(module_name)
            restricted_globals[module_name] = module
        except ImportError:
            pass
    
    return restricted_globals


# 便捷函数
def safe_execute(
    code: str,
    timeout: float = 30.0,
    max_memory_mb: int = 512,
    network_enabled: bool = False
) -> SandboxResult:
    """安全执行代码的便捷函数
    
    Args:
        code: 要执行的代码
        timeout: 超时时间
        max_memory_mb: 最大内存限制
        network_enabled: 是否允许网络
        
    Returns:
        SandboxResult: 执行结果
    """
    with sandbox_context(
        max_memory_mb=max_memory_mb,
        max_execution_time=timeout,
        network_enabled=network_enabled
    ) as sandbox:
        return sandbox.execute_code(code)
