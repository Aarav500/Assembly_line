MONTHLY_HOURS = 730

PRICES = {
    "aws": {
        "compute": {"vcpu_per_hr": 0.023, "ram_gb_per_hr": 0.0035},
        "db": {"vcpu_per_hr": 0.035, "ram_gb_per_hr": 0.005, "storage_gb_per_mo": 0.12},
        "storage": {"gb_per_mo": 0.023}
    },
    "azure": {
        "compute": {"vcpu_per_hr": 0.025, "ram_gb_per_hr": 0.0038},
        "db": {"vcpu_per_hr": 0.036, "ram_gb_per_hr": 0.0055, "storage_gb_per_mo": 0.115},
        "storage": {"gb_per_mo": 0.02}
    },
    "gcp": {
        "compute": {"vcpu_per_hr": 0.022, "ram_gb_per_hr": 0.003},
        "db": {"vcpu_per_hr": 0.034, "ram_gb_per_hr": 0.0048, "storage_gb_per_mo": 0.11},
        "storage": {"gb_per_mo": 0.026}
    }
}


def compute_cost(resource, cloud):
    # resource fields: vcpu, ram_gb
    p = PRICES[cloud]["compute"]
    vcpu = max(1, int(resource.get("vcpu", 2)))
    ram = float(resource.get("ram_gb", 4))
    hourly = vcpu * p["vcpu_per_hr"] + ram * p["ram_gb_per_hr"]
    return round(hourly * MONTHLY_HOURS, 2)


def db_cost(resource, cloud):
    # resource fields: vcpu, ram_gb, storage_gb
    p = PRICES[cloud]["db"]
    vcpu = max(1, int(resource.get("vcpu", 2)))
    ram = float(resource.get("ram_gb", 4))
    storage = float(resource.get("storage_gb", 20))
    hourly = vcpu * p["vcpu_per_hr"] + ram * p["ram_gb_per_hr"]
    monthly = hourly * MONTHLY_HOURS + storage * p["storage_gb_per_mo"]
    return round(monthly, 2)


def storage_cost(resource, cloud):
    p = PRICES[cloud]["storage"]
    size = float(resource.get("storage_gb", 100))
    monthly = size * p["gb_per_mo"]
    return round(monthly, 2)


def estimate_cost(resource, cloud):
    rtype = resource.get("type")
    if rtype == "compute":
        return compute_cost(resource, cloud)
    if rtype == "database":
        return db_cost(resource, cloud)
    if rtype == "storage":
        return storage_cost(resource, cloud)
    return 0.0

