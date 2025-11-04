REGIONS = {
    "aws": {
        "us-east": "us-east-1",
        "us-west": "us-west-2",
        "eu-west": "eu-west-1",
        "eu-central": "eu-central-1",
        "asia-east": "ap-east-1"
    },
    "azure": {
        "us-east": "eastus",
        "us-west": "westus2",
        "eu-west": "westeurope",
        "eu-central": "germanywestcentral",
        "asia-east": "eastasia"
    },
    "gcp": {
        "us-east": "us-east1",
        "us-west": "us-west2",
        "eu-west": "europe-west1",
        "eu-central": "europe-central2",
        "asia-east": "asia-east1"
    }
}

# Basic compliance support markers per cloud
CLOUD_COMPLIANCE = {
    "aws": {"hipaa": True, "gdpr": True},
    "azure": {"hipaa": True, "gdpr": True},
    "gcp": {"hipaa": True, "gdpr": True}
}

EU_REGION_KEYS = {"eu-west", "eu-central"}


def resolve_region(cloud, requested_region_key=None, data_residency=None):
    # If explicit provider region provided like aws:us-east-1, honor it
    if requested_region_key and ":" in str(requested_region_key):
        prov, region = requested_region_key.split(":", 1)
        if prov.strip().lower() == cloud:
            return region
    # Decide based on residency or default
    mapping = REGIONS.get(cloud, {})
    if data_residency and data_residency.lower() in ["eu", "europe", "gdpr"]:
        # Prefer eu-west if available
        return mapping.get("eu-west") or next(iter(mapping.values()))
    if requested_region_key and requested_region_key in mapping:
        return mapping[requested_region_key]
    # default to us-east for demo
    return mapping.get("us-east") or next(iter(mapping.values()))


def satisfies_compliance(cloud, requirements, selected_region_key=None):
    if not requirements:
        return True
    caps = CLOUD_COMPLIANCE.get(cloud, {})
    for req in requirements:
        if req.lower() == "gdpr":
            # ensure we are in EU-like region
            if selected_region_key and selected_region_key not in EU_REGION_KEYS:
                return False
        if not caps.get(req.lower(), False):
            return False
    return True

