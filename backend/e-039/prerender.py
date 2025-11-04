import os
import json
from typing import List, Tuple, Dict, Any
from utils import path_to_output_file, sha256_bytes, atomic_write, load_json, dump_json, iso_now


class PreRenderResult:
    def __init__(self):
        self.written: List[str] = []
        self.changed: List[str] = []
        self.skipped: List[str] = []
        self.errors: List[Dict[str, Any]] = []
        self.manifest: Dict[str, str] = {}

    def to_dict(self):
        return {
            "written": self.written,
            "changed": self.changed,
            "skipped": self.skipped,
            "errors": self.errors,
            "manifest": self.manifest,
        }


def _manifest_path(build_root: str, site_slug: str) -> str:
    return os.path.join(build_root, site_slug, "manifest.json")


def load_manifest(build_root: str, site_slug: str) -> Dict[str, str]:
    return load_json(_manifest_path(build_root, site_slug), {})


def save_manifest(build_root: str, site_slug: str, manifest: Dict[str, str]):
    dump_json(_manifest_path(build_root, site_slug), manifest)


def render_paths(app, site_slug: str, paths: List[str], build_root: str) -> PreRenderResult:
    result = PreRenderResult()
    manifest = load_manifest(build_root, site_slug)

    build_dir = os.path.join(build_root, site_slug)
    os.makedirs(build_dir, exist_ok=True)

    # Use Flask test client to render internally
    with app.app_context():
        client = app.test_client()
        for p in paths:
            # Normalize
            if not p.startswith('/'):
                p = '/' + p
            try:
                resp = client.get(p)
                if resp.status_code != 200:
                    result.errors.append({"path": p, "status_code": resp.status_code})
                    continue
                data = resp.get_data()
                digest = sha256_bytes(data)
                prev_digest = manifest.get(p)
                outfile_rel = path_to_output_file(p)
                outfile_abs = os.path.join(build_dir, outfile_rel)
                if prev_digest == digest and os.path.exists(outfile_abs):
                    result.skipped.append(p)
                else:
                    atomic_write(outfile_abs, data)
                    result.written.append(p)
                    if prev_digest != digest:
                        result.changed.append(p)
                manifest[p] = digest
            except Exception as e:
                result.errors.append({"path": p, "error": str(e)})
                continue

    result.manifest = manifest
    save_manifest(build_root, site_slug, manifest)
    return result

