from __future__ import annotations
import re
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Any, Iterable
from .policy import Policy, Match


@dataclass
class PolicyEngine:
    policies: List[Policy] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str) -> "PolicyEngine":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or []
        policies = []
        for item in raw:
            try:
                policies.append(Policy.from_dict(item))
            except Exception as e:
                raise ValueError(f"Invalid policy in {path}: {e}") from e
        return cls(policies=policies)

    def scan(self, content: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        metadata = metadata or {}
        findings: List[Dict[str, Any]] = []
        deny_count = 0
        warn_count = 0

        for policy in self.policies:
            matches: Iterable[Match] = policy.evaluate(content, metadata)
            for m in matches:
                finding = {
                    "policy_id": policy.id,
                    "action": policy.action,
                    "severity": policy.severity,
                    "message": policy.message,
                    "tags": policy.tags,
                    "location": {
                        "line": m.line,
                        "column": m.column,
                        "span": [m.start, m.end],
                    },
                    "snippet": m.snippet,
                    "match": m.display_text,
                }
                findings.append(finding)
                if policy.action == "deny":
                    deny_count += 1
                else:
                    warn_count += 1

        allowed = deny_count == 0
        summary = {
            "deny": deny_count,
            "warn": warn_count,
            "total": deny_count + warn_count,
        }
        return {
            "allowed": allowed,
            "summary": summary,
            "findings": findings,
            "metadata": metadata,
        }

