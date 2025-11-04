import io
import requests
from typing import Optional
from pdfminer.high_level import extract_text as pdf_extract_text


def _is_pdf_response(resp: requests.Response) -> bool:
    ctype = resp.headers.get("Content-Type", "").lower()
    if "application/pdf" in ctype:
        return True
    # Some servers mislabel PDFs; check first bytes for %PDF
    try:
        head = resp.content[:4]
        return head == b"%PDF"
    except Exception:
        return False


def load_text_from_url(url: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    if _is_pdf_response(r):
        return pdf_extract_text(io.BytesIO(r.content))
    # Otherwise, treat as text/HTML
    text = r.text
    # Quick and naive HTML tag stripping if HTML content
    if "<html" in text.lower():
        import re
        text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
    return text


def load_text_from_file(file_storage) -> str:
    filename = (file_storage.filename or "").lower()
    data = file_storage.read()
    if filename.endswith(".pdf") or (data[:4] == b"%PDF"):
        return pdf_extract_text(io.BytesIO(data))
    try:
        # Try decode as UTF-8 text
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""

