import os
import re
from typing import Dict, Any, List, Optional

from .utils import list_files, glob_find, has_any, read_text_safe, parse_coverage_xml, parse_coverage_from_badges, yaml_load_safe, count_python_files


def _detect_tests(root: str) -> Dict[str, Any]:
    tests_dir = os.path.isdir(os.path.join(root, "tests")) or os.path.isdir(os.path.join(root, "test"))
    test_files = glob_find(root, [
        "tests/**/*.py", "tests/*.py", "test/**/*.py", "test/*.py", "**/test_*.py", "**/*_test.py"
    ])
    coverage_xml_paths = [
        p for p in [
            os.path.join(root, "coverage.xml"),
            os.path.join(root, "reports", "coverage.xml"),
            os.path.join(root, "build", "coverage.xml")
        ] if os.path.exists(p)
    ]
    coverage_xml_pct: Optional[float] = None
    for p in coverage_xml_paths:
        coverage_xml_pct = parse_coverage_xml(read_text_safe(p))
        if coverage_xml_pct is not None:
            break

    coverage_cfg_present = any([
        os.path.exists(os.path.join(root, ".coveragerc")),
        any("[coverage:" in read_text_safe(p) for p in [
            os.path.join(root, "setup.cfg"),
        ] if os.path.exists(p)),
        ("[tool.coverage" in read_text_safe(os.path.join(root, "pyproject.toml"))) if os.path.exists(os.path.join(root, "pyproject.toml")) else False
    ])

    # Parse coverage badge from README if possible
    readme_paths = [
        p for p in [
            os.path.join(root, "README.md"),
            os.path.join(root, "README.rst"),
            os.path.join(root, "README.MD"),
            os.path.join(root, "Readme.md")
        ] if os.path.exists(p)
    ]
    badge_pct = None
    for p in readme_paths:
        badge_pct = parse_coverage_from_badges(read_text_safe(p))
        if badge_pct is not None:
            break

    # Detect CI steps that run tests
    ci_test = _ci_has_tests(root)

    code_files = count_python_files(root, exclude_dirs=["tests", "test"]) or 1

    return {
        "has_tests_dir": bool(tests_dir),
        "test_files_count": len(test_files),
        "code_files_count": int(code_files),
        "coverage_config_present": bool(coverage_cfg_present),
        "coverage_percent": coverage_xml_pct if coverage_xml_pct is not None else badge_pct,
        "ci_has_tests": bool(ci_test),
        "evidence": {
            "test_files": [os.path.relpath(p, root) for p in test_files][:50],
            "coverage_xml_found": [os.path.relpath(p, root) for p in coverage_xml_paths],
            "ci_test_workflows": ci_test.get("workflows", []) if isinstance(ci_test, dict) else []
        }
    }


def _ci_has_tests(root: str) -> Dict[str, Any]:
    workflows = glob_find(root, [".github/workflows/*.yml", ".github/workflows/*.yaml"])
    found = []
    for wf in workflows:
        text = read_text_safe(wf)
        y = yaml_load_safe(text)
        if not isinstance(y, dict):
            continue
        jobs = y.get("jobs") or {}
        if not isinstance(jobs, dict):
            continue
        for job_name, job_def in jobs.items():
            steps = (job_def or {}).get("steps") or []
            if not isinstance(steps, list):
                continue
            for st in steps:
                if not isinstance(st, dict):
                    continue
                name = (st.get("name") or "").lower()
                run = (st.get("run") or "").lower()
                uses = (st.get("uses") or "").lower()
                if any(k in name or k in run for k in ["pytest", "tox", "unittest", "nose", "coverage run", "python -m pytest", "pytest -q"]):
                    found.append(os.path.relpath(wf, root))
                    break
                if "pytest-action" in uses or "tox" in uses:
                    found.append(os.path.relpath(wf, root))
                    break
    return {"has": bool(found), "workflows": found}


def _detect_security(root: str) -> Dict[str, Any]:
    has_security_md = has_any(root, ["SECURITY.md", "security.md", "docs/SECURITY.md"])
    dependabot = has_any(root, [".github/dependabot.yml", ".github/dependabot.yaml"]) 
    codeql_workflow = False
    codeql_workflows = []
    for wf in glob_find(root, [".github/workflows/*.yml", ".github/workflows/*.yaml"]):
        text = read_text_safe(wf)
        if "codeql" in text.lower() or "github/codeql" in text.lower():
            codeql_workflow = True
            codeql_workflows.append(os.path.relpath(wf, root))

    bandit_config = any([
        has_any(root, ["bandit.yaml", ".bandit"]),
    ])

    precommit_cfg = None
    for p in [".pre-commit-config.yaml", ".pre-commit-config.yml"]:
        f = os.path.join(root, p)
        if os.path.exists(f):
            precommit_cfg = f
            break
    precommit_text = read_text_safe(precommit_cfg) if precommit_cfg else ""
    precommit_has_bandit = "id: bandit" in precommit_text
    precommit_has_detect_secrets = ("detect-secrets" in precommit_text) or ("gitleaks" in precommit_text) or ("trufflehog" in precommit_text)

    secrets_configs = glob_find(root, ["*gitleaks*.toml", "*gitleaks*.yaml", "*gitleaks*.yml", ".secrets*.yaml", ".secrets*.yml"]) 

    # Dependency pinning check
    req_files = glob_find(root, ["requirements.txt", "requirements-*.txt", "req*.txt", "constraints.txt"]) 
    pinned_total = 0
    total_deps = 0
    for rf in req_files:
        text = read_text_safe(rf)
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            # Rough parse: treat URLs and editable installs as unpinned
            if s.startswith("-e") or s.startswith("git+"):
                total_deps += 1
                continue
            total_deps += 1
            # Consider '==' as pinned. '~=' and '>=' etc are not fully pinned
            if "==" in s and not s.endswith("=="):
                pinned_total += 1
    lock_files_present = any([
        os.path.exists(os.path.join(root, "poetry.lock")),
        os.path.exists(os.path.join(root, "Pipfile.lock")),
        os.path.exists(os.path.join(root, "requirements.lock"))
    ])
    deps_pinned_ratio = 1.0 if lock_files_present else (float(pinned_total) / float(total_deps) if total_deps > 0 else 0.0)

    return {
        "has_security_md": bool(has_security_md),
        "has_dependabot": bool(dependabot),
        "has_codeql": bool(codeql_workflow),
        "codeql_workflows": codeql_workflows,
        "has_bandit_config": bool(bandit_config or precommit_has_bandit),
        "has_secrets_scanning": bool(precommit_has_detect_secrets or len(secrets_configs) > 0),
        "deps_pinned_ratio": max(0.0, min(1.0, deps_pinned_ratio)),
        "evidence": {
            "precommit_config": os.path.relpath(precommit_cfg, root) if precommit_cfg else None,
            "secrets_configs": [os.path.relpath(p, root) for p in secrets_configs],
            "requirement_files": [os.path.relpath(p, root) for p in req_files],
        }
    }


def _detect_infra(root: str) -> Dict[str, Any]:
    dockerfile = any([
        os.path.exists(os.path.join(root, "Dockerfile")),
        os.path.exists(os.path.join(root, "docker", "Dockerfile"))
    ])
    docker_compose = len(glob_find(root, ["docker-compose.simple.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"])) > 0

    # Kubernetes detection: any yaml containing apiVersion and kind under k8s-like dirs
    k8s_candidates = glob_find(root, ["k8s/**/*.yml", "k8s/**/*.yaml", "kubernetes/**/*.yml", "kubernetes/**/*.yaml", "deploy/**/*.yml", "deploy/**/*.yaml"]) 
    has_k8s = False
    k8s_files: List[str] = []
    for p in k8s_candidates:
        text = read_text_safe(p)
        if ("apiVersion:" in text) and ("kind:" in text):
            has_k8s = True
            k8s_files.append(os.path.relpath(p, root))

    terraform_files = glob_find(root, ["**/*.tf"]) 

    ci_workflows = glob_find(root, [".github/workflows/*.yml", ".github/workflows/*.yaml"]) 
    other_ci = []
    for f in [".gitlab-ci.yml", ".circleci/config.yml", "azure-pipelines.yml", "Jenkinsfile"]:
        if os.path.exists(os.path.join(root, f)):
            other_ci.append(f)

    makefile = has_any(root, ["Makefile", "makefile"])

    return {
        "has_dockerfile": bool(dockerfile),
        "has_docker_compose": bool(docker_compose),
        "has_k8s": bool(has_k8s),
        "k8s_files": k8s_files,
        "has_terraform": bool(len(terraform_files) > 0),
        "ci_workflows_count": len(ci_workflows) + len(other_ci),
        "ci_workflows": [os.path.relpath(p, root) for p in ci_workflows] + other_ci,
        "has_makefile": bool(makefile)
    }


def _detect_docs(root: str) -> Dict[str, Any]:
    readme = has_any(root, ["README.md", "README.rst", "README.txt", "Readme.md", "README.MD"]) 
    contributing = has_any(root, ["CONTRIBUTING.md", "contributing.md", "docs/CONTRIBUTING.md"]) 
    code_of_conduct = has_any(root, ["CODE_OF_CONDUCT.md", "code_of_conduct.md"]) 
    docs_dir = os.path.isdir(os.path.join(root, "docs"))
    mkdocs_cfg = has_any(root, ["mkdocs.yml", "mkdocs.yaml"]) 
    sphinx_conf = os.path.exists(os.path.join(root, "docs", "conf.py"))
    changelog = has_any(root, ["CHANGELOG.md", "Changelog.md", "CHANGELOG.rst"]) 
    license_present = any([
        has_any(root, ["LICENSE", "LICENSE.md", "LICENSE.txt"]),
    ])

    return {
        "has_readme": bool(readme),
        "has_contributing": bool(contributing),
        "has_code_of_conduct": bool(code_of_conduct),
        "has_docs_dir": bool(docs_dir),
        "has_docs_site": bool(mkdocs_cfg or sphinx_conf),
        "has_changelog": bool(changelog),
        "has_license": bool(license_present)
    }


def scan_project(root: str) -> Dict[str, Any]:
    root = os.path.abspath(root)
    return {
        "tests": _detect_tests(root),
        "security": _detect_security(root),
        "infra": _detect_infra(root),
        "docs": _detect_docs(root)
    }

