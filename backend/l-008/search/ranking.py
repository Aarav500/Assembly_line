import numpy as np
from typing import Optional, Tuple


def _min_max_scale(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    mn = np.min(x)
    mx = np.max(x)
    if mx - mn < 1e-12:
        return np.zeros_like(x)
    return (x - mn) / (mx - mn)


def combine_scores(
    lexical: Optional[np.ndarray],
    semantic: Optional[np.ndarray],
    w_lex: float = 0.5,
    w_sem: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = 0
    if lexical is not None:
        n = lexical.shape[0]
    elif semantic is not None:
        n = semantic.shape[0]
    else:
        return np.array([]), np.array([]), np.array([])

    lex_s = _min_max_scale(lexical) if lexical is not None else np.zeros(n)
    sem_s = _min_max_scale(semantic) if semantic is not None else np.zeros(n)

    # Normalize weights
    total_w = max(w_lex + w_sem, 1e-9)
    wl = w_lex / total_w
    ws = w_sem / total_w

    combo = wl * lex_s + ws * sem_s
    return combo, lex_s, sem_s

