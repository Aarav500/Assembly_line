import os
import sys
import json
from pathlib import Path

# Add parent directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from app import app


def main():
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    json_path = docs_dir / "openapi.json"
    yaml_path = docs_dir / "openapi.yaml"

    with app.test_client() as client:
        resp = client.get("/apispec_1.json")
        if resp.status_code != 200:
            raise SystemExit(
                f"Failed to fetch OpenAPI spec: status {resp.status_code}, body: {resp.data[:200]!r}"
            )
        spec = resp.get_json()

    # Write JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)

    # Write YAML
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True)

    print(f"Wrote {json_path} and {yaml_path}")


if __name__ == "__main__":
    main()
