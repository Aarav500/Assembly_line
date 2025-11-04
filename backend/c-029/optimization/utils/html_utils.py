import os
from bs4 import BeautifulSoup
from typing import List, Tuple

HTML_EXTS = {".html", ".htm", ".j2", ".jinja2", ".tpl"}


def is_html_file(path: str) -> bool:
    _, ext = os.path.splitext(path.lower())
    return ext in HTML_EXTS


def find_html_files(root: str) -> List[str]:
    files = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            p = os.path.join(dirpath, f)
            if is_html_file(p):
                files.append(p)
    return files


def parse_html(content: str) -> BeautifulSoup:
    return BeautifulSoup(content, "html.parser")


def load_html(path: str) -> Tuple[str, BeautifulSoup]:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        txt = fh.read()
    return txt, parse_html(txt)


def write_html(path: str, soup: BeautifulSoup) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(str(soup))

