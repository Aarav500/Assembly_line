from typing import List, Dict


def evaluate_output(output: str, criteria: List[str]) -> Dict:
    if not criteria:
        return {
            'score': 1.0,
            'matched': [],
            'missing': [],
            'details': 'No criteria provided; default score = 1.0'
        }
    out_lower = output.lower()
    matched = []
    missing = []
    for c in criteria:
        if c.strip() == '':
            continue
        if c.lower() in out_lower:
            matched.append(c)
        else:
            missing.append(c)
    total = len(matched) + len(missing)
    score = (len(matched) / total) if total > 0 else 0.0
    return {
        'score': round(score, 4),
        'matched': matched,
        'missing': missing,
        'details': f"Matched {len(matched)} of {total} criteria"
    }

