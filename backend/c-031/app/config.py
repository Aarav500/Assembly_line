# Centralized RBAC policy configuration
# - SENSITIVE_PATTERNS: URL regex patterns mapped to roles required to access them
# - SENSITIVE_LEVELS: semantic levels usable via @sensitive(level)

SENSITIVE_PATTERNS = [
    {"pattern": r"^/admin($|/)", "roles": {"admin"}},
    {"pattern": r"^/billing($|/)", "roles": {"admin", "billing"}},
    {"pattern": r"^/users/\\d+/secrets($|/)", "roles": {"admin", "security"}},
    {"pattern": r"^/tokens($|/)", "roles": {"admin", "security"}},
]

SENSITIVE_LEVELS = {
    # Low sensitivity: broader access
    "low": {"support", "auditor", "admin"},
    # Medium: tighter, typical for logs, audit, moderate-risk data
    "medium": {"security", "admin"},
    # High: admin-only
    "high": {"admin"},
}

