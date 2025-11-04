import json
import os
import shutil
import subprocess
from pathlib import Path


BUILD_DIR = Path("build/sbom")
BUILD_DIR.mkdir(parents=True, exist_ok=True)


def run(cmd):
    print(f"[generate_sbom] Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=True)


def main():
    output_format = os.getenv("SBOM_FORMAT", "cyclonedx-json").lower()
    if output_format not in {"cyclonedx-json", "cyclonedx-xml"}:
        print(f"Unsupported SBOM_FORMAT: {output_format}. Falling back to cyclonedx-json")
        output_format = "cyclonedx-json"

    out_path = BUILD_DIR / ("cyclonedx.json" if output_format.endswith("json") else "cyclonedx.xml")

    # Prefer cyclonedx-py, then cyclonedx-bom
    candidates = []

    if shutil.which("cyclonedx-py"):
        if output_format.endswith("json"):
            candidates.append(["cyclonedx-py", "-e", "-j", "-o", str(out_path)])
        else:
            candidates.append(["cyclonedx-py", "-e", "-o", str(out_path)])
        # Try using requirements as a fallback
        if Path("requirements.txt").exists():
            if output_format.endswith("json"):
                candidates.append(["cyclonedx-py", "-e", "-j", "-r", "requirements.txt", "-o", str(out_path)])
            else:
                candidates.append(["cyclonedx-py", "-e", "-r", "requirements.txt", "-o", str(out_path)])

    if shutil.which("cyclonedx-bom"):
        # Some versions provide a unified CLI. Try sensible flags.
        if output_format.endswith("json"):
            candidates.append(["cyclonedx-bom", "-o", str(out_path), "-j", "-e"])  # may vary by version
        else:
            candidates.append(["cyclonedx-bom", "-o", str(out_path), "-e"])  # XML default
        if Path("requirements.txt").exists():
            if output_format.endswith("json"):
                candidates.append(["cyclonedx-bom", "-o", str(out_path), "-j", "-e", "-r", "requirements.txt"])  # may vary
            else:
                candidates.append(["cyclonedx-bom", "-o", str(out_path), "-e", "-r", "requirements.txt"])  # may vary

    if not candidates:
        raise SystemExit(
            "Neither 'cyclonedx-py' nor 'cyclonedx-bom' is installed. Install with: pip install cyclonedx-bom"
        )

    last_err = None
    for cmd in candidates:
        try:
            run(cmd)
            print(f"[generate_sbom] SBOM written to {out_path}")
            return
        except subprocess.CalledProcessError as e:
            last_err = e
            print(f"[generate_sbom] Command failed: {' '.join(cmd)}")

    if last_err:
        raise SystemExit(last_err.returncode)


if __name__ == "__main__":
    main()

