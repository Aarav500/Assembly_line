# Sample feature: Authentication
FEATURE_INFO = {
    "name": "Authentication",
    "description": "User login, logout, and session management",
    "owner": "team-security",
}


def health_check():
    # Simulate a successful health check
    # In a real app, verify DB connectivity, password hashing config, etc.
    return True, "Auth service responding"

