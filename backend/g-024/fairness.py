from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    brier_score_loss,
    confusion_matrix,
)


EPS = 1e-12


def _safe_div(a, b):
    b = b if b not in [0, 0.0] else EPS
    return a / b


def rate_positive(y):
    return float(np.mean(y)) if len(y) else 0.0


def group_values(series: pd.Series) -> List[Any]:
    vals = list(pd.Series(series).dropna().unique())
    return sorted(vals, key=lambda x: str(x))


def compute_group_classification_stats(y_true, y_pred):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    tpr = _safe_div(tp, tp + fn)  # recall
    fpr = _safe_div(fp, fp + tn)
    tnr = _safe_div(tn, tn + fp)
    fnr = _safe_div(fn, fn + tp)
    ppv = _safe_div(tp, tp + fp)  # precision
    npv = _safe_div(tn, tn + fn)
    return {
        'tp': int(tp), 'tn': int(tn), 'fp': int(fp), 'fn': int(fn),
        'tpr': tpr, 'fpr': fpr, 'tnr': tnr, 'fnr': fnr, 'ppv': ppv, 'npv': npv
    }


def compute_fairness_audit(
    df: pd.DataFrame,
    target_col: str,
    pred_col: str,
    proba_col: Optional[str],
    protected_attrs: List[str],
    privileged_values: Optional[Dict[str, List[Any]]] = None,
    positive_label: Any = 1,
) -> Dict[str, Any]:
    # Normalize target to {0,1}
    y_true_raw = df[target_col].values
    pos_mask = (df[target_col] == positive_label).astype(int)
    y_true = pos_mask.values if isinstance(pos_mask, pd.Series) else pos_mask
    y_pred = df[pred_col].astype(int).values

    if proba_col is not None and proba_col in df.columns:
        proba = df[proba_col].astype(float).values
    else:
        proba = None

    overall = {
        'n_samples': int(len(df)),
        'n_pos': int(np.sum(y_true)),
        'n_neg': int(len(df) - np.sum(y_true)),
        'positive_rate': float(np.mean(y_true)) if len(df) else 0.0,
        'accuracy': accuracy_score(y_true, y_pred) if len(df) else 0.0,
        'precision': precision_score(y_true, y_pred, zero_division=0) if len(df) else 0.0,
        'recall': recall_score(y_true, y_pred, zero_division=0) if len(df) else 0.0,
        'f1': f1_score(y_true, y_pred, zero_division=0) if len(df) else 0.0,
    }
    if proba is not None:
        try:
            overall['roc_auc'] = roc_auc_score(y_true, proba)
        except Exception:
            overall['roc_auc'] = None
        try:
            overall['brier'] = brier_score_loss(y_true, proba)
        except Exception:
            overall['brier'] = None

    per_attr: Dict[str, Any] = {}

    for attr in protected_attrs:
        series = df[attr]
        groups = group_values(series)
        group_metrics = {}
        pos_rates = {}
        tprs = {}
        fprs = {}
        ppvs = {}
        counts = {}

        for g in groups:
            mask = (series == g).values
            y_t = y_true[mask]
            y_p = y_pred[mask]
            counts[g] = int(mask.sum())
            if counts[g] == 0:
                group_metrics[g] = {
                    'count': 0,
                    'positive_rate': None,
                    'accuracy': None,
                    'precision': None,
                    'recall': None,
                    'f1': None,
                    'tpr': None,
                    'fpr': None,
                    'ppv': None,
                    'npv': None,
                }
                continue

            stats = compute_group_classification_stats(y_t, y_p)
            pr = float(np.mean(y_p))
            pos_rates[g] = pr
            tprs[g] = stats['tpr']
            fprs[g] = stats['fpr']
            ppvs[g] = stats['ppv']

            gm = {
                'count': counts[g],
                'positive_rate': pr,
                'accuracy': accuracy_score(y_t, y_p),
                'precision': precision_score(y_t, y_p, zero_division=0),
                'recall': recall_score(y_t, y_p, zero_division=0),
                'f1': f1_score(y_t, y_p, zero_division=0),
                'tpr': stats['tpr'],
                'fpr': stats['fpr'],
                'ppv': stats['ppv'],
                'npv': stats['npv'],
            }
            if proba is not None:
                try:
                    gm['roc_auc'] = roc_auc_score(y_t, proba[mask])
                except Exception:
                    gm['roc_auc'] = None
                try:
                    gm['brier'] = brier_score_loss(y_t, proba[mask])
                except Exception:
                    gm['brier'] = None
            group_metrics[g] = gm

        # Choose privileged group(s)
        priv_list = None
        if privileged_values and attr in privileged_values:
            priv_list = privileged_values[attr]
        # fallback: select group with highest positive rate as privileged (if available)
        privileged_group = None
        if priv_list:
            # pick first that exists
            for v in priv_list:
                if v in groups:
                    privileged_group = v
                    break
        if privileged_group is None and len(pos_rates) > 0:
            privileged_group = max(pos_rates, key=lambda k: pos_rates[k])

        # Disparities
        dpd = None  # demographic parity difference
        diratio = None  # disparate impact ratio
        eod = None  # equalized odds diff (max(|TPR diff|, |FPR diff|))
        eopp = None  # equal opportunity difference (TPR diff)
        pprd = None  # predictive parity difference (PPV diff)

        if len(pos_rates) >= 2:
            rates = list(pos_rates.values())
            dpd = float(max(rates) - min(rates))
            if privileged_group is not None:
                priv_rate = pos_rates.get(privileged_group, None)
                if priv_rate is not None and priv_rate > 0:
                    # Use worst ratio vs privileged group
                    ratios = [ _safe_div(pos_rates[g], priv_rate) for g in pos_rates ]
                    diratio = float(min(ratios))
                else:
                    diratio = None
        if len(tprs) >= 2:
            eopp = float(max(tprs.values()) - min(tprs.values()))
        if len(tprs) >= 2 and len(fprs) >= 2:
            eod = float(max(abs(tprs[g] - tprs.get(privileged_group, tprs[g])) for g in tprs) if privileged_group in tprs else max(tprs.values()) - min(tprs.values()))
            eod = max(eod, float(max(abs(fprs[g] - fprs.get(privileged_group, fprs[g])) for g in fprs) if privileged_group in fprs else max(fprs.values()) - min(fprs.values())))
        if len(ppvs) >= 2:
            pprd = float(max(ppvs.values()) - min(ppvs.values()))

        per_attr[attr] = {
            'groups': group_metrics,
            'privileged_group': privileged_group,
            'demographic_parity_difference': dpd,
            'disparate_impact_ratio': diratio,
            'equal_opportunity_difference': eopp,
            'equalized_odds_difference': eod,
            'predictive_parity_difference': pprd,
        }

    summary = {
        'overall': overall,
        'by_protected_attribute': per_attr,
    }

    # Flags for common thresholds
    flags = {}
    for attr, vals in per_attr.items():
        flags[attr] = {}
        dpd = vals.get('demographic_parity_difference')
        diratio = vals.get('disparate_impact_ratio')
        eopp = vals.get('equal_opportunity_difference')
        eod = vals.get('equalized_odds_difference')
        pprd = vals.get('predictive_parity_difference')
        groups = vals.get('groups', {})
        counts = {g: groups[g]['count'] for g in groups}
        small_groups = [g for g, c in counts.items() if c < 50]
        flags[attr]['small_group_warnings'] = small_groups
        flags[attr]['demographic_parity_violation'] = bool(dpd is not None and dpd > 0.1)
        flags[attr]['disparate_impact_violation'] = bool(diratio is not None and diratio < 0.8)
        flags[attr]['equal_opportunity_violation'] = bool(eopp is not None and eopp > 0.1)
        flags[attr]['equalized_odds_violation'] = bool(eod is not None and eod > 0.1)
        flags[attr]['predictive_parity_violation'] = bool(pprd is not None and pprd > 0.1)

    summary['flags'] = flags
    return {
        'summary': summary,
    }

