import random
from dataclasses import dataclass

COOKIE_NAME = "bg_variant"


@dataclass
class Decision:
    variant: str  # "blue" | "green"
    source: str   # "forced" | "sticky" | "random"


def _coerce_variant(value: str | None):
    if not value:
        return None
    v = value.strip().lower()
    if v in ("blue", "green"):
        return v
    return None


def choose_variant(request, cfg) -> Decision:
    # Forced by query or header
    forced = _coerce_variant(request.args.get("variant")) or _coerce_variant(request.headers.get("X-BG-Variant"))
    if forced:
        return Decision(variant=forced, source="forced")

    # Sticky cookie, if respected
    cookie_variant = request.cookies.get(COOKIE_NAME)
    if cfg.get("respect_sticky", True) and _coerce_variant(cookie_variant):
        return Decision(variant=cookie_variant, source="sticky")

    # Random split
    blue_percent = max(0, min(100, int(cfg.get("blue_percent", 100))))
    pick = random.random() * 100.0
    variant = "blue" if pick < blue_percent else "green"
    return Decision(variant=variant, source="random")

