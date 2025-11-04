from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


def compute_reweighing_weights(df: pd.DataFrame, protected_attrs: List[str], target_col: str) -> pd.Series:
    """
    Compute Kamiran & Calders reweighing-style weights for combinations of protected groups and class labels.
    For simplicity, we factorize combined protected attributes.
    """
    base = df.copy()
    # Create a combined protected group key
    key = base[protected_attrs].astype(str).agg('|'.join, axis=1)
    base['__group_key'] = key

    # P(Y=y), P(A=a), P(A=a, Y=y)
    n = len(base)
    weights = pd.Series(1.0, index=base.index)

    py = base[target_col].value_counts(normalize=True).to_dict()
    pa = base['__group_key'].value_counts(normalize=True).to_dict()
    pay = base.groupby(['__group_key', target_col]).size() / n
    pay = pay.to_dict()

    for idx, row in base[['__group_key', target_col]].itertuples(index=True):
        a = row[0] if isinstance(row, tuple) else base.loc[idx, '__group_key']
        y = row[1] if isinstance(row, tuple) else base.loc[idx, target_col]
        # expected independent prob: P(A=a) * P(Y=y)
        expected = pa.get(a, 0.0) * py.get(y, 0.0)
        observed = pay.get((a, y), 0.0)
        w = (expected / observed) if observed > 0 else 1.0
        if not np.isfinite(w):
            w = 1.0
        weights.at[idx] = float(w)
    return weights


def train_baseline_model_with_optional_reweighing(
    df: pd.DataFrame,
    target_col: str,
    protected_attrs: List[str],
    positive_label: Any = 1,
    use_reweighing: bool = False,
) -> Dict[str, Any]:
    # Exclude target and protected attrs from features
    X = df.drop(columns=[target_col] + protected_attrs, errors='ignore')
    # Try to keep only numeric via get_dummies
    X = pd.get_dummies(X, drop_first=True)
    X = X.fillna(0)
    y = (df[target_col] == positive_label).astype(int).values

    # Split for calibration but return predictions on full set (simple)
    # We'll fit on full data with optional sample_weight
    pipe = Pipeline([
        ('scaler', StandardScaler(with_mean=False)),
        ('clf', LogisticRegression(max_iter=200, n_jobs=None))
    ])

    sample_weight = None
    reweighing_applied = False
    if use_reweighing:
        try:
            sw = compute_reweighing_weights(df, protected_attrs, target_col)
            sample_weight = sw.values
            reweighing_applied = True
        except Exception:
            sample_weight = None
            reweighing_applied = False

    pipe.fit(X, y, **({'clf__sample_weight': sample_weight} if sample_weight is not None else {}))
    # Probability of positive class
    y_score = pipe.predict_proba(X)[:, 1]
    y_pred = (y_score >= 0.5).astype(int)

    return {
        'model_type': 'LogisticRegression',
        'features_used': list(X.columns),
        'proba_col': '__baseline_proba',
        'pred_col': '__baseline_pred',
        'y_score': y_score.tolist(),
        'y_pred': y_pred.tolist(),
        'reweighing_applied': reweighing_applied,
    }


def suggest_mitigations(audit_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    summary = audit_result.get('summary', {})
    by_attr = summary.get('by_protected_attribute', {})
    overall = summary.get('overall', {})

    for attr, metrics in by_attr.items():
        flags = summary.get('flags', {}).get(attr, {})
        groups = metrics.get('groups', {})
        privileged = metrics.get('privileged_group', None)

        if flags.get('disparate_impact_violation') or flags.get('demographic_parity_violation'):
            suggestions.append({
                'attribute': attr,
                'issue': 'Demographic parity / disparate impact',
                'threshold': 'DI < 0.8 or DP diff > 0.1',
                'actions': [
                    'Pre-processing: Apply reweighing to decorrelate protected attributes from labels',
                    'Pre-processing: Oversample under-represented protected groups',
                    'Post-processing: Adjust decision thresholds per group to align positive rates',
                ]
            })
        if flags.get('equal_opportunity_violation'):
            suggestions.append({
                'attribute': attr,
                'issue': 'Equal opportunity (TPR parity) violation',
                'threshold': 'TPR diff > 0.1',
                'actions': [
                    'Post-processing: Calibrate group-specific thresholds to equalize TPR',
                    'In-processing: Add fairness constraints targeting TPR parity',
                    'Data: Collect more positive-labeled examples for low-TPR groups',
                ]
            })
        if flags.get('equalized_odds_violation'):
            suggestions.append({
                'attribute': attr,
                'issue': 'Equalized odds (TPR and FPR parity) violation',
                'threshold': 'EO diff > 0.1',
                'actions': [
                    'Post-processing: Use cost-sensitive thresholds tuned per group to reduce both TPR and FPR gaps',
                    'In-processing: Train with fairness-regularized objective for EO',
                ]
            })
        if flags.get('predictive_parity_violation'):
            suggestions.append({
                'attribute': attr,
                'issue': 'Predictive parity (PPV parity) violation',
                'threshold': 'PPV diff > 0.1',
                'actions': [
                    'Calibration: Apply Platt or isotonic calibration per group',
                    'Thresholding: Adjust thresholds per group to align PPV',
                ]
            })
        small_groups = flags.get('small_group_warnings', [])
        if small_groups:
            suggestions.append({
                'attribute': attr,
                'issue': 'Small sample size in groups',
                'groups': small_groups,
                'actions': [
                    'Data: Increase data collection for small groups',
                    'Evaluation: Use stratified CV and report uncertainty',
                ]
            })

        # Additional heuristic suggestions based on low group accuracy vs overall
        overall_acc = overall.get('accuracy', None)
        if overall_acc is not None and groups:
            for g, gm in groups.items():
                acc = gm.get('accuracy', None)
                if acc is not None and overall_acc - acc >= 0.1:
                    suggestions.append({
                        'attribute': attr,
                        'group': g,
                        'issue': 'Group-specific underperformance',
                        'actions': [
                            'Model: Include interaction features capturing group-specific patterns (without using protected attributes in decision rule)',
                            'Data: Targeted error analysis and label quality checks for this group',
                        ]
                    })

    return suggestions

