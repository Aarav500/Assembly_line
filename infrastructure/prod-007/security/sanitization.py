from __future__ import annotations
import re
import subprocess
from typing import List, Tuple
import bleach


_WHITESPACE_RE = re.compile(r"[\t \x0b\x0c\r]+")
_CONTROL_CHARS = "".join(map(chr, list(range(0, 9)) + list(range(11, 13)) + list(range(14, 32)) + [127]))
_CONTROL_CHARS_RE = re.compile("[%s]" % re.escape(_CONTROL_CHARS))


def strip_control_chars(s: str) -> str:
    if not s:
        return s
    return _CONTROL_CHARS_RE.sub("", s)


def normalize_whitespace(s: str, keep_newlines: bool = False) -> str:
    if not s:
        return s
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    if keep_newlines:
        # Collapse spaces and tabs, keep newlines
        parts = [
            _WHITESPACE_RE.sub(" ", line).strip()
            for line in s.split("\n")
        ]
        return "\n".join(parts).strip()
    return " ".join(s.split()).strip()


def sanitize_plain_text(s: str) -> str:
    s = strip_control_chars(s)
    s = normalize_whitespace(s, keep_newlines=False)
    return s


def sanitize_html(s: str) -> str:
    s = strip_control_chars(s)
    allowed_tags = [
        "b", "i", "em", "strong", "a", "p", "ul", "ol", "li", "br", "code", "pre", "span"
    ]
    allowed_attrs = {
        "a": ["href", "title", "rel"],
        "span": ["style"],
    }
    allowed_protocols = ["http", "https", "mailto"]
    cleaned = bleach.clean(
        s,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=allowed_protocols,
        strip=True,
    )
    # Also linkify safe URLs
    cleaned = bleach.linkify(cleaned, parse_email=True, callbacks=[bleach.linkifier.nofollow])
    return cleaned


def sanitize_for_like_query(term: str, escape_char: str = "\\") -> Tuple[str, str]:
    # Escape LIKE wildcards and the escape char itself
    term = sanitize_plain_text(term)
    term = term.replace(escape_char, escape_char + escape_char)
    term = term.replace("%", escape_char + "%")
    term = term.replace("_", escape_char + "_")
    # Wrap in wildcards for contains search
    pattern = f"%{term}%"
    return pattern, escape_char


def safe_run_command(args: List[str], timeout: int = 5) -> str:
    # Defend against command injection by:
    # - No shell
    # - Explicit list args
    # - Reject empty args and suspicious ones
    if not args or any(arg is None for arg in args):
        raise ValueError("invalid command")
    # Disallow user-controlled args that look like options for safety
    for a in args[1:]:  # allow program name (args[0])
        if a.startswith("-"):
            raise ValueError("disallowed argument")
        if len(a) > 253:
            raise ValueError("argument too long")
    proc = subprocess.run(
        args,
        shell=False,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    # Normalize output to avoid control characters
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    out = strip_control_chars(out)
    return out.strip()

