from __future__ import annotations
import json
import math
import os
import re
from typing import Any, Dict, List, Tuple


class Suggester:
    def __init__(self, blueprints_path: str):
        self.blueprints_path = blueprints_path
        self.blueprints = self._load_blueprints(blueprints_path)
        self.blueprint_by_id = {b["id"]: b for b in self.blueprints}
        self.upgrade_catalog = self._build_upgrade_catalog()

    def _load_blueprints(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Blueprints file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Blueprints JSON must be a list")
        return data

    def suggest(self, project: Dict[str, Any], top_k: int = 3) -> Dict[str, Any]:
        tokens = self._extract_tokens(project)
        scale_info = self._extract_scale(project)
        features = set(map(str.lower, project.get("features", []) or []))
        constraints = set(map(str.lower, project.get("constraints", []) or []))

        scored: List[Tuple[float, Dict[str, Any], List[str]]] = []
        for bp in self.blueprints:
            score, reasons = self._score_blueprint(bp, tokens, features, constraints, scale_info)
            scored.append((score, bp, reasons))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        agg_upgrades: Dict[str, Dict[str, Any]] = {}
        suggestions = []
        for score, bp, reasons in top:
            bp_upgrades = self._recommended_upgrades(project, bp, tokens, features, constraints, scale_info)
            for up in bp_upgrades:
                agg = agg_upgrades.get(up["id"]) or up.copy()
                agg["priority"] = self._max_priority(agg.get("priority"), up.get("priority"))
                agg["sources"] = sorted(set((agg.get("sources") or []) + [bp["id"]]))
                agg_upgrades[up["id"]] = agg

            suggestions.append({
                "id": bp["id"],
                "name": bp["name"],
                "score": round(float(min(1.0, max(0.0, score))), 4),
                "reasons": reasons,
                "fit_notes": bp.get("when_to_use", []),
                "suggested_structure": bp.get("structure", {}),
                "recommended_upgrades": bp_upgrades,
            })

        # Global upgrades not tied to a single blueprint
        global_upgrades = self._recommended_upgrades(project, None, tokens, features, constraints, scale_info)
        for up in global_upgrades:
            agg = agg_upgrades.get(up["id"]) or up.copy()
            agg["priority"] = self._max_priority(agg.get("priority"), up.get("priority"))
            agg["sources"] = sorted(set((agg.get("sources") or []) + ["global"]))
            agg_upgrades[up["id"]] = agg

        return {
            "project_echo": self._project_echo(project),
            "blueprint_suggestions": suggestions,
            "upgrades": sorted(agg_upgrades.values(), key=lambda u: (self._priority_rank(u.get("priority")), u["id"]))
        }

    def _project_echo(self, project: Dict[str, Any]) -> Dict[str, Any]:
        # Lightweight echo back to caller
        return {
            "name": project.get("name"),
            "type": (project.get("type") or "").lower() or None,
            "domain": (project.get("domain") or "").lower() or None,
            "features": project.get("features") or [],
            "stack": project.get("stack") or {},
            "constraints": project.get("constraints") or [],
            "scale": project.get("scale") or {},
        }

    # ------------------------- Tokenization & Scoring -------------------------
    def _extract_tokens(self, project: Dict[str, Any]) -> Dict[str, Any]:
        tokens: Dict[str, Any] = {
            "type": (project.get("type") or "").lower(),
            "domain": (project.get("domain") or "").lower(),
            "features": [s.lower() for s in (project.get("features") or [])],
            "constraints": [s.lower() for s in (project.get("constraints") or [])],
            "frameworks": [],
            "databases": [],
            "brokers": [],
            "summary_terms": [],
        }
        stack = project.get("stack") or {}
        for k in ("frameworks", "databases", "brokers"):
            v = stack.get(k) or []
            if isinstance(v, str):
                v = [v]
            tokens[k] = [str(x).lower() for x in v]

        summary = str(project.get("summary") or "")
        terms = [t for t in re.split(r"[^a-zA-Z0-9_]+", summary.lower()) if t]
        tokens["summary_terms"] = terms
        return tokens

    def _extract_scale(self, project: Dict[str, Any]) -> Dict[str, float]:
        scale = project.get("scale") or {}
        users = self._to_float(scale.get("users"))
        rpm = self._to_float(scale.get("requests_per_minute"))
        data_gb = self._to_float(scale.get("data_gb_per_day"))
        return {"users": users, "rpm": rpm, "data_gb": data_gb}

    def _to_float(self, v: Any) -> float:
        try:
            if v is None:
                return 0.0
            return float(v)
        except Exception:
            return 0.0

    def _score_blueprint(
        self,
        bp: Dict[str, Any],
        tokens: Dict[str, Any],
        features: set[str],
        constraints: set[str],
        scale: Dict[str, float],
    ) -> Tuple[float, List[str]]:
        reasons: List[str] = []
        tags = set([t.lower() for t in bp.get("tags", [])])
        token_bag = set(
            [tokens.get("type"), tokens.get("domain")] +
            tokens.get("features", []) + tokens.get("constraints", []) +
            tokens.get("frameworks", []) + tokens.get("summary_terms", [])
        )
        token_bag.discard("")

        # Base match by tags
        if tags:
            tag_matches = tags.intersection(token_bag)
            base = (len(tag_matches) / max(1, len(tags))) * 0.6
            if tag_matches:
                reasons.append(f"tag matches: {', '.join(sorted(tag_matches))}")
        else:
            base = 0.2

        score = base

        # Framework hints
        hint_fw = [x.lower() for x in (bp.get("hints", {}).get("frameworks") or [])]
        fw_matches = set(hint_fw).intersection(set(tokens.get("frameworks", [])))
        if fw_matches:
            score += min(0.3, 0.15 * len(fw_matches))
            reasons.append(f"framework match: {', '.join(sorted(fw_matches))}")

        # Domain/feature boosts
        if "kafka" in tokens.get("brokers", []) or "stream" in token_bag or "streaming" in token_bag:
            if bp["id"] in ("event-driven-service", "data-pipeline"):
                score += 0.2
                reasons.append("streaming signals detected")

        if ("ml" in token_bag or "machinelearning" in token_bag or "model" in token_bag) and bp["id"] == "ml-service":
            score += 0.3
            reasons.append("ML indicators present")

        if tokens.get("type") in ("api", "service") and bp["id"] in ("rest-api", "microservice"):
            score += 0.1
            reasons.append("service/api type")

        if tokens.get("type") in ("web", "frontend", "site") and bp["id"] == "web-app":
            score += 0.2
            reasons.append("web app type")

        if tokens.get("type") == "cli" and bp["id"] == "cli-tool":
            score += 0.5
            reasons.append("CLI type")

        # Scale-based boosts
        rpm = scale.get("rpm", 0.0)
        data_gb = scale.get("data_gb", 0.0)
        if rpm >= 2000 and bp["id"] in ("rest-api", "microservice"):
            score += 0.1
            reasons.append("high RPM")
        if data_gb >= 10 and bp["id"] in ("data-pipeline", "event-driven-service"):
            score += 0.1
            reasons.append("high data volume")

        # Constraint hints
        if ("low-latency" in constraints or "high-throughput" in constraints) and bp["id"] in ("microservice", "event-driven-service"):
            score += 0.1
            reasons.append("performance constraints")

        # Anti-patterns reduce score
        anti = [a.lower() for a in (bp.get("anti_patterns") or [])]
        anti_hits = set(anti).intersection(token_bag)
        if anti_hits:
            score -= min(0.3, 0.1 * len(anti_hits))
            reasons.append(f"anti-pattern signals: {', '.join(sorted(anti_hits))}")

        # Clamp score
        score = max(0.0, min(1.0, score))
        return score, reasons

    # ------------------------- Upgrades -------------------------
    def _build_upgrade_catalog(self) -> Dict[str, Dict[str, Any]]:
        return {
            "observability": {"title": "Observability (metrics, logs, traces)"},
            "tracing": {"title": "Distributed Tracing"},
            "api-docs": {"title": "OpenAPI Docs & Validation"},
            "auth": {"title": "Authentication & Authorization"},
            "rate-limiting": {"title": "Rate Limiting & Throttling"},
            "caching": {"title": "Caching Layer"},
            "queueing": {"title": "Asynchronous Queueing"},
            "ci-cd": {"title": "CI/CD Pipeline"},
            "containerization": {"title": "Containerization & IaC"},
            "testing": {"title": "Test Suite (unit/integration)"},
            "linting": {"title": "Linting & Formatting"},
            "typing": {"title": "Static Typing & Type Checks"},
            "validation": {"title": "Input Validation & Schema"},
            "secrets": {"title": "Secrets Management"},
            "encryption": {"title": "Encryption at Rest & in Transit"},
            "migrations": {"title": "Database Migrations"},
            "feature-flags": {"title": "Feature Flags"},
            "i18n": {"title": "Internationalization"},
            "retries-idempotency": {"title": "Retries & Idempotency"},
            "data-quality": {"title": "Data Quality & Validation"},
            "batch-scheduling": {"title": "Batch Scheduling & Orchestration"},
            "model-serving": {"title": "Model Serving & Versioning"},
            "security-headers": {"title": "Security Headers & Hardening"},
        }

    def _recommended_upgrades(
        self,
        project: Dict[str, Any],
        bp: Dict[str, Any] | None,
        tokens: Dict[str, Any],
        features: set[str],
        constraints: set[str],
        scale: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []

        def add(up_id: str, rationale: str, priority: str = "medium"):
            meta = self.upgrade_catalog.get(up_id, {"title": up_id})
            recs.append({
                "id": up_id,
                "title": meta.get("title", up_id),
                "rationale": rationale,
                "priority": priority,
            })

        # Baseline by blueprint
        if bp is not None:
            for up_id in bp.get("baseline_upgrades", []):
                add(up_id, f"Baseline for {bp['name']}", priority="medium")

        # Global rules
        rpm = scale.get("rpm", 0.0)
        data_gb = scale.get("data_gb", 0.0)
        users = scale.get("users", 0.0)

        # Always helpful
        add("testing", "Recommended for reliability", priority="medium")
        add("linting", "Improve code quality", priority="low")
        add("ci-cd", "Automate builds, tests, deploys", priority="medium")
        add("containerization", "Repeatable deployments", priority="low")
        add("typing", "Catch type errors early", priority="low")

        # API/service specifics
        if tokens.get("type") in ("api", "service") or (bp and bp["id"] in ("rest-api", "microservice")):
            add("api-docs", "Generate and validate OpenAPI schema", priority="high")
            add("validation", "Validate request/response payloads", priority="high")
            add("security-headers", "Harden HTTP endpoints", priority="medium")
            add("rate-limiting", "Protect against abuse", priority="medium")
            if "auth" in features or "authentication" in features:
                add("auth", "Project requires authentication", priority="high")

        # Performance/scale
        if rpm >= 1000 or "high-throughput" in constraints or "low-latency" in constraints:
            add("observability", "Monitor performance and errors", priority="high")
            add("caching", "Reduce load and latency", priority="medium")
            add("tracing", "Trace cross-service calls", priority="medium")

        # Data-intensive
        if data_gb >= 5 or tokens.get("type") in ("etl", "pipeline") or (bp and bp["id"] in ("data-pipeline",)):
            add("data-quality", "Detect bad data early", priority="high")
            add("batch-scheduling", "Reliable orchestration", priority="medium")
            add("retries-idempotency", "Safe reprocessing", priority="high")

        # Streaming / async signals
        if "kafka" in tokens.get("brokers", []) or "streaming" in tokens.get("features", []) or (bp and bp["id"] == "event-driven-service"):
            add("queueing", "Handle async workloads", priority="high")
            add("retries-idempotency", "Ensure at-least-once processing is safe", priority="high")
            add("observability", "Track consumer lag & processing", priority="high")

        # Regulated / sensitive domains
        if tokens.get("domain") in ("fintech", "healthcare", "gov") or "regulatory" in constraints or "compliance" in constraints:
            add("secrets", "Centralized secret management", priority="high")
            add("encryption", "Protect data at rest & in transit", priority="high")
            add("migrations", "Controlled DB changes", priority="medium")

        # Growth / product
        if users >= 5000 or "multi-tenant" in constraints:
            add("feature-flags", "Ship safely and target cohorts", priority="medium")

        # ML specific
        if "ml" in tokens.get("summary_terms", []) or "ml" in tokens.get("features", []) or (bp and bp["id"] == "ml-service"):
            add("model-serving", "Versioned model deployments", priority="medium")
            add("observability", "Monitor model performance", priority="high")

        # Web app
        if (tokens.get("type") == "web") or (bp and bp["id"] == "web-app"):
            add("i18n", "Prepare for global users", priority="low")

        # Deduplicate while preserving highest priority rationale
        final: Dict[str, Dict[str, Any]] = {}
        for r in recs:
            prev = final.get(r["id"]) or r
            if self._priority_rank(r["priority"]) < self._priority_rank(prev["priority"]):
                # higher priority number means lower priority; rank 0 is highest
                pass
            else:
                # keep the higher priority (lower rank value)
                if self._priority_rank(r["priority"]) < self._priority_rank(prev["priority"]):
                    prev = r
                else:
                    # same priority, keep existing but merge rationale if different
                    if r["rationale"] != prev["rationale"]:
                        prev["rationale"] = prev["rationale"] + "; " + r["rationale"]
            final[r["id"]] = {
                "id": r["id"],
                "title": r["title"],
                "rationale": prev["rationale"],
                "priority": self._higher_priority(prev["priority"], r["priority"]),
            }
        return list(final.values())

    def _priority_rank(self, p: str | None) -> int:
        order = {"high": 0, "medium": 1, "low": 2}
        return order.get((p or "medium").lower(), 1)

    def _higher_priority(self, a: str, b: str) -> str:
        return a if self._priority_rank(a) < self._priority_rank(b) else b

    def _max_priority(self, a: str | None, b: str | None) -> str:
        if not a:
            return b or "medium"
        if not b:
            return a or "medium"
        return a if self._priority_rank(a) < self._priority_rank(b) else b

