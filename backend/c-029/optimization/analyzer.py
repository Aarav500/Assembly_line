import os
from typing import Dict, List
from bs4 import BeautifulSoup

from config import SIZE_THRESHOLDS, ANALYZE_EXTENSIONS
from optimization.utils.html_utils import find_html_files, load_html
from optimization.passes.split_js_suggestions import analyze_js_for_splitting
from optimization.passes.inline_critical_css_suggestions import analyze_css_for_critical


class ProjectAnalyzer:
    def _collect_files(self, root: str) -> Dict:
        counts = {"html": 0, "js": 0, "css": 0, "images": 0, "other": 0}
        sizes = {"html": 0, "js": 0, "css": 0, "images": 0, "other": 0}
        largest: List[Dict] = []
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                _, ext = os.path.splitext(fn.lower())
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                if ext in ANALYZE_EXTENSIONS["html"]:
                    k = "html"
                elif ext in ANALYZE_EXTENSIONS["js"]:
                    k = "js"
                elif ext in ANALYZE_EXTENSIONS["css"]:
                    k = "css"
                elif ext in ANALYZE_EXTENSIONS["images"]:
                    k = "images"
                else:
                    k = "other"
                counts[k] += 1
                sizes[k] += size
                largest.append({"file": p, "size_bytes": size})
        largest_sorted = sorted(largest, key=lambda x: x["size_bytes"], reverse=True)[:20]
        return {"counts": counts, "sizes": sizes, "largest_files": largest_sorted}

    def _analyze_html(self, root: str) -> Dict:
        files = find_html_files(root)
        imgs_missing = 0
        iframes_missing = 0
        scripts_blocking = 0
        details: List[Dict] = []
        has_preload = 0
        stylesheet_links = 0

        for f in files:
            try:
                _, soup = load_html(f)
            except Exception:
                continue
            file_img_missing = 0
            file_iframe_missing = 0
            file_scripts_blocking = 0

            for link in soup.find_all("link"):
                rel = (" ".join(link.get("rel", []))).lower() if link.get("rel") else ""
                as_attr = (link.get("as") or "").lower()
                if "preload" in rel:
                    has_preload += 1
                if "stylesheet" in rel:
                    stylesheet_links += 1
            for img in soup.find_all("img"):
                if not img.get("loading"):
                    imgs_missing += 1
                    file_img_missing += 1
            for fr in soup.find_all("iframe"):
                if not fr.get("loading"):
                    iframes_missing += 1
                    file_iframe_missing += 1
            for s in soup.find_all("script"):
                if s.get("src") and not s.get("async") and not s.get("defer"):
                    t = (s.get("type") or "").strip().lower()
                    if t != "module":
                        scripts_blocking += 1
                        file_scripts_blocking += 1

            if file_img_missing or file_iframe_missing or file_scripts_blocking:
                details.append({
                    "file": f,
                    "images_missing_lazy": file_img_missing,
                    "iframes_missing_lazy": file_iframe_missing,
                    "blocking_scripts": file_scripts_blocking,
                })

        suggestions: List[str] = []
        if imgs_missing or iframes_missing:
            suggestions.append("Add loading=\"lazy\" to non-critical images and iframes.")
        if scripts_blocking:
            suggestions.append("Add defer/async to external scripts to avoid render-blocking.")
        if stylesheet_links > 0 and has_preload == 0:
            suggestions.append("Consider preloading critical CSS or using critical CSS inlining for faster FCP.")

        return {
            "html_files": len(files),
            "images_missing_lazy": imgs_missing,
            "iframes_missing_lazy": iframes_missing,
            "blocking_scripts": scripts_blocking,
            "preload_links": has_preload,
            "stylesheet_links": stylesheet_links,
            "files_with_issues": details,
            "suggestions": suggestions,
        }

    def _analyze_images(self, root: str) -> Dict:
        large_images: List[Dict] = []
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg"}:
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                if size >= SIZE_THRESHOLDS["img_large_bytes"]:
                    large_images.append({"file": p, "size_bytes": size})
        return {"large_images": large_images}

    def analyze(self, root: str) -> Dict:
        overview = self._collect_files(root)
        html = self._analyze_html(root)
        js = analyze_js_for_splitting(root)
        css = analyze_css_for_critical(root)
        images = self._analyze_images(root)

        recommendations: List[Dict] = []
        if html.get("images_missing_lazy", 0) or html.get("iframes_missing_lazy", 0):
            recommendations.append({
                "pass_id": "lazy_load_media",
                "title": "Add lazy-loading to media",
                "rationale": "Reduce initial bytes and improve LCP by deferring offscreen media.",
            })
        if html.get("blocking_scripts", 0):
            recommendations.append({
                "pass_id": "defer_scripts",
                "title": "Defer render-blocking scripts",
                "rationale": "Prevent scripts from blocking HTML parsing.",
            })
        if js.get("route_split_suggestions"):
            recommendations.append({
                "pass_id": None,
                "title": "Split large JS bundles",
                "rationale": "Use dynamic import() to split bundles per route or feature.",
                "details": js.get("route_split_suggestions"),
            })
        if js.get("vendor_split_suggestions"):
            recommendations.append({
                "pass_id": None,
                "title": "Extract vendor libraries",
                "rationale": "Split common libraries into vendor chunk for better caching.",
                "details": js.get("vendor_split_suggestions"),
            })
        if css.get("critical_css_suggestions"):
            recommendations.append({
                "pass_id": None,
                "title": "Inline critical CSS",
                "rationale": "Inline above-the-fold CSS and load the rest async.",
                "details": css.get("critical_css_suggestions"),
            })

        return {
            "root": os.path.abspath(root),
            "overview": overview,
            "html_findings": html,
            "js_findings": js,
            "css_findings": css,
            "image_findings": images,
            "recommendations": recommendations,
        }

