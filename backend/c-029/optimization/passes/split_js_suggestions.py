import os
from typing import Dict, List
from config import SIZE_THRESHOLDS

COMMON_LIBS = ["react", "react-dom", "vue", "angular", "rxjs", "lodash", "moment", "jquery"]


def analyze_js_for_splitting(root: str) -> Dict:
    big_files: List[Dict] = []
    vendor_suggestions: List[Dict] = []
    route_suggestions: List[Dict] = []
    dynamic_import_files: List[str] = []

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext not in {".js", ".mjs", ".cjs"}:
                continue
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            text = ""
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            except Exception:
                pass

            has_dynamic_import = "import(" in text
            imports_common = [lib for lib in COMMON_LIBS if (f"'{lib}'" in text or f'"{lib}"' in text)]

            if has_dynamic_import:
                dynamic_import_files.append(p)

            if size >= SIZE_THRESHOLDS["js_large_bytes"]:
                big_files.append({"file": p, "size_bytes": size, "dynamic_import": has_dynamic_import})
                if not has_dynamic_import:
                    route_suggestions.append({
                        "file": p,
                        "suggestion": "Consider splitting this large bundle per route using dynamic import() and router-based chunks.",
                    })

            if imports_common:
                base = os.path.basename(p).lower()
                if "vendor" not in base and "vendors" not in base:
                    vendor_suggestions.append({
                        "file": p,
                        "libs": imports_common,
                        "suggestion": "Extract common libraries into a separate vendor chunk to improve caching.",
                    })

    return {
        "js_big_files": big_files,
        "dynamic_import_files": dynamic_import_files,
        "vendor_split_suggestions": vendor_suggestions,
        "route_split_suggestions": route_suggestions,
    }

