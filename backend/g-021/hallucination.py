import os
import re
from typing import List, Union

from utils import simple_tokenize

# Threshold for flagging hallucinations based on similarity score (0..1). Lower means stricter.
HALLUCINATION_THRESHOLD = float(os.getenv("HALLUCINATION_THRESHOLD", 0.5))


def _normalize_reference_input(references: Union[str, List[str]]) -> List[str]:
    if references is None:
        return []
    if isinstance(references, str):
        return [references]
    if isinstance(references, list):
        # ensure list of strings
        return [str(r) for r in references]
    # Fallback to string conversion
    return [str(references)]


def jaccard_similarity(a_tokens: List[str], b_tokens: List[str]) -> float:
    a_set = set(a_tokens)
    b_set = set(b_tokens)
    if not a_set and not b_set:
        return 1.0
    union = a_set | b_set
    if not union:
        return 0.0
    inter = a_set & b_set
    return len(inter) / len(union)


def compute_hallucination_score(output_text: str, references: Union[str, List[str]]) -> float:
    """
    Returns similarity score in [0,1], where 1 means output aligns fully with references
    and 0 means no overlap. This is a naive proxy for hallucination likelihood.
    """
    refs = _normalize_reference_input(references)
    out_tokens = simple_tokenize(output_text)
    ref_tokens_all: List[str] = []
    for r in refs:
        ref_tokens_all.extend(simple_tokenize(r))
    return jaccard_similarity(out_tokens, ref_tokens_all)


def is_hallucination(score: float) -> bool:
    return score < HALLUCINATION_THRESHOLD

