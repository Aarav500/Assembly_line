import os

API_NAME = os.getenv('API_NAME', 'example-api')

# Versions must be strings in MAJOR.MINOR format
SUPPORTED_VERSIONS = [
    '1.0',
    '1.1',
    '2.0',
]

LATEST_VERSION = '2.0'

# Deprecation metadata per version
# Sunset is an RFC 1123 or ISO date string for human consumption
DEPRECATED_VERSIONS = {
    '1.0': {
        'sunset': '2026-01-01',
        'link': 'https://example.com/migrations/v1.0_to_2.0',
        'notice': 'API v1.0 is deprecated. Please migrate to v2.0. See migration guide.'
    }
}

# Documentation base URL for migration guides
MIGRATIONS_BASE_URL = os.getenv('MIGRATIONS_BASE_URL', 'https://example.com/migrations')

# If True, when a requested version is not available, serve the closest available version
# with compatibility adapters. If False, return 406 Not Acceptable for unsupported requests.
ENABLE_FLEXIBLE_NEGOTIATION = True

# If True, include verbose Warning headers when downgrading/upgrading between versions
INCLUDE_WARNING_HEADERS = True

# If True, log deprecation warnings and negotiation outcomes
LOG_VERSION_EVENTS = True

