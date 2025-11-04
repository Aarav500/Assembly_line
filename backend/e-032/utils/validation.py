def validate_spec(spec: dict):
    if not isinstance(spec, dict):
        raise ValueError("Spec must be an object")
    resources = spec.get("resources")
    if resources is None or not isinstance(resources, list) or len(resources) == 0:
        raise ValueError("Spec.resources must be a non-empty array")
    for i, r in enumerate(resources):
        if not isinstance(r, dict):
            raise ValueError(f"Resource at index {i} must be an object")
        rtype = r.get("type")
        if rtype not in ("compute", "database", "storage"):
            raise ValueError(f"Resource at index {i} has invalid type {rtype}")
        if rtype in ("compute", "database"):
            if "vcpu" in r and (not isinstance(r["vcpu"], int) or r["vcpu"] <= 0):
                raise ValueError(f"Resource {r.get('id', i)} vcpu must be positive integer")
            if "ram_gb" in r and (not isinstance(r["ram_gb"], (int, float)) or r["ram_gb"] <= 0):
                raise ValueError(f"Resource {r.get('id', i)} ram_gb must be positive number")
        if rtype in ("database", "storage"):
            if "storage_gb" in r and (not isinstance(r["storage_gb"], (int, float)) or r["storage_gb"] <= 0):
                raise ValueError(f"Resource {r.get('id', i)} storage_gb must be positive number")

