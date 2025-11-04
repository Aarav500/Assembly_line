import json
import os
from typing import Any, Dict, List, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
RULES_DIR = os.path.join(BASE_DIR, "data", "rules")


class Rule:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.id = data.get("id")
        self.category = data.get("category")
        self.when = data.get("when", [])
        self.priority = data.get("priority", 5)

    def match(self, ctx: Dict[str, Any]) -> bool:
        def get_val(path: str):
            return ctx.get(path)

        for cond in self.when:
            field = cond.get("field")
            op = cond.get("op", "==")
            value = cond.get("value")
            actual = get_val(field)

            if op == "exists":
                if (value is True and actual is None) or (value is False and actual is not None):
                    return False
                continue

            if op in ("==", "eq"):
                if actual != value:
                    return False
            elif op in ("!=", "ne"):
                if actual == value:
                    return False
            elif op == ">":
                if not (isinstance(actual, (int, float)) and actual > value):
                    return False
            elif op == ">=":
                if not (isinstance(actual, (int, float)) and actual >= value):
                    return False
            elif op == "<":
                if not (isinstance(actual, (int, float)) and actual < value):
                    return False
            elif op == "<=":
                if not (isinstance(actual, (int, float)) and actual <= value):
                    return False
            elif op == "in":
                try:
                    if actual not in value:
                        return False
                except TypeError:
                    return False
            elif op == "not_in":
                try:
                    if actual in value:
                        return False
                except TypeError:
                    return False
            elif op == "contains":
                try:
                    if value not in actual:
                        return False
                except TypeError:
                    return False
            elif op == "not_contains":
                try:
                    if value in actual:
                        return False
                except TypeError:
                    return False
            elif op == "truthy":
                if not bool(actual):
                    return False
            elif op == "falsy":
                if bool(actual):
                    return False
            else:
                # Unknown operator, do not match
                return False
        return True

    def to_recommendation(self) -> Dict[str, Any]:
        keys = [
            "id",
            "category",
            "title",
            "message",
            "impact",
            "effort",
            "priority",
            "tags",
            "links",
        ]
        return {k: self.data.get(k) for k in keys}


class RecommendationEngine:
    def __init__(self, rules_dir: str = RULES_DIR):
        self.rules_dir = rules_dir
        self.rules: List[Rule] = []
        self._load_rules()

    def _load_rules(self):
        if not os.path.isdir(self.rules_dir):
            return
        for filename in os.listdir(self.rules_dir):
            if not filename.endswith(".json"):
                continue
            fpath = os.path.join(self.rules_dir, filename)
            with open(fpath, "r", encoding="utf-8") as f:
                try:
                    items = json.load(f)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"Invalid JSON in {fpath}: {e}")
                for item in items:
                    self.rules.append(Rule(item))
        # stable ordering: by category then priority then id
        self.rules.sort(key=lambda r: (r.category or "zzz", r.priority, r.id or ""))

    def _normalize_context(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        norm = dict((k, v) for k, v in (ctx or {}).items())
        # Normalize strings to lowercase for key fields
        for key in [
            "language",
            "framework",
            "cloud_provider",
            "database",
            "budget_tier",
            "deployment",
        ]:
            if key in norm and isinstance(norm[key], str):
                norm[key] = norm[key].strip().lower()
        # Normalize compliance to list of lowercase strings
        comp = norm.get("compliance")
        if isinstance(comp, str) and comp:
            norm["compliance"] = [c.strip().lower() for c in comp.split(",") if c.strip()]
        elif isinstance(comp, list):
            norm["compliance"] = [str(c).strip().lower() for c in comp]
        else:
            norm["compliance"] = []
        # Coerce booleans and numbers safely
        def to_bool(v):
            if isinstance(v, bool):
                return v
            if v is None:
                return False
            if isinstance(v, (int, float)):
                return bool(v)
            s = str(v).strip().lower()
            return s in ("1", "true", "yes", "y", "on")

        def to_int(v, default=0):
            try:
                return int(v)
            except Exception:
                try:
                    return int(float(v))
                except Exception:
                    return default

        norm["expected_users"] = to_int(norm.get("expected_users", 0), 0)
        for b in ["handles_pii", "public_api", "mobile_audience", "traffic_spikes", "ci_cd"]:
            norm[b] = to_bool(norm.get(b, False))
        # Derived flags
        norm["is_flask"] = norm.get("framework") == "flask"
        norm["is_python"] = norm.get("language") == "python"
        norm["relational_db"] = norm.get("database") in ("postgres", "mysql", "mariadb", "sqlserver")
        norm["has_cloud"] = norm.get("cloud_provider") in ("aws", "gcp", "azure")
        norm["high_traffic"] = norm.get("expected_users", 0) >= 10000 or norm.get("traffic_spikes")
        return norm

    def evaluate(self, context: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        ctx = self._normalize_context(context or {})
        results: Dict[str, List[Dict[str, Any]]] = {}
        seen_ids = set()

        for rule in self.rules:
            if rule.id in seen_ids:
                continue
            if rule.match(ctx):
                rec = rule.to_recommendation()
                cat = rec.get("category", "general")
                results.setdefault(cat, []).append(rec)
                seen_ids.add(rule.id)

        # Sort inside each category by priority then id
        for cat, items in results.items():
            items.sort(key=lambda r: (int(r.get("priority", 5)), r.get("id", "")))
        return results


_engine_singleton: RecommendationEngine | None = None

def get_engine() -> RecommendationEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = RecommendationEngine()
    return _engine_singleton

