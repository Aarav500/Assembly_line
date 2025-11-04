from typing import Any, Dict, List


def _eco_from_type(pkg_type: str) -> str:
    t = (pkg_type or "").lower()
    if any(x in t for x in ["python", "pip"]):
        return "python"
    if any(x in t for x in ["node", "npm", "yarn"]):
        return "node"
    if any(x in t for x in ["maven", "gradle", "java"]):
        return "java"
    if any(x in t for x in ["golang", "go"]):
        return "go"
    if any(x in t for x in ["ruby", "gem"]):
        return "ruby"
    if any(x in t for x in ["dotnet", "nuget"]):
        return "dotnet"
    if any(x in t for x in ["alpine", "apk"]):
        return "alpine"
    if any(x in t for x in ["debian", "ubuntu", "apt", "dpkg"]):
        return "debian"
    if any(x in t for x in ["rhel", "centos", "rpm", "yum", "microdnf", "dnf"]):
        return "rhel"
    if any(x in t for x in ["os", "linux", "distroless"]):
        return "os"
    return t or "unknown"


def _ecosystem_tip(eco: str) -> str:
    eco = eco.lower()
    if eco == "python":
        return "Pin and upgrade affected packages in requirements.txt or pyproject.toml (e.g., pip install <pkg>==<fixed>). Use pip-audit or pip-tools to manage upgrades."
    if eco == "node":
        return "Run npm audit fix --force where safe, or bump versions in package.json/package-lock.json. Consider using npm/yarn resolutions."
    if eco == "java":
        return "Upgrade dependency versions in pom.xml/build.gradle to fixed releases. Consider using Maven Enforcer/Versions plugin."
    if eco == "go":
        return "Update go.mod to require a fixed version (go get -u <module>@<version>) and run go mod tidy."
    if eco == "ruby":
        return "Update Gemfile.lock via bundle update <gem> to a version containing a fix."
    if eco == "dotnet":
        return "Upgrade the NuGet package to a fixed version in the .csproj/.fsproj and restore packages."
    if eco == "alpine":
        return "Rebuild image with latest base and run: apk update && apk upgrade --no-cache."
    if eco == "debian":
        return "Rebuild image and run: apt-get update && apt-get -y upgrade or apt-get install -y <pkg>=<fixed>."
    if eco == "rhel":
        return "Rebuild image and run: yum update -y or microdnf update -y for RHEL-based images."
    return "Upgrade the affected package to a fixed version and rebuild/redeploy."


def _generic_hardening(target_type: str) -> List[str]:
    tips = [
        "Introduce CI checks to fail builds on HIGH/CRITICAL vulnerabilities.",
        "Pin dependency versions to avoid accidental vulnerable upgrades.",
        "Enable Dependabot/Renovate to keep dependencies updated.",
        "Run scans on every commit and regularly refresh vulnerability databases.",
    ]
    if target_type == "image":
        tips.extend([
            "Use minimal/base images (e.g., distroless, alpine) when appropriate.",
            "Prefer multi-stage builds to reduce final image attack surface.",
            "Regularly rebuild images to pick up OS package fixes.",
        ])
    else:
        tips.extend([
            "Avoid wildcard version ranges; use exact or caret constraints with care.",
            "Remove unused dependencies and dev packages from production builds.",
        ])
    return tips


def generate_mitigations(normalized_findings: List[Dict[str, Any]], target_type: str) -> List[Dict[str, Any]]:
    mitigations: List[Dict[str, Any]] = []

    # Deduplicate by (id, pkgName, source)
    seen = set()

    for f in normalized_findings:
        key = (f.get("id"), f.get("pkgName"), f.get("source"))
        if key in seen:
            continue
        seen.add(key)

        category = f.get("category")
        pkg = f.get("pkgName")
        fid = f.get("id")
        sev = (f.get("severity") or "").upper()
        eco = _eco_from_type(f.get("pkgType") or f.get("type") or "")
        fixed = f.get("fixedVersion")
        refs = f.get("references") or []

        if category == "misconfiguration":
            recommendation = f"Review and remediate configuration: {f.get('title') or fid}. Follow best practices for the target and set secure defaults."
            mitigations.append({
                "vulnerabilityId": fid,
                "pkgName": None,
                "severity": sev,
                "recommendation": recommendation,
                "ecosystem": eco,
                "references": refs[:5],
            })
            continue

        # Vulnerabilities
        if fixed:
            rec = f"Upgrade {pkg} to {fixed} or later."
        else:
            rec = f"Check upstream for patches or workarounds for {pkg}. Consider replacing or removing the dependency if unmaintained."

        eco_tip = _ecosystem_tip(eco)
        recommendation = f"{rec} {eco_tip}"

        if sev in ("CRITICAL", "HIGH") and target_type == "image" and eco in ("alpine", "debian", "rhel", "os"):
            recommendation += " Rebuild from the latest base image to incorporate OS-level fixes."

        mitigations.append({
            "vulnerabilityId": fid,
            "pkgName": pkg,
            "severity": sev,
            "recommendation": recommendation,
            "ecosystem": eco,
            "references": refs[:5],
        })

    # Add generic hardening last
    generic = _generic_hardening(target_type)
    for tip in generic:
        mitigations.append({
            "vulnerabilityId": None,
            "pkgName": None,
            "severity": None,
            "recommendation": tip,
            "ecosystem": None,
            "references": [],
        })

    return mitigations

