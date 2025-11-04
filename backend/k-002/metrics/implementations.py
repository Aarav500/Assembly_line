import math
import re
from typing import Dict, Optional

AVAILABLE_METRICS = {
    "length_fit": "How well the output length matches the target length (words or range).",
    "keyword_coverage": "Fraction of provided keywords present in the output (case-insensitive).",
    "readability": "Flesch Reading Ease normalized to [0,1].",
    "diversity": "Unique-to-total word ratio (0..1).",
    "speed": "Prefers faster strategies relative to per-strategy timeout.",
}

DEFAULT_WEIGHTS = {
    "length_fit": 0.25,
    "keyword_coverage": 0.30,
    "readability": 0.20,
    "diversity": 0.15,
    "speed": 0.10,
}

_word_re = re.compile(r"[A-Za-z0-9']+")
_sent_re = re.compile(r"[.!?]+")


def tokenize_words(text: str):
    return _word_re.findall(text.lower())


def count_sentences(text: str) -> int:
    # Rough sentence split; ensure at least 1
    s = _sent_re.split(text)
    cnt = len([x for x in s if x.strip()])
    return max(1, cnt)


def count_syllables(word: str) -> int:
    # Very rough heuristic syllable counter
    word = word.lower()
    if len(word) <= 3:
        return 1
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def flesch_reading_ease(text: str) -> float:
    words = tokenize_words(text)
    n_words = max(1, len(words))
    n_sent = count_sentences(text)
    n_syll = sum(count_syllables(w) for w in words)
    # Flesch Reading Ease
    fre = 206.835 - 1.015 * (n_words / n_sent) - 84.6 * (n_syll / n_words)
    return fre


def normalize_01(x: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.0
    v = (x - lo) / (hi - lo)
    return max(0.0, min(1.0, v))


def metric_length_fit(output: str, target_length) -> Optional[float]:
    if target_length is None:
        return None
    words = tokenize_words(output)
    n = len(words)
    # target_length can be int or range-like
    if isinstance(target_length, int):
        if target_length <= 0:
            return None
        # Triangular decay: perfect when equal, declines linearly with relative error
        rel_err = abs(n - target_length) / max(1, target_length)
        return max(0.0, 1.0 - rel_err)
    # list/tuple [min,max] or dict {min: , max: }
    tmin = None
    tmax = None
    if isinstance(target_length, (list, tuple)) and len(target_length) == 2:
        tmin, tmax = target_length
    elif isinstance(target_length, dict):
        tmin = target_length.get("min")
        tmax = target_length.get("max")
    if tmin is None and tmax is None:
        return None
    if tmin is None:
        tmin = 0
    if tmax is None:
        tmax = max(tmin, n)
    if tmin <= n <= tmax:
        return 1.0
    # Outside range: decay with distance to nearest bound relative to bound size
    if n < tmin:
        gap = tmin - n
        scale = max(1, tmin)
        return max(0.0, 1.0 - gap / scale)
    else:
        gap = n - tmax
        scale = max(1, tmax)
        return max(0.0, 1.0 - gap / scale)


def metric_keyword_coverage(output: str, keywords) -> Optional[float]:
    if not keywords:
        return None
    words = set(tokenize_words(output))
    kws = [str(k).lower() for k in keywords if str(k).strip()]
    if not kws:
        return None
    hits = sum(1 for k in kws if k in words)
    return hits / len(kws)


def metric_readability(output: str) -> float:
    fre = flesch_reading_ease(output)
    # Map FRE approximately from [-50, 120] to [0,1]
    return normalize_01(fre, -50.0, 120.0)


def metric_diversity(output: str) -> float:
    words = tokenize_words(output)
    n = len(words)
    if n == 0:
        return 0.0
    uniq = len(set(words))
    return max(0.0, min(1.0, uniq / n))


def metric_speed(elapsed_sec: float, strategy_timeout: Optional[float]) -> Optional[float]:
    if not strategy_timeout or strategy_timeout <= 0:
        return None
    ratio = elapsed_sec / strategy_timeout
    return max(0.0, min(1.0, 1.0 - ratio))


def compute_all_metrics(output: str, prompt: str, elapsed_sec: float, config: Dict) -> Dict[str, Optional[float]]:
    keywords = config.get("keywords")
    target_length = config.get("target_length")
    strategy_timeout = config.get("strategy_timeout")
    return {
        "length_fit": metric_length_fit(output, target_length),
        "keyword_coverage": metric_keyword_coverage(output, keywords),
        "readability": metric_readability(output),
        "diversity": metric_diversity(output),
        "speed": metric_speed(elapsed_sec, strategy_timeout),
    }


def compute_score(metrics: Dict[str, Optional[float]], weights: Dict[str, float]) -> float:
    total_weight = 0.0
    total = 0.0
    for k, w in (weights or {}).items():
        if w is None or w <= 0:
            continue
        v = metrics.get(k)
        if v is None:
            continue
        v_clamped = max(0.0, min(1.0, float(v)))
        total += w * v_clamped
        total_weight += w
    if total_weight <= 0:
        return 0.0
    return total / total_weight

