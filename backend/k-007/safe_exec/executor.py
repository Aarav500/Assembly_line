import os
import subprocess
import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional


MAX_STDOUT_BYTES = 64 * 1024  # 64KiB per stream
DEFAULT_ENV = {
    "LANG": "C",
    "LC_ALL": "C",
}


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool
    duration_ms: int


class ExecutionError(Exception):
    def __init__(self, public_message: str, http_status: int = 400, details: Optional[Dict] = None):
        super().__init__(public_message)
        self.public_message = public_message
        self.http_status = http_status
        self.details = details or {}


def _apply_resource_limits():
    try:
        import resource
        # CPU seconds
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        # Max address space ~256MB
        mem_bytes = 256 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        # Max files
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        # Disable core dumps
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except Exception:
        # Resource limits may not be supported on this platform; continue without them
        pass


class SafeExecutor:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def run(self, exec_path: str, args: list, cwd: Optional[str], timeout_seconds: int) -> ExecutionResult:
        if not isinstance(args, list) or not args:
            raise ExecutionError("Executor misconfiguration: args must be non-empty list", http_status=500)
        if args[0] != exec_path:
            raise ExecutionError("Executor safety mismatch: first arg must be exec_path", http_status=500)
        if not os.path.isabs(exec_path):
            raise ExecutionError("Executor requires absolute exec_path", http_status=500)

        env = dict(DEFAULT_ENV)
        # Do not inherit parent env to reduce attack surface

        start = time.time()
        timed_out = False
        truncated = False

        try:
            proc = subprocess.Popen(
                args,
                cwd=cwd or None,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,  # capture as bytes then decode safely
                shell=False,
                preexec_fn=_apply_resource_limits,
            )
            try:
                out_b, err_b = proc.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                out_b, err_b = proc.communicate()
        except FileNotFoundError:
            raise ExecutionError("Executable not found", http_status=500)
        except PermissionError:
            raise ExecutionError("Permission denied executing command", http_status=500)
        except OSError as oe:
            raise ExecutionError("OS error during execution", http_status=500, details={"errno": getattr(oe, "errno", None)})

        duration_ms = int((time.time() - start) * 1000)

        # Truncate outputs
        if len(out_b) > MAX_STDOUT_BYTES:
            out_b = out_b[:MAX_STDOUT_BYTES]
            truncated = True
        if len(err_b) > MAX_STDOUT_BYTES:
            err_b = err_b[:MAX_STDOUT_BYTES]
            truncated = True

        # Decode as UTF-8 with replacement
        stdout = out_b.decode("utf-8", errors="replace") if out_b is not None else ""
        stderr = err_b.decode("utf-8", errors="replace") if err_b is not None else ""

        return ExecutionResult(
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            truncated=truncated,
            duration_ms=duration_ms,
        )

