PRICING = {
    "currency": "USD",
    # GPU hourly on-demand rates in USD and relative discounts for spot/reserved
    "gpu": {
        "A100-80GB": {
            "on_demand": 4.10,
            "spot_discount": 0.70,       # 70% off on-demand
            "reserved_discount": 0.30    # 30% off on-demand
        },
        "V100-16GB": {
            "on_demand": 2.50,
            "spot_discount": 0.60,
            "reserved_discount": 0.25
        },
        "T4-16GB": {
            "on_demand": 0.35,
            "spot_discount": 0.50,
            "reserved_discount": 0.20
        },
        "L4-24GB": {
            "on_demand": 0.90,
            "spot_discount": 0.55,
            "reserved_discount": 0.22
        }
    },
    # Memory cost per GB-hour in USD (adjust to your provider)
    "memory_gb_hour": 0.00099,
}

