import re
import requests
from bs4 import BeautifulSoup

USER_AGENT = 'kb-diff-bot/1.0 (+https://example.com)'


def normalize_text(text: str) -> str:
    # Normalize whitespace: strip trailing spaces, collapse multiple blank lines
    lines = [re.sub(r'\s+$', '', line) for line in text.splitlines()]
    # Remove leading/trailing blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    # Collapse more than 2 consecutive blanks into single blank
    normalized = []
    blank_count = 0
    for line in lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= 1:
                normalized.append("")
        else:
            blank_count = 0
            normalized.append(line)
    return "\n".join(normalized).strip()


def fetch_content(url: str, selector: str | None = None, timeout: int = 20) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html, text/plain;q=0.9, */*;q=0.8"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()

    ctype = resp.headers.get('Content-Type', '')
    content = resp.content

    text = None
    if 'text/html' in ctype or (ctype.startswith('text/') and 'html' in ctype):
        soup = BeautifulSoup(content, 'html.parser')
        if selector:
            sel = soup.select_one(selector)
            if sel:
                text = sel.get_text(separator='\n')
            else:
                # Fallback to full text if selector not found
                text = soup.get_text(separator='\n')
        else:
            text = soup.get_text(separator='\n')
    elif ctype.startswith('text/') or ctype == 'application/json':
        try:
            text = content.decode('utf-8', errors='replace')
        except Exception:
            text = content.decode('latin-1', errors='replace')
    else:
        # Fallback: try decode as utf-8
        try:
            text = content.decode('utf-8', errors='replace')
        except Exception:
            text = content.decode('latin-1', errors='replace')

    return normalize_text(text or '')

