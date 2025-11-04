from typing import List, Dict


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Dict]:
    """
    Split text into word-based chunks with overlap.

    Args:
        text: Input text.
        chunk_size: Number of words per chunk.
        overlap: Number of words to overlap between consecutive chunks.

    Returns:
        List of dicts with keys: start_word, end_word, text
    """
    if not text:
        return []
    words = text.split()
    n = len(words)
    if n == 0:
        return []

    chunk_size = max(1, int(chunk_size))
    overlap = max(0, int(overlap))
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 5)  # ensure progress

    chunks = []
    start = 0
    idx = 0
    while start < n:
        end = min(n, start + chunk_size)
        chunk_words = words[start:end]
        chunks.append({
            "start_word": start,
            "end_word": end - 1,
            "text": " ".join(chunk_words),
        })
        if end >= n:
            break
        start = end - overlap
        idx += 1
    return chunks

