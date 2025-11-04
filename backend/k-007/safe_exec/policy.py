import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


SAFE_PRINTABLE_RE = re.compile(r"^[\w\-\.@#:\/\s\[\]\(\),=+]*$")


def _is_safe_relative_path(value: str) -> bool:
    if os.path.isabs(value):
        return False
    # Normalize and ensure no parent traversal or null bytes
    if "\x00" in value:
        return False
    norm = os.path.normpath(value)
    if norm.startswith(".."):
        return False
    # Disallow bizarre parts
    parts = [p for p in norm.split(os.sep) if p and p != "."]
    return all(p not in ("..",) for p in parts)


def _is_safe_under_allowed_paths(value: str, allowed: List[str]) -> bool:
    if "\x00" in value:
        return False
    try:
        real_value = os.path.realpath(value)
    except Exception:
        return False
    for base in allowed:
        try:
            real_base = os.path.realpath(base)
        except Exception:
            continue
        # Ensure trailing sep for prefix check safety
        if os.path.commonpath([real_base]) == os.path.commonpath([real_base, real_value]):
            return True
    return False


def _is_safe_string(value: str, max_len: int = 256) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) > max_len:
        return False
    if "\x00" in value:
        return False
    # Only allow common safe printable set
    return bool(SAFE_PRINTABLE_RE.match(value))


@dataclass
class CommandSpec:
    exec_path: str
    exec_args: List[str]
    working_dir: Optional[str]
    timeout_seconds: int


class SafeExecPolicy:
    def __init__(self, allowed_commands: Dict[str, dict], default_timeout_seconds: int = 5,
                 allowed_working_dirs: Optional[List[str]] = None):
        self.allowed_commands = allowed_commands
        self.default_timeout_seconds = default_timeout_seconds
        self.allowed_working_dirs = allowed_working_dirs or ["/tmp", "/var/tmp"]

    def describe(self) -> Dict[str, dict]:
        # Return a redacted view of the policy to clients
        described = {}
        for name, spec in self.allowed_commands.items():
            described[name] = {
                "flags": list(spec.get("args", {}).get("flags", [])),
                "max_positionals": spec.get("args", {}).get("positional", {}).get("max", 0),
                "positional_policy": {
                    k: v for k, v in spec.get("args", {}).get("positional", {}).items()
                    if k in ("allow_any_string", "allow_relative", "allow_paths", "patterns", "max")
                },
                "timeout_seconds": spec.get("timeout_seconds", self.default_timeout_seconds),
            }
        return {
            "allowed_commands": described,
            "allowed_working_dirs": list(self.allowed_working_dirs),
            "default_timeout_seconds": self.default_timeout_seconds,
        }

    def validate(self, command: str, args: List[str], working_dir: Optional[str] = None) -> CommandSpec:
        if command not in self.allowed_commands:
            raise ValueError(f"Command '{command}' is not allowed")

        cmd_spec = self.allowed_commands[command]
        exec_path = cmd_spec.get("path")
        if not exec_path or not os.path.isabs(exec_path):
            raise ValueError("Misconfigured policy for command: missing absolute exec path")
        if not os.path.exists(exec_path) or not os.access(exec_path, os.X_OK):
            raise ValueError("Configured executable is not present or not executable")

        # Working directory validation
        normalized_cwd = None
        if working_dir is not None:
            if not isinstance(working_dir, str) or not working_dir:
                raise ValueError("Invalid working_dir")
            if not _is_safe_under_allowed_paths(working_dir, self.allowed_working_dirs):
                raise ValueError("Working directory is not permitted by policy")
            normalized_cwd = os.path.realpath(working_dir)

        allowed_flags = set(cmd_spec.get("args", {}).get("flags", []))
        pos_cfg = cmd_spec.get("args", {}).get("positional", {})
        max_pos = int(pos_cfg.get("max", 0))

        exec_args: List[str] = [exec_path]
        flags_seen: List[str] = []
        positionals: List[str] = []

        for a in args:
            if not isinstance(a, str) or "\x00" in a:
                raise ValueError("Invalid argument type or contains null byte")
            if a.startswith("-"):
                # flags must match allowed exactly
                if a not in allowed_flags:
                    raise ValueError(f"Flag not allowed: {a}")
                flags_seen.append(a)
            else:
                # positional handling based on policy
                if max_pos <= 0:
                    raise ValueError("No positional arguments allowed for this command")

                allow_any = bool(pos_cfg.get("allow_any_string", False))
                allow_rel = bool(pos_cfg.get("allow_relative", False))
                allow_paths = list(pos_cfg.get("allow_paths", []))
                patterns = [re.compile(p) for p in pos_cfg.get("patterns", [])]

                ok = False
                if allow_any and _is_safe_string(a, 256):
                    ok = True
                if not ok and allow_rel and _is_safe_relative_path(a):
                    ok = True
                if not ok and allow_paths and os.path.isabs(a) and _is_safe_under_allowed_paths(a, allow_paths):
                    ok = True
                if not ok and patterns:
                    ok = any(p.fullmatch(a) is not None for p in patterns)

                if not ok:
                    raise ValueError("Positional argument not permitted by policy")

                positionals.append(a)
                if len(positionals) > max_pos:
                    raise ValueError("Too many positional arguments for this command")

        exec_args.extend(flags_seen)
        exec_args.extend(positionals)

        timeout_seconds = int(cmd_spec.get("timeout_seconds", self.default_timeout_seconds))
        if timeout_seconds <= 0 or timeout_seconds > 30:
            # Enforce a reasonable upper bound regardless of config
            timeout_seconds = min(max(timeout_seconds, 1), 30)

        return CommandSpec(exec_path=exec_path, exec_args=exec_args, working_dir=normalized_cwd, timeout_seconds=timeout_seconds)


def load_default_policy() -> SafeExecPolicy:
    # Default policy: adjust paths as needed for your system
    allowed_commands = {
        "ls": {
            "path": "/bin/ls",
            "args": {
                "flags": ["-l", "-a", "-h", "--color=auto"],
                "positional": {
                    "allow_relative": True,
                    "allow_paths": ["/tmp", "/var/log", "/var/tmp"],
                    "max": 2,
                },
            },
            "timeout_seconds": 5,
        },
        "echo": {
            "path": "/bin/echo",
            "args": {
                "flags": [],
                "positional": {
                    "allow_any_string": True,
                    "max": 10,
                },
            },
            "timeout_seconds": 3,
        },
        "grep": {
            "path": "/bin/grep",
            "args": {
                "flags": ["-i", "-n", "-r", "-w"],
                "positional": {
                    # Simple alnum/._- patterns for token args (e.g., pattern, filename)
                    "patterns": [r"^[A-Za-z0-9._\-]+$"],
                    "max": 2,
                },
            },
            "timeout_seconds": 5,
        },
    }
    allowed_working_dirs = ["/tmp", "/var/tmp"]
    return SafeExecPolicy(allowed_commands=allowed_commands, allowed_working_dirs=allowed_working_dirs)

