from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import ast
import logging

logger = logging.getLogger(__name__)


@dataclass
class Issue:
    rule_id: str
    category: str
    title: str
    file: str
    line: Optional[int]
    column: Optional[int]
    severity: str  # low, medium, high, critical
    recommendation: str
    details: Optional[str] = None
    tags: Optional[list] = None

    def to_dict(self) -> Dict[str, Any]:
        try:
            return {
                "id": f"{self.rule_id}:{self.file}:{self.line}",
                "rule_id": self.rule_id,
                "type": self.category,
                "title": self.title,
                "file": self.file,
                "line": self.line,
                "column": self.column,
                "severity": self.severity,
                "recommendation": self.recommendation,
                "details": self.details,
                "tags": self.tags or [],
                "detected_at": datetime.utcnow().isoformat() + "Z",
            }
        except Exception as e:
            logger.error(f"Error converting Issue to dict: {e}")
            raise


class BaseRule:
    rule_id: str = "base"
    name: str = "Base Rule"
    description: str = ""
    category: str = "general"  # bugs | security | performance | tests
    default_severity: str = "low"
    scope: str = "file"  # file | project

    def analyze_file(self, file_path: str, tree: ast.AST, code: str) -> List[Issue]:
        try:
            return []
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return []

    def analyze_project(self, files: List[Tuple[str, ast.AST, str]]) -> List[Issue]:
        try:
            return []
        except Exception as e:
            logger.error(f"Error analyzing project: {e}")
            return []