from datetime import datetime, timezone
from typing import Any, Dict, List

from .config import settings
from .scanner import get_scanner, ScanError
from . import storage


def recheck_all_images() -> Dict[str, Any]:
    images = settings.load_images()
    scanner = get_scanner()
    now = datetime.now(timezone.utc)

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for image in images:
        try:
            report, counts = scanner.scan_image(image)
            scan_id = storage.save_scan(
                image=image,
                scanned_at=now,
                scanner=scanner.name,
                report=report,
                counts=counts,
            )
            results.append(
                {
                    "image": image,
                    "scan_id": scan_id,
                    "scanner": scanner.name,
                    "counts": counts,
                }
            )
        except ScanError as e:
            errors.append({"image": image, "error": str(e)})
        except Exception as e:  # noqa: BLE001
            errors.append({"image": image, "error": f"Unexpected error: {e}"})

    pruned = 0
    if settings.retain_runs > 0:
        try:
            pruned = storage.prune_old_scans_per_image(settings.retain_runs)
        except Exception:
            pruned = 0

    return {
        "started_at": now.isoformat(),
        "scanner": scanner.name,
        "processed": len(images),
        "succeeded": len(results),
        "failed": len(errors),
        "pruned": pruned,
        "results": results,
        "errors": errors,
    }

