# Sample feature: Search
FEATURE_INFO = {
    "name": "Search",
    "description": "Full-text search across content",
    "owner": "team-core",
}


def health_check():
    # Simulate a failing health check
    # In a real app, verify index connectivity, schema version, etc.
    return False, "Index unreachable: connection timeout"

