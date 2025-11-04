from typing import List, Dict, Any, Optional
from models import Runner, JobRequest


def _normalize(values: List[float]) -> List[float]:
    if not values:
        return []
    max_v = max(values)
    if max_v <= 0:
        return [0.0 for _ in values]
    return [v / max_v for v in values]


def _weight_profile(job: JobRequest, policy: Dict[str, Any], heavy: bool, misses_deadline_any: bool) -> Dict[str, float]:
    weights = policy.get("weights", {})
    if job.priority == "high" or job.deadline_minutes is not None or misses_deadline_any:
        return weights.get("latency_sensitive", {"cost": 0.15, "speed": 0.7, "queue": 0.1, "risk": 0.05})
    if heavy or job.budget_cap is not None:
        return weights.get("heavy", {"cost": 0.6, "speed": 0.25, "queue": 0.1, "risk": 0.05})
    return weights.get("normal", {"cost": 0.35, "speed": 0.45, "queue": 0.15, "risk": 0.05})


def _is_heavy(job: JobRequest, policy: Dict[str, Any]) -> bool:
    threshold = float(policy.get("heavy_threshold", 60.0))
    # Simple heuristic: CPU-minutes proxy
    cpu_minutes = job.estimated_minutes * max(1, job.cpu_req)
    mem_factor = max(1.0, job.mem_req_mb / 2048.0)
    score = cpu_minutes * mem_factor
    return score >= threshold


def select_runner(job: JobRequest, runners: List[Runner], policy: Dict[str, Any]) -> Dict[str, Any]:
    reasons_excluded: List[Dict[str, Any]] = []

    # Step 1: filter candidates by hard constraints
    candidates: List[Runner] = []
    for r in runners:
        reason: Optional[str] = None
        if not r.online:
            reason = "runner_offline"
        elif job.cpu_req > r.cpu or job.mem_req_mb > r.memory_mb:
            reason = "insufficient_resources"
        elif job.required_labels and not set(job.required_labels).issubset(set(r.labels)):
            reason = "labels_not_matched"
        elif r.running_jobs >= r.capacity:
            reason = "no_capacity"
        elif r.preemptible and not job.allow_preemptible:
            reason = "preemptible_not_allowed"
        if reason:
            reasons_excluded.append({"runner_id": r.id, "name": r.name, "reason": reason})
        else:
            candidates.append(r)

    if not candidates:
        return {
            "selected": None,
            "candidates": [],
            "excluded": reasons_excluded,
            "message": "No available runners meet hard constraints"
        }

    # Step 2: score candidates
    heavy = _is_heavy(job, policy)

    # Precompute metrics
    predicted_durations = []
    costs = []
    queues = []
    risks = []
    meta: List[Dict[str, Any]] = []

    # derive whether any miss deadline to tune weights
    misses_deadline_any = False

    for r in candidates:
        # Higher performance_score => faster. Baseline 1.0 means neutral.
        perf_multiplier = (1.0 / max(0.1, r.performance_score))
        predicted_minutes = job.estimated_minutes * perf_multiplier
        queue_minutes = max(0.0, r.queue_time_estimate)
        cost_estimate = predicted_minutes * max(0.0, r.cost_per_minute)
        risk_score = 1.0 if r.preemptible else 0.0

        misses_deadline = False
        if job.deadline_minutes is not None:
            misses_deadline = (predicted_minutes + queue_minutes) > job.deadline_minutes
            if misses_deadline:
                misses_deadline_any = True

        over_budget = False
        budget_excess_ratio = 0.0
        if job.budget_cap is not None:
            over_budget = cost_estimate > job.budget_cap
            if over_budget and job.budget_cap > 0:
                budget_excess_ratio = (cost_estimate - job.budget_cap) / job.budget_cap

        predicted_durations.append(predicted_minutes)
        costs.append(cost_estimate)
        queues.append(queue_minutes)
        risks.append(risk_score)
        meta.append({
            "runner": r,
            "predicted_minutes": predicted_minutes,
            "queue_minutes": queue_minutes,
            "cost_estimate": cost_estimate,
            "misses_deadline": misses_deadline,
            "over_budget": over_budget,
            "budget_excess_ratio": budget_excess_ratio,
        })

    # Weight profile
    weights = _weight_profile(job, policy, heavy, misses_deadline_any)
    wc = float(weights.get("cost", 0.35))
    ws = float(weights.get("speed", 0.45))
    wq = float(weights.get("queue", 0.15))
    wr = float(weights.get("risk", 0.05))
    total_w = max(1e-9, (wc + ws + wq + wr))
    wc, ws, wq, wr = wc/total_w, ws/total_w, wq/total_w, wr/total_w

    # Normalize
    cost_norm = _normalize(costs)
    dur_norm = _normalize(predicted_durations)
    queue_norm = _normalize(queues)
    # Risk already in [0,1]

    scored: List[Dict[str, Any]] = []

    # Additional constraints from policy
    max_q_high = float(policy.get("constraints", {}).get("max_queue_minutes_for_high_priority", 5.0))

    for i, m in enumerate(meta):
        r = m["runner"]
        # Base score
        score = wc * cost_norm[i] + ws * dur_norm[i] + wq * queue_norm[i] + wr * risks[i]

        penalties: List[str] = []
        # Penalize missing deadline (if not hard disqualify)
        if m["misses_deadline"]:
            if job.priority == "high":
                # disqualify
                penalties.append("disqualified_misses_deadline_high_priority")
                score = float("inf")
            else:
                score *= 2.0
                penalties.append("penalty_deadline")

        # Penalize over budget
        if m["over_budget"]:
            # If way over budget, stronger penalty
            ratio = m["budget_excess_ratio"]
            score *= (1.0 + min(3.0, 1.5 + ratio))
            penalties.append("penalty_over_budget")

        # Queue constraint for high priority
        if job.priority == "high" and m["queue_minutes"] > max_q_high:
            score *= 1.5
            penalties.append("penalty_queue_high_priority")

        scored.append({
            "runner_id": r.id,
            "name": r.name,
            "provider": r.provider,
            "labels": r.labels,
            "preemptible": r.preemptible,
            "online": r.online,
            "capacity": r.capacity,
            "running_jobs": r.running_jobs,
            "metrics": {
                "predicted_minutes": round(m["predicted_minutes"], 3),
                "queue_minutes": round(m["queue_minutes"], 3),
                "cost_estimate": round(m["cost_estimate"], 4),
                "normalized": {
                    "cost": round(cost_norm[i], 4),
                    "duration": round(dur_norm[i], 4),
                    "queue": round(queue_norm[i], 4),
                    "risk": risks[i],
                },
            },
            "penalties": penalties,
            "misses_deadline": m["misses_deadline"],
            "over_budget": m["over_budget"],
            "score": score,
        })

    # Sort by score asc (lower is better)
    scored = sorted(scored, key=lambda x: x["score"]) if scored else []

    # Remove disqualified (inf score)
    scored_filtered = [c for c in scored if c["score"] != float("inf")]

    selected = scored_filtered[0] if scored_filtered else None

    response: Dict[str, Any] = {
        "selected": selected,
        "candidates": scored_filtered,
        "excluded": reasons_excluded,
        "weights": weights,
        "job_profile": {
            "heavy": heavy,
            "priority": job.priority,
            "deadline_minutes": job.deadline_minutes,
            "budget_cap": job.budget_cap,
        },
    }

    if not selected:
        response["message"] = "No suitable runner after scoring"

    # Provide fallbacks (top 3)
    response["fallbacks"] = scored_filtered[1:4] if len(scored_filtered) > 1 else []

    return response

