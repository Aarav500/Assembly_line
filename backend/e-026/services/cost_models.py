from typing import Optional, Tuple

SIZE_ORDER = [
    "nano",
    "micro",
    "small",
    "medium",
    "large",
    "xlarge",
    "2xlarge",
    "4xlarge",
]

SIZE_MULTIPLIER = {
    "nano": 0.125,
    "micro": 0.25,
    "small": 0.5,
    "medium": 0.75,
    "large": 1.0,
    "xlarge": 2.0,
    "2xlarge": 4.0,
    "4xlarge": 8.0,
}

# Base hourly price for 'large' per instance family (illustrative values)
FAMILY_BASE_PRICE_LARGE = {
    "t3": 0.0832,
    "t3a": 0.0745,
    "m5": 0.0960,
    "m6g": 0.077,
    "c5": 0.085,
    "c6g": 0.068,
    "standard": 0.09,
}


def parse_instance_type(instance_type: str) -> Tuple[str, str]:
    # Expect format like 'm5.large', fallback to 'standard.large'
    if not instance_type:
        return "standard", "large"
    parts = instance_type.split(".")
    if len(parts) == 2:
        return parts[0], parts[1]
    return "standard", parts[-1]


def format_instance_type(family: str, size: str) -> str:
    return f"{family}.{size}"


def price_for(instance_type: str, region: Optional[str] = None) -> float:
    family, size = parse_instance_type(instance_type)
    base_large = FAMILY_BASE_PRICE_LARGE.get(family, FAMILY_BASE_PRICE_LARGE["standard"])
    multiplier = SIZE_MULTIPLIER.get(size, 1.0)
    # Region adjustment placeholder: regions may vary, we keep it flat for demo
    return round(base_large * multiplier, 4)


def adjust_size(size: str, steps: int) -> str:
    if size not in SIZE_ORDER:
        size = "large"
    idx = SIZE_ORDER.index(size)
    new_idx = max(0, min(len(SIZE_ORDER) - 1, idx + steps))
    return SIZE_ORDER[new_idx]


def recommend_type(current_type: str, direction: str, aggressiveness: int = 1) -> Optional[str]:
    family, size = parse_instance_type(current_type)
    if direction == "down":
        new_size = adjust_size(size, -aggressiveness)
        if new_size == size:
            return None
        return format_instance_type(family, new_size)
    elif direction == "up":
        new_size = adjust_size(size, aggressiveness)
        if new_size == size:
            return None
        return format_instance_type(family, new_size)
    return None

