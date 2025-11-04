from planners.pricing import estimate_cost
from planners.constraints import resolve_region, satisfies_compliance
from utils.naming import slugify

SUPPORTED_CLOUDS = ["aws", "azure", "gcp"]


def plan_deployment(spec: dict) -> dict:
    project_name = spec.get("name", "project")
    resources = spec.get("resources", [])
    global_prefs = spec.get("preferences", {})

    planned = []
    per_cloud_totals = {c: 0.0 for c in SUPPORTED_CLOUDS}

    for idx, res in enumerate(resources):
        rid = res.get("id") or f"res{idx+1}"
        rtype = res.get("type")
        allowed_clouds = res.get("allowedClouds") or global_prefs.get("allowedClouds") or SUPPORTED_CLOUDS
        allowed_clouds = [c for c in allowed_clouds if c in SUPPORTED_CLOUDS]
        if not allowed_clouds:
            allowed_clouds = SUPPORTED_CLOUDS

        requested_region_key = res.get("preferredRegion") or global_prefs.get("preferredRegion")
        residency = res.get("dataResidency") or global_prefs.get("dataResidency")
        compliance = res.get("compliance") or global_prefs.get("compliance") or []

        best = None
        best_cost = None
        best_cloud_region = None
        best_region_key = None

        for cloud in allowed_clouds:
            # decide region
            region_key_for_compliance = None
            if requested_region_key in ("eu-west", "eu-central", "us-east", "us-west", "asia-east"):
                region_key_for_compliance = requested_region_key
            elif residency and residency.lower() in ["eu", "gdpr", "europe"]:
                region_key_for_compliance = "eu-west"
            else:
                region_key_for_compliance = "us-east"

            if not satisfies_compliance(cloud, compliance, selected_region_key=region_key_for_compliance):
                continue

            region = resolve_region(cloud, requested_region_key, residency)
            # estimate cost for this cloud
            est = estimate_cost(res, cloud)
            if best is None or est < best_cost:
                best = cloud
                best_cost = est
                best_cloud_region = region
                best_region_key = region_key_for_compliance

        if best is None:
            # fallback to first supported
            best = allowed_clouds[0]
            best_cloud_region = resolve_region(best, requested_region_key, residency)
            best_cost = estimate_cost(res, best)

        per_cloud_totals[best] += best_cost

        planned.append({
            "resourceId": rid,
            "name": res.get("name") or f"{rtype}-{rid}",
            "type": rtype,
            "assignedCloud": best,
            "cloudRegion": best_cloud_region,
            "estimatedMonthlyCost": best_cost,
            "inputs": res,
            "reasons": {
                "cost": best_cost,
                "region": best_cloud_region,
                "notes": "Selected by cost heuristic under compliance/region constraints"
            }
        })

    total_cost = sum(per_cloud_totals.values())
    clouds_selected = {c: round(v, 2) for c, v in per_cloud_totals.items() if v > 0}

    return {
        "name": project_name,
        "summary": {
            "totalEstimatedMonthlyCost": round(total_cost, 2),
            "perCloudCost": clouds_selected
        },
        "plan": planned
    }

