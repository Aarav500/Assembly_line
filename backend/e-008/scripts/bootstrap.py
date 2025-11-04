#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ARGO_NS = "argo-cd"
FLUX_NS = "flux-system"

PLACEHOLDER_URL = "__GIT_URL__"
PLACEHOLDER_BRANCH = "__GIT_BRANCH__"


def run(cmd, check=True):
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=check)


def kubectl_apply_file(path, dry_run=False):
    cmd = ["kubectl", "apply", "-f", str(path)]
    if dry_run:
        cmd.extend(["--dry-run=client"])
    run(cmd)


def kubectl_apply_kustomize(dir_path, dry_run=False):
    cmd = ["kubectl", "apply", "-k", str(dir_path)]
    if dry_run:
        cmd.extend(["--dry-run=client"])
    run(cmd)


def render_with_placeholders(src_path, git_url, git_branch):
    raw = Path(src_path).read_text()
    raw = raw.replace(PLACEHOLDER_URL, git_url)
    raw = raw.replace(PLACEHOLDER_BRANCH, git_branch)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml")
    tmp.write(raw.encode("utf-8"))
    tmp.flush()
    tmp.close()
    return tmp.name


def bootstrap_argocd(git_url, git_branch, dry_run=False, namespace=ARGO_NS):
    # Namespace
    kubectl_apply_file(ROOT / "argo" / "namespace.yaml", dry_run=dry_run)
    # Install Argo CD
    kubectl_apply_kustomize(ROOT / "argo" / "install", dry_run=dry_run)
    # Apply root application (app-of-apps) pointing to this repo/path
    root_app_file = render_with_placeholders(ROOT / "argo" / "root-application.yaml", git_url, git_branch)
    try:
        kubectl_apply_file(root_app_file, dry_run=dry_run)
    finally:
        try:
            os.unlink(root_app_file)
        except Exception:
            pass


def bootstrap_flux(git_url, git_branch, dry_run=False, namespace=FLUX_NS):
    # Namespace
    kubectl_apply_file(ROOT / "flux" / "namespace.yaml", dry_run=dry_run)
    # Install Flux controllers
    kubectl_apply_kustomize(ROOT / "flux" / "install", dry_run=dry_run)
    # Apply GitRepository and Kustomizations with placeholders
    for rel in ["gitrepository.yaml", "kustomization-dev.yaml", "kustomization-prod.yaml"]:
        rendered = render_with_placeholders(ROOT / "flux" / rel, git_url, git_branch)
        try:
            kubectl_apply_file(rendered, dry_run=dry_run)
        finally:
            try:
                os.unlink(rendered)
            except Exception:
                pass


def main():
    p = argparse.ArgumentParser(description="Bootstrap ArgoCD/Flux and configure GitOps applications")
    p.add_argument("--provider", choices=["argocd", "flux", "both"], default="both")
    p.add_argument("--git-url", required=True, help="Git repository URL that contains this repo (HTTPS or SSH)")
    p.add_argument("--branch", default="main", help="Git branch for GitOps reconciliation")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--argo-namespace", default=ARGO_NS)
    p.add_argument("--flux-namespace", default=FLUX_NS)
    args = p.parse_args()

    try:
        if args.provider in ("argocd", "both"):
            bootstrap_argocd(args.git_url, args.branch, dry_run=args.dry_run, namespace=args.argo_namespace)
        if args.provider in ("flux", "both"):
            bootstrap_flux(args.git_url, args.branch, dry_run=args.dry_run, namespace=args.flux_namespace)
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()

