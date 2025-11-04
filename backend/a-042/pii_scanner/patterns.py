import re

# Define PII and secret patterns
# Each entry: {
#   'name': str,
#   'regex': compiled pattern,
#   'severity': 'low'|'medium'|'high',
#   'description': str,
#   'post_filter': callable or None  # optional validator e.g., Luhn
# }

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
SSN_RE = re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
# Raw candidate credit card pattern; validated with Luhn in post_filter
CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
AWS_ACCESS_KEY_ID_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")
SLACK_TOKEN_RE = re.compile(r"\bxox(?:p|b|o|a|r|s)-[A-Za-z0-9-]{10,}\b")
GITHUB_TOKEN_RE = re.compile(r"\bgh[pous]_[A-Za-z0-9]{36}\b")
GITHUB_PAT_RE = re.compile(r"\bgithub_pat_[0-9A-Za-z_]{22,}\b")
PRIVATE_KEY_BLOCK_RE = re.compile(r"-----BEGIN (?:RSA |DSA |EC )?PRIVATE KEY-----")
DOB_RE = re.compile(r"\b(?:\d{4}[/-](?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])|(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])[/-]\d{4})\b")
IPV6_RE = re.compile(r"\b(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|(::1))\b")

PATTERN_DEFINITIONS = [
    {
        'name': 'email',
        'regex': EMAIL_RE,
        'severity': 'medium',
        'description': 'Email address',
    },
    {
        'name': 'phone',
        'regex': PHONE_RE,
        'severity': 'low',
        'description': 'US phone number',
    },
    {
        'name': 'ssn',
        'regex': SSN_RE,
        'severity': 'high',
        'description': 'US Social Security Number',
    },
    {
        'name': 'credit_card',
        'regex': CREDIT_CARD_RE,
        'severity': 'high',
        'description': 'Credit card number candidate',
        'post_filter': 'luhn',
    },
    {
        'name': 'ipv4',
        'regex': IPV4_RE,
        'severity': 'medium',
        'description': 'IPv4 address',
    },
    {
        'name': 'ipv6',
        'regex': IPV6_RE,
        'severity': 'medium',
        'description': 'IPv6 address',
    },
    {
        'name': 'aws_access_key_id',
        'regex': AWS_ACCESS_KEY_ID_RE,
        'severity': 'high',
        'description': 'AWS Access Key ID',
    },
    {
        'name': 'google_api_key',
        'regex': GOOGLE_API_KEY_RE,
        'severity': 'high',
        'description': 'Google API Key',
    },
    {
        'name': 'slack_token',
        'regex': SLACK_TOKEN_RE,
        'severity': 'high',
        'description': 'Slack token',
    },
    {
        'name': 'github_token',
        'regex': GITHUB_TOKEN_RE,
        'severity': 'high',
        'description': 'GitHub token',
    },
    {
        'name': 'github_pat',
        'regex': GITHUB_PAT_RE,
        'severity': 'high',
        'description': 'GitHub Personal Access Token',
    },
    {
        'name': 'private_key_block',
        'regex': PRIVATE_KEY_BLOCK_RE,
        'severity': 'high',
        'description': 'Private key block header',
    },
    {
        'name': 'dob',
        'regex': DOB_RE,
        'severity': 'medium',
        'description': 'Date of birth (YYYY-MM-DD or MM/DD/YYYY)',
    },
]

# Sensitive filenames to flag even without content matches
SENSITIVE_FILENAME_GLOBS = [
    '.env', '.env.*',
    '*.pem', '*.key', '*.pfx', '*.p12', '*.der',
    'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519',
    '.aws/credentials', '.git-credentials',
    '*credential*', '*secret*', '*passwd*', '*shadow*',
    'config.yml', 'config.yaml', 'secrets.yml', 'secrets.yaml',
]
