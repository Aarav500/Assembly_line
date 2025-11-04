import os
import re
import time
import subprocess
from typing import Dict, Any

from registry import VulnRegistry


class GateResult:
    def __init__(self, status: str, message: str = "", data: Dict[str, Any] = None):
        self.status = status  # passed, failed, waiting, skipped
        self.message = message
        self.data = data or {}

    def to_dict(self):
        return {"status": self.status, "message": self.message, "data": self.data}


class GateContext:
    def __init__(self, run: Dict[str, Any]):
        self.run = run
        self.service = run["service"]
        self.working_dir = run["working_dir"]
        self.current_base = run["base_current"]
        self.target_base = run["base_target"]
        self.dockerfile_path = run["dockerfile"]


class PolicyGate:
    name = "PolicyGate"

    def run(self, ctx: GateContext) -> GateResult:
        base = ctx.target_base
        # Policies: no 'latest' tags, from allowed base image names
        if ":latest" in base or base.endswith(":latest"):
            return GateResult("failed", "Policy: 'latest' tag is not allowed")
        allowed = ctx.service.get("allowed_bases", [])
        base_name = base.split(":")[0]
        if base_name not in allowed:
            return GateResult("failed", f"Policy: base '{base_name}' not allowed; allowed: {allowed}")
        # Additional policy: only -slim variants
        if not base.split(":")[1].endswith("-slim"):
            return GateResult("failed", "Policy: only '-slim' variants allowed")
        return GateResult("passed", "Policy checks passed")


class SecurityGate:
    name = "SecurityGate"

    def __init__(self):
        self.vulns = VulnRegistry()

    def run(self, ctx: GateContext) -> GateResult:
        policy = ctx.service.get("security_policy", {})
        rec = self.vulns.get(ctx.target_base)
        crit = rec.get("critical", 0)
        high = rec.get("high", 0)
        max_c = policy.get("max_critical_vulns", 0)
        max_h = policy.get("max_high_vulns", 10)
        if crit > max_c:
            return GateResult("failed", f"Security: critical vulns {crit} > allowed {max_c}")
        if high > max_h:
            return GateResult("failed", f"Security: high vulns {high} > allowed {max_h}")
        return GateResult("passed", f"Security: critical={crit}, high={high}")


class BuildGate:
    name = "BuildGate"

    def run(self, ctx: GateContext) -> GateResult:
        # Simulate build by linting Dockerfile content and producing a build artifact
        df_out = os.path.join(ctx.working_dir, "Dockerfile.updated")
        if not os.path.exists(df_out):
            return GateResult("failed", "Build: updated Dockerfile not found")
        with open(df_out, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.startswith("FROM "):
            return GateResult("failed", "Build: Dockerfile must start with FROM")
        if "RUN" not in content and "CMD" not in content:
            return GateResult("failed", "Build: Dockerfile missing RUN or CMD")
        # produce a fake image artifact file
        artifact = os.path.join(ctx.working_dir, "image.artifact")
        with open(artifact, "w", encoding="utf-8") as f:
            f.write(f"image:{ctx.service['name']} base={ctx.target_base}\n")
        return GateResult("passed", "Build: simulated build succeeded", {"artifact": artifact})


class TestGate:
    name = "TestGate"

    def run(self, ctx: GateContext) -> GateResult:
        # Run the local test suite
        try:
            proc = subprocess.run(["pytest", "-q", "tests_sample"], cwd=".", capture_output=True, text=True, timeout=120)
            if proc.returncode != 0:
                return GateResult("failed", f"Tests failed:\n{proc.stdout}\n{proc.stderr}")
        except FileNotFoundError:
            return GateResult("failed", "pytest not installed")
        except subprocess.TimeoutExpired:
            return GateResult("failed", "Tests timed out")
        return GateResult("passed", "Tests passed")


class CanaryGate:
    name = "CanaryGate"

    def run(self, ctx: GateContext) -> GateResult:
        # Simulate canary doing health checks
        time.sleep(0.2)
        return GateResult("passed", "Canary: simulated checks passed")


class ManualApprovalGate:
    name = "ManualApprovalGate"

    def run(self, ctx: GateContext) -> GateResult:
        approved = bool(ctx.run.get("approved"))
        if approved:
            return GateResult("passed", "Approval received")
        return GateResult("waiting", "Waiting for manual approval")


GATE_CLASSES = {
    "PolicyGate": PolicyGate,
    "SecurityGate": SecurityGate,
    "BuildGate": BuildGate,
    "TestGate": TestGate,
    "CanaryGate": CanaryGate,
    "ManualApprovalGate": ManualApprovalGate,
}

