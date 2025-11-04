import fnmatch
import re
from datetime import datetime, timezone
from dateutil import parser as dateparser


def glob_match(pattern: str, text: str) -> bool:
    if not pattern:
        return False
    return fnmatch.fnmatch(text, pattern)


def compile_regex(pattern: str):
    if not pattern:
        return None
    try:
        return re.compile(pattern)
    except re.error:
        return None


def regex_match(regex, text: str) -> bool:
    if not regex:
        return False
    return bool(regex.search(text))


def parse_created(value):
    # value could be ISO8601 string
    if not value:
        return None
    try:
        dt = dateparser.parse(value)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def now_utc():
    return datetime.now(timezone.utc)

