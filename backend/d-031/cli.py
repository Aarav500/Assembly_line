import argparse
import json
import sys
from compliance.runner import run_checks
from compliance.config import load_config


def main():
    parser = argparse.ArgumentParser(description="Run GDPR/HIPAA compliance checks")
    parser.add_argument("--config", help="Path to compliance YAML/JSON config", default=None)
    parser.add_argument("--format", help="Output format: json, summary, both", default="both")
    parser.add_argument("--output", help="Path to write JSON report", default="compliance-report.json")
    parser.add_argument("--fail-on", help="Severity threshold to fail: low|medium|high|none", default="medium")
    parser.add_argument("--only", help="Only run a category: gdpr|hipaa", default=None)
    parser.add_argument("--strict", action="store_true", help="Equivalent to --fail-on low")

    args = parser.parse_args()

    fail_on = "low" if args.strict else args.fail_on

    # Load config (path overrides env/defaults)
    config = load_config(path=args.config)

    report = run_checks(config=config, only=args.only, fail_on=fail_on)

    # Output handling
    fmt = args.format.lower()
    exit_code = report.get("exit_code", 0)

    if fmt in ("summary", "both"):
        summary = report.get("summary", {})
        print("Compliance Report Summary")
        print(f" - Total checks: {summary.get('total', 0)}")
        print(f" - Passed: {summary.get('passed', 0)}")
        print(f" - Failed: {summary.get('failed', 0)}")
        print(f" - Skipped: {summary.get('skipped', 0)}")
        print(f" - Fail-on threshold: {summary.get('fail_on')}")
        if summary.get('failed', 0) > 0:
            print("Failed checks (id: title -> message):")
            for r in report.get("results", []):
                if r.get("status") == "fail":
                    print(f"   - {r['id']}: {r['title']} -> {r['message']}")

    if fmt in ("json", "both"):
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"JSON report written to {args.output}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

