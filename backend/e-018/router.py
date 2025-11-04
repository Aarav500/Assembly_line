from typing import Dict, Optional


def choose_replica(replica_status: Dict[str, Dict], preferred_region: Optional[str], strategy: str, max_lag: float) -> Optional[str]:
    # Filter healthy
    candidates = {name: st for name, st in replica_status.items() if st.get("healthy")}
    if not candidates:
        return None

    # Prefer preferred_region with acceptable lag
    if preferred_region:
        same_region = [
            (name, st) for name, st in candidates.items()
            if st.get("region") == preferred_region and st.get("lag", float("inf")) <= max_lag
        ]
        if same_region:
            # Pick the lowest lag among same region
            name = sorted(same_region, key=lambda x: (x[1].get("lag", 999999), x[0]))[0][0]
            return name

    # Strategy fallback
    if strategy == "lowest-lag":
        name = min(candidates.items(), key=lambda kv: kv[1].get("lag", float("inf")))[0]
        return name

    # Default 'nearest' without a distance map: approximate by same region else lowest lag
    if preferred_region:
        same_region = [(name, st) for name, st in candidates.items() if st.get("region") == preferred_region]
        if same_region:
            name = sorted(same_region, key=lambda x: (x[1].get("lag", 999999), x[0]))[0][0]
            return name

    # Fallback to lowest lag globally
    name = min(candidates.items(), key=lambda kv: kv[1].get("lag", float("inf")))[0]
    return name

