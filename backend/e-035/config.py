SERVICES = [
    {
        "name": "web",
        "dockerfile": "services/web/Dockerfile",
        "allowed_bases": ["python"],
        "security_policy": {"max_critical_vulns": 0, "max_high_vulns": 5},
        "gates": [
            "PolicyGate",
            "SecurityGate",
            "BuildGate",
            "TestGate",
            "CanaryGate",
            "ManualApprovalGate",
        ],
    }
]

DATA_DIR = "data"
WORK_DIR = os.path.join(DATA_DIR, "working")

