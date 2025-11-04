import json
import os
import threading
from typing import Dict, Any


class PolicyNotFound(Exception):
    pass


class ValidationError(Exception):
    pass


DEFAULTS: Dict[str, Any] = {
    "risk_tolerance": 0.5,         # 0..1
    "max_leverage": 1.0,           # >=1.0
    "exploration": 0.1,            # 0..1
    "target_utilization": 0.5,     # 0..1 of budget to use when signal strong
    "take_profit": 0.03,           # 0..1 relative TP band
    "stop_loss": 0.03,             # 0..1 relative SL band
    "max_order_fraction": 0.1,     # 0..1 max fraction of capacity per order
    "momentum_weight": 0.5,        # signal weight
    "volatility_weight": -0.4,     # penalize vol
    "mean_reversion": 0.0          # positive favors reversion, negative favors trend
}


_BUILT_INS = {
    "aggressive": {
        "risk_tolerance": 0.9,
        "max_leverage": 2.0,
        "exploration": 0.3,
        "target_utilization": 0.8,
        "take_profit": 0.05,
        "stop_loss": 0.07,
        "max_order_fraction": 0.25,
        "momentum_weight": 0.7,
        "volatility_weight": -0.2,
        "mean_reversion": -0.1
    },
    "conservative": {
        "risk_tolerance": 0.2,
        "max_leverage": 1.0,
        "exploration": 0.05,
        "target_utilization": 0.3,
        "take_profit": 0.02,
        "stop_loss": 0.02,
        "max_order_fraction": 0.05,
        "momentum_weight": 0.3,
        "volatility_weight": -0.6,
        "mean_reversion": 0.2
    }
}


class PolicyEngine:
    def __init__(self, filepath: str = "config/policies.json"):
        self.filepath = filepath
        self._lock = threading.Lock()
        self._policies: Dict[str, Dict[str, Any]] = {}
        self._ensure_storage()
        self._load()

    def _ensure_storage(self):
        dirname = os.path.dirname(self.filepath)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(_BUILT_INS, f, indent=2)

    def _load(self):
        with self._lock:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
            except (FileNotFoundError, json.JSONDecodeError):
                data = {}
            # fill defaults for each policy
            normalized = {}
            for name, params in {**_BUILT_INS, **data}.items():
                try:
                    normalized[name] = self._validate_and_merge(params)
                except ValidationError:
                    # skip invalid custom entries
                    continue
            self._policies = normalized
            self._persist_unlocked()

    def _persist_unlocked(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self._policies, f, indent=2, sort_keys=True)

    def list_policies(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._policies)

    def get_policy(self, name: str) -> Dict[str, Any]:
        with self._lock:
            pol = self._policies.get(name)
            if not pol:
                raise PolicyNotFound(name)
            return dict(pol)

    def set_policy(self, name: str, params: Dict[str, Any]):
        if not isinstance(name, str) or not name:
            raise ValidationError("name must be a non-empty string")
        if not isinstance(params, dict):
            raise ValidationError("params must be an object")
        with self._lock:
            merged = self._validate_and_merge(params)
            self._policies[name] = merged
            self._persist_unlocked()

    def delete_policy(self, name: str):
        with self._lock:
            if name not in self._policies:
                raise PolicyNotFound(name)
            del self._policies[name]
            self._persist_unlocked()

    def _validate_and_merge(self, params: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(DEFAULTS)
        for k, v in params.items():
            if k not in DEFAULTS:
                # allow forward-compat but do not store unknown keys
                continue
            out[k] = v
        # validation and clamping
        def clamp(x, lo, hi):
            try:
                x = float(x)
            except Exception:
                raise ValidationError(f"invalid value for parameter")
            return max(lo, min(hi, x))

        out["risk_tolerance"] = clamp(out["risk_tolerance"], 0.0, 1.0)
        out["max_leverage"] = max(1.0, float(out["max_leverage"]))
        out["exploration"] = clamp(out["exploration"], 0.0, 1.0)
        out["target_utilization"] = clamp(out["target_utilization"], 0.0, 1.0)
        out["take_profit"] = clamp(out["take_profit"], 0.0, 1.0)
        out["stop_loss"] = clamp(out["stop_loss"], 0.0, 1.0)
        out["max_order_fraction"] = clamp(out["max_order_fraction"], 0.0, 1.0)
        # weights can be any finite float
        for w in ("momentum_weight", "volatility_weight", "mean_reversion"):
            try:
                out[w] = float(out[w])
            except Exception:
                raise ValidationError(f"{w} must be a number")
        return out

