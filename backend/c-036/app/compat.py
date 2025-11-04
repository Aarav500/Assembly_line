from __future__ import annotations
from typing import Dict, Any, List


# Backward compatibility adapters between latest schema (v2) and older (v1)
# Latest canonical model (v2): {id, first_name, last_name, email}
# v1 response model: {id, name}


def adapt_user_to_version(user_v2: Dict[str, Any], version: str) -> Dict[str, Any]:
    if version == 'v1':
        name = f"{user_v2.get('first_name', '').strip()} {user_v2.get('last_name', '').strip()}".strip()
        return {
            "id": user_v2.get("id"),
            "name": name or None
        }
    # For v2 and above, return as-is (could deep copy if needed)
    return {
        "id": user_v2.get("id"),
        "first_name": user_v2.get("first_name"),
        "last_name": user_v2.get("last_name"),
        "email": user_v2.get("email")
    }


def adapt_users_list_to_version(users_v2: List[Dict[str, Any]], version: str) -> List[Dict[str, Any]]:
    return [adapt_user_to_version(u, version) for u in users_v2]


def adapt_request_payload_to_v2(version: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if version == 'v1':
        # v1 provided {name: "First Last"} or just one string
        name = (payload or {}).get('name', '')
        name = name.strip()
        if not name:
            # Best-effort: treat provided value as first_name if present
            return {"first_name": None, "last_name": None, "email": (payload or {}).get("email")}
        parts = [p for p in name.split(' ') if p]
        if len(parts) == 1:
            first, last = parts[0], ''
        else:
            first, last = parts[0], ' '.join(parts[1:])
        return {"first_name": first, "last_name": last, "email": (payload or {}).get("email")}
    # Already v2 schema
    return {
        "first_name": (payload or {}).get("first_name"),
        "last_name": (payload or {}).get("last_name"),
        "email": (payload or {}).get("email")
    }

