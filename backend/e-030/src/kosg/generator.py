from __future__ import annotations
import io
import os
import posixpath
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from jinja2 import Environment, StrictUndefined
import importlib.resources as ir

from .utils import compute_context


def _render_string(env: Environment, s: str, ctx: dict) -> str:
    return env.from_string(s).render(**ctx)


def _render_path(env: Environment, rel_path: Path, ctx: dict) -> str:
    parts = [ _render_string(env, p, ctx) for p in rel_path.as_posix().split("/") ]
    path = posixpath.join(*parts)
    if path.endswith(".j2"):
        path = path[:-3]
    return path


@dataclass
class GeneratedFile:
    path: str
    content: str


class ScaffoldGenerator:
    def __init__(self) -> None:
        self.env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
        self.templates_root = ir.files("kosg").joinpath("templates")

    def _iter_template_files(self) -> List[Path]:
        files: List[Path] = []
        base = Path(self.templates_root)
        for p in base.rglob("*"):
            if p.is_file():
                files.append(p)
        return files

    def render(self, payload: dict) -> Tuple[dict, List[GeneratedFile]]:
        ctx = compute_context(payload)
        gen_files: List[GeneratedFile] = []
        base = Path(self.templates_root)
        for abs_path in self._iter_template_files():
            rel = abs_path.relative_to(base)
            rel_rendered = _render_path(self.env, rel, ctx)
            raw = abs_path.read_text(encoding="utf-8")
            content_rendered = _render_string(self.env, raw, ctx)
            gen_files.append(GeneratedFile(path=rel_rendered, content=content_rendered))
        return ctx, gen_files

    def as_file_map(self, payload: dict) -> Dict[str, str]:
        _, files = self.render(payload)
        return {f.path: f.content for f in files}

    def as_zip_bytes(self, payload: dict) -> bytes:
        _, files = self.render(payload)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.writestr(f.path, f.content)
        buf.seek(0)
        return buf.getvalue()

