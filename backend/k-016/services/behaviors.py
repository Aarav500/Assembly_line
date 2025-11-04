from typing import Dict, Any
import random
import math


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _safe_float(d: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        v = d.get(key, default)
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def decide_trade(state: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    # Inputs
    price = _safe_float(state, "price", 0.0)
    volatility = _clamp(_safe_float(state, "volatility", 0.0), 0.0, 5.0)
    momentum = _clamp(_safe_float(state, "momentum", 0.0), -1.0, 1.0)
    moving_avg = _safe_float(state, "moving_avg", price)
    budget = max(0.0, _safe_float(state, "budget", 0.0))
    inventory = _safe_float(state, "inventory", 0.0)

    # Derived
    price_dev = 0.0
    if moving_avg > 0:
        price_dev = (price - moving_avg) / moving_avg
        price_dev = _clamp(price_dev, -1.0, 1.0)

    # Signal
    signal = (
        policy["momentum_weight"] * momentum +
        policy["volatility_weight"] * volatility +
        policy["mean_reversion"] * (-price_dev)
    )

    # Threshold influenced by risk tolerance (aggressive -> lower threshold)
    base_thresh = 0.25
    thresh = _clamp(base_thresh * (1.2 - policy["risk_tolerance"]), 0.05, 0.6)

    # Exploration: occasionally take a small contrarian or random action
    if random.random() < policy["exploration"]:
        jitter = (random.random() - 0.5) * 0.5
        signal += jitter

    # Determine direction
    action = "hold"
    if signal > thresh:
        action = "buy"
    elif signal < -thresh:
        action = "sell"

    # Capacity calculations
    max_leverage = policy["max_leverage"]
    # Maximum capital deployable considering leverage
    deployable_capital = budget * max_leverage

    # Aggressive profiles may allow limited shorting; conservative do not
    allow_short = policy["risk_tolerance"] >= 0.7

    max_order_fraction = policy["max_order_fraction"]
    target_util = policy["target_utilization"]

    strength = _clamp(abs(signal) / (abs(signal) + thresh + 1e-9), 0.0, 1.0)
    # Scale order fraction by signal strength and risk tolerance
    frac = max_order_fraction * (0.5 + 0.5 * strength) * (0.5 + 0.5 * policy["risk_tolerance"])
    frac = _clamp(frac, 0.0, max_order_fraction)

    quantity = 0.0
    price_limit = None

    if price > 0.0:
        if action == "buy":
            capital_to_use = deployable_capital * target_util * frac
            quantity = capital_to_use / price
            price_limit = price * (1 + policy["take_profit"] * strength * 0.5)
        elif action == "sell":
            if inventory > 0:
                # Sell a fraction of current holdings
                quantity = max(0.0, inventory * frac)
            elif allow_short:
                # Short using a portion of deployable capital
                capital_to_short = deployable_capital * target_util * frac * 0.5
                quantity = capital_to_short / price
            else:
                quantity = 0.0
            price_limit = price * (1 - policy["take_profit"] * strength * 0.5)

    # Round to a sensible precision (e.g., 6 decimals for quantity)
    quantity = float(f"{quantity:.6f}")
    if price_limit is not None:
        price_limit = float(f"{price_limit:.6f}")

    # If no meaningful quantity, hold
    if quantity <= 0.0:
        action = "hold"
        quantity = 0.0
        price_limit = None

    # Confidence based on signal and policy aversion to volatility
    vol_penalty = _clamp(volatility * abs(policy["volatility_weight"]) * 0.2, 0.0, 0.5)
    confidence = _clamp(abs(signal) - (thresh * 0.5) - vol_penalty, 0.0, 1.0)

    # Risk bands for reference
    stop_loss = policy["stop_loss"]
    take_profit = policy["take_profit"]

    return {
        "action": action,
        "quantity": quantity,
        "price_limit": price_limit,
        "confidence": float(f"{confidence:.3f}"),
        "bands": {
            "stop_loss": float(f"{stop_loss:.4f}"),
            "take_profit": float(f"{take_profit:.4f}")
        },
        "explain": {
            "signal": float(f"{signal:.4f}"),
            "threshold": float(f"{thresh:.4f}"),
            "inputs": {
                "price": price,
                "volatility": volatility,
                "momentum": momentum,
                "price_deviation": price_dev,
                "budget": budget,
                "inventory": inventory
            }
        }
    }

