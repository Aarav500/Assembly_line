#!/usr/bin/env python3
import json
import os
import pathlib
import time
import sys

def main() -> int:
    region = os.getenv("GEO_REGION", "us-east-1")
    target = pathlib.Path(".deploy")
    target.mkdir(exist_ok=True)

    info = {
        "region": region,
        "app": "geo-flask",
        "status": "deployed",
        "timestamp": int(time.time()),
    }

    out = target / "deployment_info.json"
    out.write_text(json.dumps(info, indent=2))

    print(f"[deploy] Simulated deployment of geo-flask to {region}")
    print(f"[deploy] Wrote {out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

