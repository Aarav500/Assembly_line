import math
import re
from typing import List, Tuple, Dict, Optional


_SENT_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD_REGEX = re.compile(r"[A-Za-z0-9']+")

# A compact English stopword set to avoid heavy dependencies
_STOPWORDS = {
    'a','about','above','after','again','against','all','am','an','and','any','are','aren\'t','as','at','be','because','been','before','being','below','between','both','but','by','can\'t','cannot','could','couldn\'t','did','didn\'t','do','does','doesn\'t','doing','don\'t','down','during','each','few','for','from','further','had','hadn\'t','has','hasn\'t','have','haven\'t','having','he','he\'d','he\'ll','he\'s','her','here','here\'s','hers','herself','him','himself','his','how','how\'s','i','i\'d','i\'ll','i\'m','i\'ve','if','in','into','is','isn\'t','it','it\'s','its','itself','let\'s','me','more','most','mustn\'t','my','myself','no','nor','not','of','off','on','once','only','or','other','ought','our','ours','ourselves','out','over','own','same','shan\'t','she','she\'d','she\'ll','she\'s','should','shouldn\'t','so','some','such','than','that','that\'s','the','their','theirs','them','themselves','then','there','there\'s','these','they','they\'d','they\'ll','they\'re','they\'ve','this','those','through','to','too','under','until','up','very','was','wasn\'t','we','we\'d','we\'ll','we\'re','we\'ve','were','weren\'t','what','what\'s','when','when\'s','where','where\'s','which','while','who','who\'s','whom','why','why\'s','with','won\'t','would','wouldn\'t','you','you\'d','you\'ll','you\'re','you\'ve','your','yours','yourself','yourselves'
}


def _split_sentences(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    # Split by punctuation delimiters and newlines
    parts = _SENT_SPLIT_REGEX.split(text)
    # Clean and filter
    sents = []
    for p in parts:
        s = p.strip()
        if s:
            sents.append(s)
    return sents


def _tokenize_words(text: str) -> List[str]:
    return [m.group(0).lower() for m in _WORD_REGEX.finditer(text)]


def _sentence_scores(sentences: List[str]) -> Tuple[Dict[int, float], List[List[str]]]:
    tokenized = [_tokenize_words(s) for s in sentences]
    freq: Dict[str, int] = {}
    for toks in tokenized:
        for w in toks:
            if w in _STOPWORDS:
                continue
            freq[w] = freq.get(w, 0) + 1
    if not freq:
        return {i: 0.0 for i in range(len(sentences))}, tokenized

    # Normalize frequencies
    max_f = max(freq.values())
    for w in list(freq.keys()):
        freq[w] = freq[w] / max(1.0, float(max_f))

    scores: Dict[int, float] = {}
    for i, toks in enumerate(tokenized):
        if not toks:
            scores[i] = 0.0
            continue
        s = 0.0
        valid_count = 0
        for w in toks:
            if w in _STOPWORDS:
                continue
            s += freq.get(w, 0.0)
            valid_count += 1
        # Normalize by sentence length to avoid very long sentences dominating
        if valid_count > 0:
            scores[i] = s / math.sqrt(valid_count)
        else:
            scores[i] = 0.0
    return scores, tokenized


class FrequencySummarizer:
    """
    Lightweight extractive summarizer based on term frequency scoring.
    No external ML dependencies. Works reasonably for general English prose.
    """

    def summarize(
        self,
        text: str,
        ratio: float = 0.2,
        max_sentences: Optional[int] = None,
        min_sentences: int = 1,
    ) -> str:
        text = (text or "").strip()
        if not text:
            return ""

        sentences = _split_sentences(text)
        if not sentences:
            return text

        n = len(sentences)
        if n == 1:
            return sentences[0]

        # Determine number of sentences to select
        k_by_ratio = max(min_sentences, int(round(n * max(0.05, min(0.95, ratio)))))
        if max_sentences is not None:
            k = min(k_by_ratio, int(max_sentences))
        else:
            k = k_by_ratio
        k = max(min_sentences, min(k, n))

        scores, _ = _sentence_scores(sentences)
        # Pick top-k sentence indices by score
        idx_sorted = sorted(range(n), key=lambda i: scores.get(i, 0.0), reverse=True)
        selected = sorted(idx_sorted[:k])  # keep original order

        summary = " ".join([sentences[i] for i in selected]).strip()
        return summary if summary else sentences[0]

