from typing import Dict, Any, List
from datetime import datetime, timezone
from collections import Counter
from drift.stats import histogram_proportions, psi, categorical_proportions, chi2_pvalue, is_number


class DriftDetector:
    def __init__(self, baseline_manager, config):
        self.baseline_manager = baseline_manager
        self.config = config

    def _severity_from_psi(self, value: float) -> str:
        if value >= self.config.PSI_THRESHOLD:
            return 'high'
        if value >= self.config.PSI_THRESHOLD_WARN:
            return 'warn'
        return 'none'

    def compute_report(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        baseline = self.baseline_manager.get() or {}
        features_section: Dict[str, Any] = {}
        num_drifted = 0
        drifted_names = []

        # Prepare current values per feature
        current_numeric: Dict[str, List[float]] = {}
        current_categorical: Dict[str, List[str]] = {}
        preds: List[float] = []

        for s in samples:
            feats = s.get('features', {})
            for k, v in feats.items():
                if k in baseline.get('numeric', {}):
                    if is_number(v):
                        current_numeric.setdefault(k, []).append(float(v))
                elif k in baseline.get('categorical', {}):
                    current_categorical.setdefault(k, []).append(str(v))
                else:
                    # Ignore features not in baseline
                    pass
            p = s.get('prediction', None)
            if p is not None and is_number(p):
                preds.append(float(p))

        # Numeric features
        for feat, bl in baseline.get('numeric', {}).items():
            edges = bl.get('bin_edges', [])
            b_props = bl.get('proportions', [])
            c_vals = current_numeric.get(feat, [])
            c_props = histogram_proportions(c_vals, edges)
            value_psi = psi(b_props, c_props)
            sev = self._severity_from_psi(value_psi)
            if sev in ('high', 'warn'):
                num_drifted += 1
                drifted_names.append(feat)
            features_section[feat] = {
                'type': 'numeric',
                'psi': value_psi,
                'severity': sev,
                'counts': {'baseline': bl.get('count', 0), 'current': len(c_vals)},
                'details': {
                    'bin_edges': edges,
                    'baseline_proportions': b_props,
                    'current_proportions': c_props
                }
            }

        # Categorical features
        for feat, bl in baseline.get('categorical', {}).items():
            cats = bl.get('categories', [])
            b_props = bl.get('proportions', [])
            c_vals = current_categorical.get(feat, [])
            # Build observed counts for chi2
            counts = Counter()
            for v in c_vals:
                key = v if v in cats else '__OTHER__'
                counts[key] += 1
            observed_counts = [counts.get(c, 0) for c in cats]
            c_props = [0.0 for _ in cats]
            total = sum(observed_counts)
            if total > 0:
                c_props = [cnt / total for cnt in observed_counts]
            value_psi = psi(b_props, c_props)
            pval = 1.0
            try:
                pval = chi2_pvalue(observed_counts, b_props)
            except Exception:
                pval = 1.0
            sev = self._severity_from_psi(value_psi)
            if (sev in ('high', 'warn')) or (pval < self.config.CAT_P_THRESHOLD):
                num_drifted += 1
                drifted_names.append(feat)
            features_section[feat] = {
                'type': 'categorical',
                'psi': value_psi,
                'chi2_pvalue': pval,
                'severity': sev if pval >= self.config.CAT_P_THRESHOLD else 'high',
                'counts': {'baseline': bl.get('count', 0), 'current': len(c_vals)},
                'details': {
                    'categories': cats,
                    'baseline_proportions': b_props,
                    'current_proportions': c_props
                }
            }

        # Output drift
        output_section = {}
        output_drifted = False
        output_severity = 'none'
        if baseline.get('output') and preds:
            edges = baseline['output'].get('bin_edges', [])
            b_props = baseline['output'].get('proportions', [])
            c_props = histogram_proportions(preds, edges)
            out_psI = psi(b_props, c_props)
            out_sev = self._severity_from_psi(out_psI)
            pr_current = sum(1 for p in preds if p >= 0.5) / len(preds)
            pr_base = baseline['output'].get('positive_rate', None)
            output_section = {
                'psi': out_psI,
                'severity': out_sev,
                'baseline_positive_rate': pr_base,
                'current_positive_rate': pr_current,
                'details': {
                    'bin_edges': edges,
                    'baseline_proportions': b_props,
                    'current_proportions': c_props
                }
            }
            output_drifted = out_sev in ('high', 'warn') or (abs((pr_current - (pr_base or pr_current))) > 0.1 if pr_base is not None else False)
            output_severity = out_sev

        # Summary
        overall_severity = 'none'
        if any(f.get('severity') == 'high' for f in features_section.values()) or (output_severity == 'high'):
            overall_severity = 'high'
        elif any(f.get('severity') == 'warn' for f in features_section.values()) or (output_severity == 'warn'):
            overall_severity = 'warn'

        report = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'window_size': len(samples),
            'summary': {
                'drift_detected': overall_severity in ('high', 'warn'),
                'severity': overall_severity,
                'num_features_evaluated': len(features_section),
                'num_features_drifted': num_drifted,
                'features_drifted': drifted_names,
                'output_drifted': output_drifted
            },
            'features': features_section,
            'output': output_section
        }
        return report

