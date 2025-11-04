# Sample feature: Payments
FEATURE_INFO = {
    "name": "Payments",
    "description": "Payment processing via external provider",
    "owner": "team-billing",
}


def health_check():
    # Simulate a successful health check but with a warning detail
    # In a real app, verify provider API reachable, credentials loaded, etc.
    return True, "Provider reachable; sandbox mode"

