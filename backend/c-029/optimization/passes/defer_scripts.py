import os
from typing import Dict
from .base import OptimizationPass
from optimization.utils.html_utils import find_html_files, load_html


class DeferScriptsPass(OptimizationPass):
    id = "defer_scripts"
    name = "Defer blocking scripts"
    description = "Adds defer to <script src> tags without async/defer/type=module."

    def analyze(self, path: str) -> Dict:
        files_need_change = []
        for f in find_html_files(path):
            try:
                _, soup = load_html(f)
            except Exception:
                continue
            candidates = []
            for s in soup.find_all("script"):
                if s.get("src") and not s.get("async") and not s.get("defer"):
                    t = (s.get("type") or "").strip().lower()
                    if t != "module":
                        candidates.append(1)
            if candidates:
                files_need_change.append({"file": f, "blocking_scripts": len(candidates)})
        return {"files_with_blocking_scripts": files_need_change}

    def apply(self, path: str, dry_run: bool = True) -> Dict:
        report: Dict = {"modified_files": [], "total_deferred": 0, "errors": []}
        for f in find_html_files(path):
            try:
                original, soup = load_html(f)
            except Exception as e:
                report["errors"].append({"file": f, "error": str(e)})
                continue
            changed = 0
            for s in soup.find_all("script"):
                if s.get("src") and not s.get("async") and not s.get("defer"):
                    t = (s.get("type") or "").strip().lower()
                    if t != "module":
                        s["defer"] = "defer"
                        s["data-defer-added"] = "1"
                        changed += 1
            if changed:
                if not dry_run:
                    try:
                        os.replace(f, f + ".bak")
                        with open(f, "w", encoding="utf-8") as out:
                            out.write(str(soup))
                    except Exception as e:
                        try:
                            with open(f + ".bak", "w", encoding="utf-8") as bfh:
                                bfh.write(original)
                            with open(f, "w", encoding="utf-8") as out:
                                out.write(str(soup))
                        except Exception as e2:
                            report["errors"].append({"file": f, "error": f"{e} / {e2}"})
                            continue
                report["modified_files"].append({"file": f, "deferred": changed, "dry_run": dry_run})
                report["total_deferred"] += changed
        return report

