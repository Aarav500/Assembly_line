from typing import Dict, List, Any
from .stats import percentile, clamp, ceil_step, floor_step

# Unit helpers

def to_cpu_m(maybe_cores_or_m: float, unit: str = "m") -> float:
    if unit == "m":
        return float(maybe_cores_or_m)
    if unit in ("core", "cores", "c"):
        return float(maybe_cores_or_m) * 1000.0
    raise ValueError("Unsupported CPU unit")


def to_mem_mib(value: float, unit: str = "Mi") -> float:
    unit = unit.lower()
    if unit in ("mi", "mib"):
        return float(value)
    if unit in ("gi", "gib"):
        return float(value) * 1024.0
    if unit in ("ki", "kib"):
        return float(value) / 1024.0
    if unit in ("mb",):
        return float(value) * (953.67431640625 / 1000.0)  # approximate Mi
    if unit in ("gb",):
        return float(value) * (953.67431640625)
    raise ValueError("Unsupported memory unit")


def fmt_cpu_qty(mcores: float) -> str:
    return f"{int(round(mcores))}m"


def fmt_mem_qty(mib: float) -> str:
    # Prefer Mi, round to nearest 1Mi
    return f"{int(round(mib))}Mi"


DEFAULT_POLICY = {
    "cpu": {
        "percentile": 0.9,
        "headroom_percent": 20,
        "min_millicores": 50,
        "max_millicores": 8000,
        "round_step_millicores": 10,
        "limit_factor": 1.5,  # limit ~ 1.5x request
    },
    "memory": {
        "percentile": 0.95,
        "headroom_percent": 20,
        "min_mebibytes": 64,
        "max_mebibytes": 32768,
        "round_step_mebibytes": 16,
        "limit_factor": 1.2,  # memory limit ~ 1.2x request
    },
    "hpa": {
        "cpu_target_utilization_percent": 70,
        "min_replicas": 1,
        "max_replicas_cap": 50,
        "scale_up_buffer": 1.5,
    },
    "vpa": {
        "update_mode": "Auto",
        "min_allowed_factor": 0.5,
        "max_allowed_factor": 1.0,
    },
}


def _get_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    merged = DEFAULT_POLICY.copy()
    for k in ("cpu", "memory", "hpa", "vpa"):
        sub = dict(DEFAULT_POLICY[k])
        sub.update(policy.get(k, {}))
        merged[k] = sub
    return merged


def _extract_series(metrics: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    cpu = []
    mem = []
    for m in metrics:
        # Expect keys cpu_mcores and mem_mib; allow fallbacks
        c = m.get("cpu_mcores")
        if c is None and "cpu_cores" in m:
            c = float(m["cpu_cores"]) * 1000.0
        if c is not None:
            cpu.append(float(c))
        mm = m.get("mem_mib")
        if mm is None and "mem_bytes" in m:
            mm = float(m["mem_bytes"]) / (1024.0 * 1024.0)
        if mm is not None:
            mem.append(float(mm))
    if not cpu and not mem:
        raise ValueError("metrics must include cpu_mcores and/or mem_mib values")
    return {"cpu": cpu, "mem": mem}


def _compute_request_limit(series: List[float], pctl: float, headroom_pct: float, min_v: float, max_v: float, round_step: float, limit_factor: float) -> Dict[str, int]:
    if not series:
        return {"request": None, "limit": None}
    base = percentile(series, pctl)
    if base is None:
        return {"request": None, "limit": None}
    req = base * (1.0 + headroom_pct / 100.0)
    req = clamp(ceil_step(req, round_step), min_v, max_v)
    limit = clamp(ceil_step(req * limit_factor, round_step), req, max_v)
    return {"request": int(round(req)), "limit": int(round(limit))}


def _suggest_hpa(series_cpu: List[float], series_mem: List[float], req_cpu: int, req_mem: int, policy_hpa: Dict[str, Any]) -> Dict[str, int]:
    min_repl = int(policy_hpa.get("min_replicas", 1))
    cap = int(policy_hpa.get("max_replicas_cap", 50))
    buf = float(policy_hpa.get("scale_up_buffer", 1.5))

    max_cpu = max(series_cpu) if series_cpu else 0.0
    max_mem = max(series_mem) if series_mem else 0.0

    cpu_based = 1
    mem_based = 1

    if req_cpu and req_cpu > 0:
        cpu_based = int(max(1, -(-int(max_cpu * buf) // int(max(req_cpu, 1)))))  # ceil division-like
    if req_mem and req_mem > 0:
        mem_based = int(max(1, -(-int(max_mem * buf) // int(max(req_mem, 1)))))

    # conservative: use max of cpu/mem
    est_max = max(cpu_based, mem_based)
    max_repl = int(clamp(est_max, min_repl, cap))

    return {
        "min_replicas": min_repl,
        "max_replicas": max_repl,
        "cpu_target_utilization_percent": int(policy_hpa.get("cpu_target_utilization_percent", 70)),
    }


def _suggest_vpa(req_cpu: int, req_mem: int, lim_cpu: int, lim_mem: int, policy_vpa: Dict[str, Any]) -> Dict[str, Any]:
    min_factor = float(policy_vpa.get("min_allowed_factor", 0.5))
    max_factor = float(policy_vpa.get("max_allowed_factor", 1.0))

    min_cpu = max(1, int(floor_step(req_cpu * min_factor, 10))) if req_cpu else None
    min_mem = max(1, int(floor_step(req_mem * min_factor, 16))) if req_mem else None

    max_cpu = int(ceil_step(lim_cpu * max_factor, 10)) if lim_cpu else None
    max_mem = int(ceil_step(lim_mem * max_factor, 16)) if lim_mem else None

    v = {
        "min_allowed": {
            "cpu": (f"{min_cpu}m" if min_cpu else None),
            "memory": (f"{min_mem}Mi" if min_mem else None),
        },
        "max_allowed": {
            "cpu": (f"{max_cpu}m" if max_cpu else None),
            "memory": (f"{max_mem}Mi" if max_mem else None),
        },
        "update_mode": policy_vpa.get("update_mode", "Auto"),
    }
    return v


def recommend_resources(metrics: List[dict], policy: Dict[str, Any] = None, current: Dict[str, Any] = None) -> Dict[str, Any]:
    policy = _get_policy(policy or {})
    series = _extract_series(metrics)

    cpu_conf = policy["cpu"]
    mem_conf = policy["memory"]

    cpu_rl = _compute_request_limit(
        series["cpu"],
        cpu_conf["percentile"],
        cpu_conf["headroom_percent"],
        cpu_conf["min_millicores"],
        cpu_conf["max_millicores"],
        cpu_conf["round_step_millicores"],
        cpu_conf["limit_factor"],
    )

    mem_rl = _compute_request_limit(
        series["mem"],
        mem_conf["percentile"],
        mem_conf["headroom_percent"],
        mem_conf["min_mebibytes"],
        mem_conf["max_mebibytes"],
        mem_conf["round_step_mebibytes"],
        mem_conf["limit_factor"],
    )

    requests = {
        "cpu_mcores": cpu_rl["request"],
        "memory_mib": mem_rl["request"],
    }
    limits = {
        "cpu_mcores": cpu_rl["limit"],
        "memory_mib": mem_rl["limit"],
    }

    hpa = _suggest_hpa(
        series_cpu=series["cpu"],
        series_mem=series["mem"],
        req_cpu=requests["cpu_mcores"] or 0,
        req_mem=requests["memory_mib"] or 0,
        policy_hpa=policy["hpa"],
    )

    vpa = _suggest_vpa(
        req_cpu=requests["cpu_mcores"] or 0,
        req_mem=requests["memory_mib"] or 0,
        lim_cpu=limits["cpu_mcores"] or (requests["cpu_mcores"] or 0),
        lim_mem=limits["memory_mib"] or (requests["memory_mib"] or 0),
        policy_vpa=policy["vpa"],
    )

    return {
        "requests": requests,
        "limits": limits,
        "hpa": hpa,
        "vpa": vpa,
    }

