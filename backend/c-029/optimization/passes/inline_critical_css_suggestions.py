import os
from typing import Dict, List
from config import SIZE_THRESHOLDS


def analyze_css_for_critical(root: str) -> Dict:
    big_css: List[Dict] = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext != ".css":
                continue
            p = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if size >= SIZE_THRESHOLDS["css_large_bytes"]:
                big_css.append({"file": p, "size_bytes": size})
    suggestions: List[Dict] = []
    for item in big_css:
        suggestions.append({
            "file": item["file"],
            "suggestion": "Extract and inline critical CSS for above-the-fold content. Load the rest with media=\"print\"+onload or preload.",
        })
    return {"css_big_files": big_css, "critical_css_suggestions": suggestions}

