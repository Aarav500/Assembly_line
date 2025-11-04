import os
import json
import socket
import datetime as dt
from typing import Dict, List


def build_spdx_like_sbom(packages: List[Dict], project_name: str = None) -> Dict:
    try:
        created = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        name = project_name or os.path.basename(os.getcwd()) or "python-project"

        components = []
        for p in packages:
            try:
                lic = p.get("license") or {}
                comp = {
                    "name": p.get("name"),
                    "version": p.get("version"),
                    "purl": p.get("purl"),
                    "licenses": [{k: v for k, v in {
                        "id": lic.get("id"),
                        "name": lic.get("name"),
                        "source": lic.get("source"),
                    }.items() if v is not None}] if (lic.get("id") or lic.get("name")) else [],
                    "supplier": p.get("author"),
                    "description": p.get("summary"),
                    "homepage": p.get("home_page"),
                }
                components.append(comp)
            except (AttributeError, TypeError, KeyError) as e:
                # Skip malformed package entries
                continue

        doc = {
            "sbomFormat": "SPDX-2.3-lite",
            "name": f"SBOM for {name}",
            "created": created,
            "creator": {
                "tool": "license-sbom-detector/0.1",
                "host": socket.gethostname(),
            },
            "components": components,
        }
        return doc
    except Exception as e:
        # Return minimal valid SBOM on error
        return {
            "sbomFormat": "SPDX-2.3-lite",
            "name": "SBOM (error)",
            "created": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "creator": {
                "tool": "license-sbom-detector/0.1",
                "host": "unknown",
            },
            "components": [],
        }


def summarize_licenses(packages: List[Dict]) -> List[Dict]:
    try:
        counts = {}
        for p in packages:
            try:
                lic = (p.get("license") or {}).get("id") or (p.get("license") or {}).get("name") or "UNKNOWN"
                counts[lic] = counts.get(lic, 0) + 1
            except (AttributeError, TypeError) as e:
                # Count as UNKNOWN if license info is malformed
                counts["UNKNOWN"] = counts.get("UNKNOWN", 0) + 1
        
        # sort with UNKNOWN last
        items = sorted([(k, v) for k, v in counts.items() if k != "UNKNOWN"], key=lambda x: (-x[1], str(x[0]).lower()))
        if "UNKNOWN" in counts:
            items.append(("UNKNOWN", counts["UNKNOWN"]))
        return [{"license": k, "count": v} for k, v in items]
    except Exception as e:
        # Return empty list on catastrophic error
        return []