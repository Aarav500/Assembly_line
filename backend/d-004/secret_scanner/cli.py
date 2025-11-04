from __future__ import annotations
import json
import sys
import click
from typing import List, Optional

from . import scanner
from . import config as cfg
from .baseline import Baseline


def exit_code_for_findings(findings, fail_on: str) -> int:
    threshold_lvl = scanner.severity_to_level(fail_on)
    for f in findings:
        if scanner.severity_to_level(f.get("severity", "low")) >= threshold_lvl:
            return 1
    return 0


@click.group()
def cli():
    """Secret scanning CLI"""


@cli.command()
@click.argument("paths", nargs=-1)
@click.option("--staged", is_flag=True, help="Scan staged files from git index")
@click.option("--config", "config_path", default=".secretscan.yml", help="Config path")
@click.option("--baseline", "baseline_path", default=".secrets.baseline.json", help="Baseline file path")
@click.option("--fail-on", "fail_on", default="medium", help="Fail if at or above severity (low, medium, high, critical)")
@click.option("--json-out/--no-json-out", default=True, help="Output results as JSON")
@click.option("--update-baseline", is_flag=True, help="Add current findings to baseline and write file")
@click.option("--verbose", is_flag=True, help="Verbose output")
def scan(paths: List[str], staged: bool, config_path: str, baseline_path: str, fail_on: str, json_out: bool, update_baseline: bool, verbose: bool):
    """Scan files or staged changes for secrets."""
    conf = cfg.load_config(config_path)
    base = Baseline.load(baseline_path)

    all_findings = []

    targets: List[str] = list(paths)
    staged_map = {}

    if staged:
        targets = scanner.list_staged_files()
        if verbose:
            click.echo(f"Found {len(targets)} staged files")
        for p in targets:
            content = scanner.read_staged_file(p)
            staged_map[p] = content

    for p in targets:
        if staged:
            content = staged_map.get(p)
            if content is None:
                # fallback to disk
                fnds = scanner.scan_file(p, conf, base)
            else:
                fnds = scanner.scan_content(content, p, conf, base)
        else:
            fnds = scanner.scan_file(p, conf, base)
        all_findings.extend(fnds)

    if update_baseline:
        # Add all current findings to baseline and save
        for f in all_findings:
            base.add(f.get("fingerprint"))
        base.save(baseline_path)
        if verbose:
            click.echo(f"Baseline updated with {len(all_findings)} findings -> {baseline_path}")
        # When updating baseline, exit 0
        sys.exit(0)

    if json_out:
        click.echo(json.dumps({
            "count": len(all_findings),
            "findings": all_findings,
        }, indent=2))
    else:
        if not all_findings:
            click.echo("No secrets detected.")
        else:
            for f in all_findings:
                click.echo(f"{f['file']}:{f['line']}:{f['column']} {f['severity'].upper()} {f['rule_id']} - {f['message']}")

    code = exit_code_for_findings(all_findings, fail_on)
    sys.exit(code)


if __name__ == "__main__":
    cli()

