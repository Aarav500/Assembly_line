import re

# Define secret detection rules
# Each rule: id, name, regex, severity, description, tags, multiline
RAW_RULES = [
    {
        "id": "AWS_ACCESS_KEY_ID",
        "name": "AWS Access Key ID",
        "regex": r"\bAKIA[0-9A-Z]{16}\b",
        "severity": "high",
        "description": "Potential AWS Access Key ID detected.",
        "tags": ["aws", "credentials"],
        "multiline": False,
    },
    {
        "id": "AWS_SECRET_ACCESS_KEY",
        "name": "AWS Secret Access Key",
        "regex": r"(?i)aws(.{0,20})?(secret|access)?(.{0,20})?key\s*[:=\"' ]{1,3}([A-Za-z0-9/+=]{40})",
        "severity": "critical",
        "description": "Potential AWS Secret Access Key detected.",
        "tags": ["aws", "credentials"],
        "multiline": False,
    },
    {
        "id": "GITHUB_TOKEN",
        "name": "GitHub Personal Access Token",
        "regex": r"\bghp_[A-Za-z0-9]{36}\b",
        "severity": "high",
        "description": "Potential GitHub token detected.",
        "tags": ["github", "token"],
        "multiline": False,
    },
    {
        "id": "SLACK_TOKEN",
        "name": "Slack Token",
        "regex": r"\bxox[baprs]-[A-Za-z0-9-]{10,48}\b",
        "severity": "high",
        "description": "Potential Slack token detected.",
        "tags": ["slack", "token"],
        "multiline": False,
    },
    {
        "id": "GOOGLE_API_KEY",
        "name": "Google API Key",
        "regex": r"\bAIza[0-9A-Za-z\-_]{35}\b",
        "severity": "high",
        "description": "Potential Google API Key detected.",
        "tags": ["google", "api"],
        "multiline": False,
    },
    {
        "id": "STRIPE_SECRET_KEY",
        "name": "Stripe Secret Key",
        "regex": r"\bsk_live_[0-9a-zA-Z]{24}\b",
        "severity": "high",
        "description": "Potential Stripe secret key detected.",
        "tags": ["stripe", "token"],
        "multiline": False,
    },
    {
        "id": "TWILIO_AUTH_TOKEN",
        "name": "Twilio Auth Token",
        "regex": r"(?i)twilio(.{0,20})?(auth|token)\s*[:=\"' ]{1,3}([A-Fa-f0-9]{32})",
        "severity": "medium",
        "description": "Potential Twilio auth token detected.",
        "tags": ["twilio", "token"],
        "multiline": False,
    },
    {
        "id": "PRIVATE_KEY_BLOCK",
        "name": "Private Key Block",
        "regex": r"-----BEGIN (?:RSA|DSA|EC|OPENSSH|PGP|PRIVATE) KEY-----[\s\S]+?-----END (?:RSA|DSA|EC|OPENSSH|PGP|PRIVATE) KEY-----",
        "severity": "critical",
        "description": "Private key block detected.",
        "tags": ["private-key"],
        "multiline": True,
    },
    {
        "id": "GENERIC_PASSWORD_ASSIGNMENT",
        "name": "Generic password assignment",
        "regex": r"(?i)\bpassword\b\s*[:=\"']\s*[^\n]*",
        "severity": "medium",
        "description": "Potential hardcoded password assignment.",
        "tags": ["password"],
        "multiline": False,
    },
]

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# Compile regex patterns
COMPILED_RULES = []
for r in RAW_RULES:
    flags = re.IGNORECASE | (re.DOTALL if r.get("multiline") else 0)
    comp = re.compile(r["regex"], flags)
    COMPILED_RULES.append({**r, "pattern": comp})

__all__ = ["COMPILED_RULES", "SEVERITY_ORDER"]

