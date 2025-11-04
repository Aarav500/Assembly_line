from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class CheckResult:
    id: str
    title: str
    category: str
    severity: str  # low|medium|high
    status: str  # pass|fail|skipped
    message: str
    remediation: str
    references: List[str]
    applicable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def bool_flag(d: Dict[str, Any], path: str, default: bool = False) -> bool:
    cur: Any = d
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return bool(cur)


def str_value(d: Dict[str, Any], path: str, default: str = "") -> str:
    cur: Any = d
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return str(cur)


def int_value(d: Dict[str, Any], path: str, default: int = 0) -> int:
    cur: Any = d
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    try:
        return int(cur)
    except Exception:
        return default


def mark_pass(id: str, title: str, category: str, severity: str, message: str, references=None) -> Dict[str, Any]:
    return CheckResult(
        id=id,
        title=title,
        category=category,
        severity=severity,
        status="pass",
        message=message,
        remediation="",
        references=references or [],
        applicable=True,
    ).to_dict()


def mark_fail(id: str, title: str, category: str, severity: str, message: str, remediation: str, references=None) -> Dict[str, Any]:
    return CheckResult(
        id=id,
        title=title,
        category=category,
        severity=severity,
        status="fail",
        message=message,
        remediation=remediation,
        references=references or [],
        applicable=True,
    ).to_dict()


def mark_skip(id: str, title: str, category: str, severity: str, reason: str, references=None) -> Dict[str, Any]:
    return CheckResult(
        id=id,
        title=title,
        category=category,
        severity=severity,
        status="skipped",
        message=reason,
        remediation="",
        references=references or [],
        applicable=False,
    ).to_dict()

