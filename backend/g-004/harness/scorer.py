import math
import re
from typing import Dict, Any, List
from .utils import normalize_text, try_float


class Scorer:
    @staticmethod
    def exact(expected: Any, pred: Any, cfg: Dict[str, Any]) -> float:
        norm = cfg.get("normalize", [])
        if isinstance(expected, list):
            exp_norm = [normalize_text(e, norm) for e in expected]
        else:
            exp_norm = [normalize_text(expected, norm)]
        pred_norm = normalize_text(pred, norm)
        return 1.0 if pred_norm in exp_norm else 0.0

    @staticmethod
    def substring(expected: Any, pred: Any, cfg: Dict[str, Any]) -> float:
        norm = cfg.get("normalize", [])
        if isinstance(expected, list):
            expected_list = expected
        else:
            expected_list = [expected]
        pred_norm = normalize_text(pred, norm)
        for e in expected_list:
            e_norm = normalize_text(e, norm)
            if e_norm in pred_norm:
                return 1.0
        return 0.0

    @staticmethod
    def regex(expected: Any, pred: Any, cfg: Dict[str, Any]) -> float:
        flags = 0
        if cfg.get("ignore_case"):
            flags |= re.IGNORECASE
        patt = expected if isinstance(expected, str) else str(expected)
        return 1.0 if re.search(patt, str(pred), flags) else 0.0

    @staticmethod
    def numeric_close(expected: Any, pred: Any, cfg: Dict[str, Any]) -> float:
        tol = float(cfg.get("tolerance", 1e-6))
        e = try_float(expected)
        p = try_float(pred)
        if e is None or p is None:
            return 0.0
        return 1.0 if abs(e - p) <= tol else 0.0

    @staticmethod
    def bleu1(expected: Any, pred: Any, cfg: Dict[str, Any]) -> float:
        # Simple BLEU-1 precision with smoothing
        def tokens(s: str):
            return [t for t in re.findall(r"\w+", s.lower())]
        if isinstance(expected, list):
            refs = [tokens(str(e)) for e in expected]
        else:
            refs = [tokens(str(expected))]
        cand = tokens(str(pred))
        if not cand:
            return 0.0
        # compute unigram precision against the best reference
        def prec(ref):
            ref_counts = {}
            for w in ref:
                ref_counts[w] = ref_counts.get(w, 0) + 1
            match = 0
            used = {}
            for w in cand:
                used[w] = used.get(w, 0) + 1
                if w in ref_counts and used[w] <= ref_counts[w]:
                    match += 1
            return (match + 1) / (len(cand) + 1)  # add-1 smoothing
        p = max(prec(r) for r in refs)
        bp = 1.0  # no brevity penalty for simplicity
        return bp * p


def get_scorer(name: str):
    name = (name or "").lower()
    if name == "exact":
        return Scorer.exact
    if name == "substring":
        return Scorer.substring
    if name == "regex":
        return Scorer.regex
    if name in ("numeric", "numeric_close"):
        return Scorer.numeric_close
    if name in ("bleu", "bleu1"):
        return Scorer.bleu1
    raise ValueError(f"Unknown scorer: {name}")

