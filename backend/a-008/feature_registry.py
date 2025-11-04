import importlib
import pkgutil
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple

BASE_DIR = Path(__file__).parent
FEATURES_PKG = "features"
FEATURES_DIR = BASE_DIR / FEATURES_PKG
TESTS_DIR = BASE_DIR / "tests_a-008"


def _call_health_check(mod) -> Tuple[bool, str]:
    hc = getattr(mod, "health_check", None)
    if hc is None or not callable(hc):
        return False, "No health_check() defined"
    try:
        result = hc()
        if isinstance(result, tuple) and len(result) >= 1:
            ok = bool(result[0])
            msg = str(result[1]) if len(result) > 1 else ("OK" if ok else "Failed")
            return ok, msg
        else:
            ok = bool(result)
            return ok, "OK" if ok else "Failed"
    except Exception as e:
        return False, f"Exception during health_check: {e}"


def _has_tests(feature_slug: str) -> bool:
    if not TESTS_DIR.exists():
        return False
    # Patterns: tests_a-008/test_<feature>.py OR tests_a-008/<feature>/**.py
    file_pattern = TESTS_DIR / f"test_{feature_slug}.py"
    if file_pattern.exists():
        return True
    subdir = TESTS_DIR / feature_slug
    if subdir.exists():
        for p in subdir.rglob("*.py"):
            if p.is_file():
                return True
    return False


def _get_meta(mod) -> Dict[str, Any]:
    meta = getattr(mod, "FEATURE_INFO", {}) or {}
    name = meta.get("name") or getattr(mod, "__name__", "")
    desc = meta.get("description") or ""
    owner = meta.get("owner") or ""
    return {"name": name, "description": desc, "owner": owner}


def detect_features() -> List[Dict[str, Any]]:
    features: List[Dict[str, Any]] = []
    if not FEATURES_DIR.exists():
        return features

    for module_info in pkgutil.iter_modules([str(FEATURES_DIR)]):
        if not module_info.ispkg:
            # We expect subpackages, skip plain modules if any
            continue
        slug = module_info.name
        mod_fqn = f"{FEATURES_PKG}.{slug}"
        try:
            mod = importlib.import_module(mod_fqn)
        except Exception as e:
            features.append({
                "slug": slug,
                "name": slug,
                "description": "",
                "owner": "",
                "status": "broken",
                "has_tests": _has_tests(slug),
                "details": f"Failed to import: {e}",
                "last_checked_at": datetime.utcnow().isoformat() + "Z",
            })
            continue

        ok, msg = _call_health_check(mod)
        tests = _has_tests(slug)

        if ok and tests:
            status = "functional"
        elif ok and not tests:
            status = "missing_tests"
        else:
            status = "broken"

        meta = _get_meta(mod)
        features.append({
            "slug": slug,
            "name": meta.get("name") or slug,
            "description": meta.get("description", ""),
            "owner": meta.get("owner", ""),
            "status": status,
            "has_tests": tests,
            "details": msg,
            "last_checked_at": datetime.utcnow().isoformat() + "Z",
        })

    # Sort by status severity then name
    order = {"broken": 0, "missing_tests": 1, "functional": 2}
    features.sort(key=lambda f: (order.get(f["status"], 99), f["name"].lower()))
    return features
