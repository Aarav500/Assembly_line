import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Regex patterns to detect Ideater feature annotations across various languages/comments
IDEATER_COMMENT_RE = re.compile(
    r"(?im)^[ \t]*(?:#|//|;|\*|<!--)[ \t]*ideater:\s*(?:feature|idea)\s*(?::|=|\s)\s*(?P<id>[A-Za-z0-9_\-.]+)\s*(?P<rest>.*)$"
)

IDEATER_ANNOTATION_RE = re.compile(
    r"(?im)@ideater\((?P<args>[^)]*)\)"
)

# Extract key=value pairs from annotation args like feature="feat-id", status="implemented"
ANNOTATION_ARG_RE = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*['\"]([^'\"]+)['\"]")

# Inline token, e.g., within docstrings or markdown: Ideater: feat-123 (implemented)
IDEATER_INLINE_RE = re.compile(
    r"(?i)ideater\s*:\s*(?P<id>[A-Za-z0-9_\-.]+)(?:\s*\((?P<status>[^)]+)\))?"
)

# Weak mention pattern: feature id appearing as a standalone token
TOKEN_RE = re.compile(r"\b(?P<id>[A-Za-z0-9_][A-Za-z0-9_\-.]{1,})\b")

SUPPORTED_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".txt", ".json", ".yml", ".yaml", ".html", ".css"
}

MAX_FILE_SIZE = 1_000_000  # 1MB cap to avoid scanning binaries/large files


@dataclass
class EvidenceLine:
    path: str
    line: int
    text: str
    status: Optional[str] = None
    strength: str = "strong"  # strong|weak

    def __getitem__(self, key):
        """Allow dict-like access for backwards compatibility."""
        return getattr(self, key)


@dataclass
class Occurrence:
    """Represents a single occurrence of a feature mention."""
    file: str
    line: int
    text: str
    status: Optional[str] = None
    strength: str = "strong"


@dataclass
class FeatureEvidence:
    id: str
    occurrences: List[Occurrence] = field(default_factory=list)
    strong_occurrences: int = 0
    inferred_status: str = "not-detected"
    lines: List[EvidenceLine] = field(default_factory=list)


@dataclass
class DetectionResult:
    features: Dict[str, FeatureEvidence] = field(default_factory=dict)
    scanned_files: int = 0


_DEF_STATUS_MAP = {
    "implemented": "implemented",
    "in-progress": "in-progress",
    "partial": "in-progress",
    "planned": "planned",
    "deprecated": "deprecated",
    "wip": "in-progress",
    "done": "implemented",
}


def _norm_status(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    v = raw.strip().lower().replace("_", "-")
    return _DEF_STATUS_MAP.get(v, v)


def _upsert_feature(result: DetectionResult, feat_id: str) -> FeatureEvidence:
    if feat_id not in result.features:
        result.features[feat_id] = FeatureEvidence(id=feat_id)
    return result.features[feat_id]


def _update_inferred_status(fe: FeatureEvidence):
    # Determine inferred status based on evidence collected
    statuses = [ln.status for ln in fe.lines if ln.status]
    if any(s == "implemented" for s in statuses):
        fe.inferred_status = "implemented"
    elif any(s in ("in-progress", "partial") for s in statuses):
        fe.inferred_status = "in-progress"
    elif fe.strong_occurrences > 0:
        fe.inferred_status = "in-progress"
    elif len(fe.occurrences) > 0:
        fe.inferred_status = "referenced"
    else:
        fe.inferred_status = "not-detected"


def _scan_content_for_features(path: str, content: str, result: DetectionResult, options: Dict[str, Any]):
    # Strong matches: comment or annotation with explicit Ideater tag
    for m in IDEATER_COMMENT_RE.finditer(content):
        feat_id = m.group("id")
        rest = (m.group("rest") or "").strip()
        status = None
        # Try to parse status from rest
        if rest:
            # Look for known keywords anywhere in the rest of line
            for token in ("implemented", "in-progress", "partial", "planned", "deprecated"):
                if re.search(rf"(?i)\b{re.escape(token)}\b", rest):
                    status = _norm_status(token)
                    break
        fe = _upsert_feature(result, feat_id)
        line_no = _line_no(content, m.start())
        line_text = _line_text(content, m.start())
        fe.lines.append(EvidenceLine(path=path, line=line_no, text=line_text, status=status, strength="strong"))
        fe.occurrences.append(Occurrence(file=path, line=line_no, text=line_text, status=status, strength="strong"))
        fe.strong_occurrences += 1
        _update_inferred_status(fe)

    for m in IDEATER_ANNOTATION_RE.finditer(content):
        args = m.group("args") or ""
        kv = {k: v for k, v in ANNOTATION_ARG_RE.findall(args)}
        feat_id = kv.get("feature") or kv.get("id") or kv.get("idea")
        if not feat_id:
            continue
        status = _norm_status(kv.get("status"))
        fe = _upsert_feature(result, feat_id)
        line_no = _line_no(content, m.start())
        line_text = _line_text(content, m.start())
        fe.lines.append(EvidenceLine(path=path, line=line_no, text=line_text, status=status, strength="strong"))
        fe.occurrences.append(Occurrence(file=path, line=line_no, text=line_text, status=status, strength="strong"))
        fe.strong_occurrences += 1
        _update_inferred_status(fe)

    for m in IDEATER_INLINE_RE.finditer(content):
        feat_id = m.group("id")
        status = _norm_status(m.group("status"))
        fe = _upsert_feature(result, feat_id)
        line_no = _line_no(content, m.start())
        line_text = _line_text(content, m.start())
        fe.lines.append(EvidenceLine(path=path, line=line_no, text=line_text, status=status, strength="strong"))
        fe.occurrences.append(Occurrence(file=path, line=line_no, text=line_text, status=status, strength="strong"))
        fe.strong_occurrences += 1
        _update_inferred_status(fe)

    # Weak heuristic: if enabled, count bare id tokens that look like feature ids
    weak_enabled = bool(options.get("weak_keyword_detection", True))
    weak_ids: List[str] = [
        match.group("id") for match in TOKEN_RE.finditer(content)
        if _is_plausible_feature_id(match.group("id"), options)
    ] if weak_enabled else []
    if weak_ids:
        # De-duplicate within file to avoid flooding
        for feat_id in sorted(set(weak_ids)):
            fe = _upsert_feature(result, feat_id)
            fe.lines.append(EvidenceLine(path=path, line=0, text="<weak-token>", status=None, strength="weak"))
            fe.occurrences.append(Occurrence(file=path, line=0, text="<weak-token>", status=None, strength="weak"))
            _update_inferred_status(fe)


def _is_plausible_feature_id(token: str, options: Dict[str, Any]) -> bool:
    # Consider tokens with a dash or dot more likely to be feature ids, or prefixed with feat/idea
    if len(token) < 4:
        return False
    if any(prefix for prefix in ("feat", "idea", "feature") if token.lower().startswith(prefix)):
        return True
    if "-" in token or "." in token:
        return True
    return False


def _line_no(content: str, idx: int) -> int:
    return content.count("\n", 0, idx) + 1


def _line_text(content: str, idx: int) -> str:
    start = content.rfind("\n", 0, idx)
    end = content.find("\n", idx)
    if start < 0:
        start = 0
    else:
        start += 1
    if end < 0:
        end = len(content)
    return content[start:end][:300]


def detect_from_repo_files(files: List[Dict[str, str]], options: Optional[Dict[str, Any]] = None) -> DetectionResult:
    options = options or {}
    result = DetectionResult()
    for f in files:
        path = f.get("path") or f.get("name") or "<memory>"
        content = f.get("content")
        if content is None:
            continue
        # Filter by ext if provided
        _, ext = os.path.splitext(path.lower())
        if ext and ext not in SUPPORTED_EXTS:
            continue
        result.scanned_files += 1
        try:
            _scan_content_for_features(path, content, result, options)
        except Exception:
            # Skip unreadable content gracefully
            continue
    return result


def detect_from_repo_path(repo_path: str, options: Optional[Dict[str, Any]] = None) -> DetectionResult:
    """Scan a directory for feature annotations."""
    options = options or {}
    result = DetectionResult()
    
    if not os.path.isdir(repo_path):
        return result
    
    for root, dirs, files in os.walk(repo_path):
        # Skip common directories
        dirs[:] = [d for d in dirs if d not in {'.git', '.svn', 'node_modules', '__pycache__', '.pytest_cache', 'venv', '.venv'}]
        
        for filename in files:
            filepath = os.path.join(root, filename)
            _, ext = os.path.splitext(filename.lower())
            
            if ext not in SUPPORTED_EXTS:
                continue
            
            try:
                # Check file size
                if os.path.getsize(filepath) > MAX_FILE_SIZE:
                    continue
                
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Use relative path from repo_path
                rel_path = os.path.relpath(filepath, repo_path)
                result.scanned_files += 1
                _scan_content_for_features(rel_path, content, result, options)
            except Exception:
                # Skip files that can't be read
                continue
    
    return result
