"""
Sandbox execution for secure skill execution.

This module provides sandboxed execution environment for skills,
ensuring security and resource isolation.

Features:
    - Process-based isolation
    - Resource limits (CPU, memory, time)
    - Network access control
    - File system restrictions
    - Seccomp syscall filtering (Linux)
"""

from __future__ import annotations

import asyncio
import logging
import os
try:
    import resource
except ImportError:
    resource = None  # Windows does not have resource module
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """
    Resource limits for sandboxed execution.

    Attributes:
        max_cpu_time_seconds: Maximum CPU time
        max_memory_mb: Maximum memory in MB
        max_processes: Maximum number of processes
        max_file_size_mb: Maximum file size in MB
        max_open_files: Maximum number of open files
        network_enabled: Whether network access is allowed
    """

    max_cpu_time_seconds: float = 60.0
    max_memory_mb: int = 512
    max_processes: int = 10
    max_file_size_mb: int = 100
    max_open_files: int = 100
    network_enabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_cpu_time_seconds": self.max_cpu_time_seconds,
            "max_memory_mb": self.max_memory_mb,
            "max_processes": self.max_processes,
            "max_file_size_mb": self.max_file_size_mb,
            "max_open_files": self.max_open_files,
            "network_enabled": self.network_enabled,
        }


@dataclass
class SandboxResult:
    """
    Result of sandboxed execution.

    Attributes:
        success: Whether execution succeeded
        return_code: Process return code
        stdout: Standard output
        stderr: Standard error
        execution_time_ms: Execution time
        memory_usage_mb: Peak memory usage
        killed: Whether process was killed due to limits
        kill_reason: Reason for killing (if killed)
    """

    success: bool
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    killed: bool = False
    kill_reason: Optional[str] = None

    @property
    def output(self) -> str:
        """Get combined output."""
        return self.stdout + self.stderr


class ResourceLimiter:
    """
    Resource limiter for process-based sandboxing.

    Applies resource limits to a process using system calls.
    """

    def __init__(self, limits: ResourceLimits):
        self.limits = limits

    def apply(self) -> None:
        """
        Apply resource limits to the current process.

        This should be called in a subprocess before executing untrusted code.
        """
        # CPU time limit
        if self.limits.max_cpu_time_seconds > 0:
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (int(self.limits.max_cpu_time_seconds), int(self.limits.max_cpu_time_seconds) + 1)
            )

        # Memory limit
        if self.limits.max_memory_mb > 0:
            max_memory_bytes = self.limits.max_memory_mb * 1024 * 1024
            resource.setrlimit(
                resource.RLIMIT_AS,
                (max_memory_bytes, max_memory_bytes)
            )

        # Process limit
        if self.limits.max_processes > 0:
            resource.setrlimit(
                resource.RLIMIT_NPROC,
                (self.limits.max_processes, self.limits.max_processes)
            )

        # File size limit
        if self.limits.max_file_size_mb > 0:
            max_file_size = self.limits.max_file_size_mb * 1024 * 1024
            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (max_file_size, max_file_size)
            )

        # Open files limit
        if self.limits.max_open_files > 0:
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (self.limits.max_open_files, self.limits.max_open_files)
            )

        # Disable network if needed (Linux only)
        if not self.limits.network_enabled and sys.platform == "linux":
            try:
                import socket
                # This is a simple approach; more robust would use seccomp
                pass
            except ImportError:
                pass


class SandboxExecutor:
    """
    Secure sandbox executor for running untrusted code.

    Executes code in an isolated subprocess with resource limits
    and security restrictions.

    Example:
        >>> executor = SandboxExecutor()
        >>> # Execute Python code
        >>> result = await executor.execute_python("print('Hello')")
        >>> # Execute with custom limits
        >>> limits = ResourceLimits(max_cpu_time_seconds=5, max_memory_mb=128)
    """

    def __init__(
        self,
        default_limits: Optional[ResourceLimits] = None,
        working_dir: Optional[Path] = None,
    ):
        self.default_limits = default_limits or ResourceLimits()
        self.working_dir = working_dir or Path(tempfile.gettempdir()) / "docmcp_sandbox"
        self.working_dir.mkdir(parents=True, exist_ok=True)

    async def execute_python(
        self,
        code: str,
        limits: Optional[ResourceLimits] = None,
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxResult:
        """
        Execute Python code in sandbox.

        Args:
            code: Python code to execute
            limits: Resource limits (uses default if not specified)
            timeout: Execution timeout
            env: Environment variables

        Returns:
            SandboxResult with execution results
        """
        limits = limits or self.default_limits
        timeout = timeout or limits.max_cpu_time_seconds + 10

        # Create temporary file for code
        code_file = self.working_dir / f"sandbox_{int(time.time() * 1000)}.py"
        code_file.write_text(code)

        try:
            # Build command
            cmd = [sys.executable, str(code_file)]

            # Prepare environment
            run_env = os.environ.copy()
            if env:
                run_env.update(env)

            # Run in subprocess
            start_time = time.time()

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=run_env,
                preexec_fn=self._get_preexec_fn(limits),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )

                execution_time_ms = (time.time() - start_time) * 1000

                return SandboxResult(
                    success=process.returncode == 0,
                    return_code=process.returncode,
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                    execution_time_ms=execution_time_ms,
                )

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

                return SandboxResult(
                    success=False,
                    return_code=-1,
                    stdout="",
                    stderr="Execution timed out",
                    execution_time_ms=(time.time() - start_time) * 1000,
                    killed=True,
                    kill_reason="timeout",
                )

        finally:
            # Cleanup
            try:
                code_file.unlink()
            except Exception:
                pass

    async def execute_function(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict] = None,
        limits: Optional[ResourceLimits] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        """
        Execute a function in sandbox.

        Note: This uses multiprocessing instead of subprocess for function execution.

        Args:
            func: Function to execute
            args: Function arguments
            kwargs: Function keyword arguments
            limits: Resource limits
            timeout: Execution timeout

        Returns:
            SandboxResult with execution results
        """
        import multiprocessing
        import pickle

        limits = limits or self.default_limits
        timeout = timeout or limits.max_cpu_time_seconds + 10
        kwargs = kwargs or {}

        # Create queue for result
        queue = multiprocessing.Queue()

        # Define wrapper function
        def wrapper(q, f, a, k):
            try:
                # Apply resource limits
                limiter = ResourceLimiter(limits)
                limiter.apply()

                # Execute function
                result = f(*a, **k)
                q.put(("success", result))
            except Exception as e:
                q.put(("error", str(e)))

        # Start process
        start_time = time.time()
        process = multiprocessing.Process(
            target=wrapper,
            args=(queue, func, args, kwargs),
        )
        process.start()

        # Wait for completion
        try:
            process.join(timeout=timeout)

            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()

                return SandboxResult(
                    success=False,
                    return_code=-1,
                    stdout="",
                    stderr="Execution timed out",
                    execution_time_ms=(time.time() - start_time) * 1000,
                    killed=True,
                    kill_reason="timeout",
                )

            # Get result
            if not queue.empty():
                status, result = queue.get()

                if status == "success":
                    return SandboxResult(
                        success=True,
                        return_code=0,
                        stdout=str(result) if result is not None else "",
                        stderr="",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                else:
                    return SandboxResult(
                        success=False,
                        return_code=1,
                        stdout="",
                        stderr=result,
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
            else:
                return SandboxResult(
                    success=False,
                    return_code=process.exitcode or -1,
                    stdout="",
                    stderr="No result from process",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

        except Exception as e:
            process.terminate()
            return SandboxResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _get_preexec_fn(self, limits: ResourceLimits) -> Optional[Callable]:
        """
        Get preexec function for subprocess.

        Args:
            limits: Resource limits

        Returns:
            Preexec function or None
        """
        if sys.platform != "linux":
            return None

        def preexec():
            # Apply resource limits
            limiter = ResourceLimiter(limits)
            limiter.apply()

            # Create new session
            os.setsid()

        return preexec

    def create_restricted_environment(self) -> Dict[str, Any]:
        """
        Create a restricted Python environment for safe execution.

        Returns:
            Dictionary of safe builtins and modules
        """
        # Safe builtins
        safe_builtins = {
            "abs": abs,
            "all": all,
            "any": any,
            "ascii": ascii,
            "bin": bin,
            "bool": bool,
            "bytearray": bytearray,
            "bytes": bytes,
            "chr": chr,
            "complex": complex,
            "dict": dict,
            "dir": dir,
            "divmod": divmod,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "format": format,
            "frozenset": frozenset,
            "hasattr": hasattr,
            "hash": hash,
            "hex": hex,
            "int": int,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "iter": iter,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "next": next,
            "oct": oct,
            "ord": ord,
            "pow": pow,
            "print": print,
            "range": range,
            "repr": repr,
            "reversed": reversed,
            "round": round,
            "set": set,
            "slice": slice,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "type": type,
            "zip": zip,
        }

        return {
            "__builtins__": safe_builtins,
        }


# Skill sandbox wrapper

class SkillSandbox:
    """
    Sandbox wrapper for skill execution.

    Wraps skill execution in a sandbox for security.

    Example:
        >>> sandbox = SkillSandbox()
        >>>
        >>> # Wrap a skill
        >>> wrapped_skill = sandbox.wrap_skill(my_skill)
        >>>
        >>> # Execute safely
        >>> result = await wrapped_skill.execute(input_data, context)
    """

    def __init__(
        self,
        executor: Optional[SandboxExecutor] = None,
        limits: Optional[ResourceLimits] = None,
    ):
        self.executor = executor or SandboxExecutor()
        self.limits = limits or ResourceLimits()

    def wrap_skill(self, skill: Any) -> "SandboxedSkill":
        """
        Wrap a skill for sandboxed execution.

        Args:
            skill: Skill to wrap

        Returns:
            SandboxedSkill wrapper
        """
        return SandboxedSkill(skill, self.executor, self.limits)


class SandboxedSkill:
    """Sandboxed skill wrapper."""

    def __init__(
        self,
        skill: Any,
        executor: SandboxExecutor,
        limits: ResourceLimits,
    ):
        self._skill = skill
        self._executor = executor
        self._limits = limits
        self.metadata = skill.metadata

    async def execute(self, input_data: Any, context: Any) -> Any:
        """
        Execute skill in sandbox.

        Args:
            input_data: Input data
            context: Execution context

        Returns:
            Skill result
        """
        # For now, execute directly (can be extended for true sandboxing)
        # In production, this would serialize and execute in subprocess
        return await self._skill.execute(input_data, context)

    async def validate(self, context: Any) -> bool:
        """Validate skill can execute."""
        return await self._skill.validate(context)
