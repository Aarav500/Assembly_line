from __future__ import annotations
import argparse
import json
import os
import sys

from manifest_checker.checker import run_check


def main() -> int:
    parser = argparse.ArgumentParser(description="Manifest checker - prevent removal/disable of required features")
    parser.add_argument("--manifest-path", default=os.environ.get("MANIFEST_PATH", "manifest.json"), help="Path to the manifest file (json/yaml)")
    parser.add_argument("--required-path", default=os.environ.get("REQUIRED_FEATURES_PATH", "manifest_checker/required_features.yaml"), help="Path to required features config (yaml/json)")
    parser.add_argument("--features-key", default=os.environ.get("MANIFEST_FEATURES_KEY", "features"), help="Key in manifest that contains features")
    parser.add_argument("--base-ref", default=os.environ.get("BASE_REF", os.environ.get("GIT_BASE_REF", "")), help="Git ref to compare against (e.g., origin/main)")
    parser.add_argument("--json", action="store_true", help="Print JSON output")

    args = parser.parse_args()

    base_ref = args.base_ref or None

    result = run_check(
        manifest_path=args.manifest_path,
        required_path=args.required_path,
        features_key=args.features_key,
        base_ref=base_ref,
    )

    if args.json or os.environ.get("CI"):
        print(json.dumps(result, indent=2))
    else:
        if result["ok"]:
            print("Manifest check passed: all required features present and enabled.")
        else:
            if result["missing_required_features"]:
                print("Missing required features: " + ", ".join(result["missing_required_features"]))
            if result["disabled_required_features"]:
                print("Required features disabled or missing 'enabled': " + ", ".join(result["disabled_required_features"]))
            if result["removed_required_features_vs_base"]:
                print("Required features removed vs base (" + (result["base_ref"] or "?") + "): " + ", ".join(result["removed_required_features_vs_base"]))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

