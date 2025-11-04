import os
from typing import Dict, List
from .base import OptimizationPass
from optimization.utils.html_utils import find_html_files, load_html, write_html


class LazyLoadMediaPass(OptimizationPass):
    id = "lazy_load_media"
    name = "Lazy-load media"
    description = "Adds loading=\"lazy\" to <img> and <iframe> without it."

    def analyze(self, path: str) -> Dict:
        files = find_html_files(path)
        missing = []
        for f in files:
            try:
                _, soup = load_html(f)
            except Exception:
                continue
            imgs = [img for img in soup.find_all("img") if not img.get("loading")]
            iframes = [fr for fr in soup.find_all("iframe") if not fr.get("loading")]
            if imgs or iframes:
                missing.append({
                    "file": f,
                    "images_missing": len(imgs),
                    "iframes_missing": len(iframes),
                })
        return {"files_with_missing_lazy": missing}

    def apply(self, path: str, dry_run: bool = True) -> Dict:
        report: Dict = {"modified_files": [], "total_added": {"images": 0, "iframes": 0}, "errors": []}
        for f in find_html_files(path):
            try:
                original, soup = load_html(f)
            except Exception as e:
                report["errors"].append({"file": f, "error": str(e)})
                continue

            to_change_imgs = [img for img in soup.find_all("img") if not img.get("loading")]
            to_change_iframes = [fr for fr in soup.find_all("iframe") if not fr.get("loading")]

            if not to_change_imgs and not to_change_iframes:
                continue

            for tag in to_change_imgs:
                tag["loading"] = "lazy"
            for tag in to_change_iframes:
                tag["loading"] = "lazy"

            if not dry_run:
                # Backup
                try:
                    os.replace(f, f + ".bak")
                    with open(f, "w", encoding="utf-8") as out:
                        out.write(str(soup))
                except Exception as e:
                    # If replace fails due to non-atomic behavior, fallback to write_html
                    try:
                        with open(f + ".bak", "w", encoding="utf-8") as bfh:
                            bfh.write(original)
                        with open(f, "w", encoding="utf-8") as out:
                            out.write(str(soup))
                    except Exception as e2:
                        report["errors"].append({"file": f, "error": f"{e} / {e2}"})
                        continue
            report["modified_files"].append({
                "file": f,
                "images_added": len(to_change_imgs),
                "iframes_added": len(to_change_iframes),
                "dry_run": dry_run,
            })
            report["total_added"]["images"] += len(to_change_imgs)
            report["total_added"]["iframes"] += len(to_change_iframes)

        return report

