from typing import Dict, Any, List


class RiskEngine:
    def __init__(self):
        # Weights should sum to 1.0
        self.weights = {
            "vuln": 0.35,
            "exposure": 0.20,
            "controls": 0.20,
            "anomalies": 0.15,
            "incidents": 0.10,
        }

    def remediation_catalog(self) -> Dict[str, Any]:
        return {
            "actions": [
                {"id": "patch_top_vuln", "label": "Patch highest severity vulnerability", "applies_to": ["asset"]},
                {"id": "restrict_exposure", "label": "Restrict external exposure", "applies_to": ["asset", "user"]},
                {"id": "enable_mfa", "label": "Enable MFA", "applies_to": ["user", "asset"]},
                {"id": "install_edr", "label": "Install EDR", "applies_to": ["asset"]},
                {"id": "enable_logging", "label": "Enable central logging", "applies_to": ["asset", "user"]},
                {"id": "isolate_host", "label": "Isolate host from network", "applies_to": ["asset"]},
                {"id": "review_anomalies", "label": "Review and resolve anomalies", "applies_to": ["asset", "user"]},
                {"id": "close_incidents", "label": "Close resolved incidents", "applies_to": ["asset", "user"]},
                {"id": "rotate_keys", "label": "Rotate credentials/keys", "applies_to": ["asset"]},
            ]
        }

    def compute_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        criticality = float(entity.get("criticality", 0.5))
        exposure = float(entity.get("exposure", 0.0))
        vulns: List[Dict[str, Any]] = entity.get("vulnerabilities", [])
        controls: Dict[str, Any] = entity.get("controls", {})
        anomalies = float(entity.get("anomalies", 0.0))
        incidents = int(entity.get("incidents", 0))

        # Vulnerability contribution: normalized average severity of open vulns
        open_v = [v for v in vulns if v.get("status") == "open"]
        if open_v:
            avg_sev = sum([float(v.get("severity", 0)) for v in open_v]) / len(open_v)
            vuln_norm = min(avg_sev / 10.0, 1.0)
        else:
            vuln_norm = 0.0

        # Controls gap: fraction of missing controls from a baseline
        expected = [
            ("mfa_enabled", 1.0),
            ("logging", 1.0),
        ]
        if entity.get("type") == "asset":
            expected.append(("edr_installed", 1.0))
        total_expected = len(expected)
        missing = 0
        for key, _ in expected:
            if not controls.get(key, False):
                missing += 1
        controls_gap = missing / total_expected if total_expected else 0.0

        anomalies_norm = min(anomalies / 10.0, 1.0)
        incidents_norm = min(incidents / 5.0, 1.0)

        w = self.weights
        raw = (
            vuln_norm * w["vuln"] +
            exposure * w["exposure"] +
            controls_gap * w["controls"] +
            anomalies_norm * w["anomalies"] +
            incidents_norm * w["incidents"]
        )
        # Amplify by criticality multiplier between 0.5 and 1.0
        multiplier = 0.5 + 0.5 * criticality
        score = max(0.0, min(100.0, round(raw * multiplier * 100.0, 1)))

        breakdown = {
            "vuln": round(vuln_norm * w["vuln"] * 100.0, 1),
            "exposure": round(exposure * w["exposure"] * 100.0, 1),
            "controls": round(controls_gap * w["controls"] * 100.0, 1),
            "anomalies": round(anomalies_norm * w["anomalies"] * 100.0, 1),
            "incidents": round(incidents_norm * w["incidents"] * 100.0, 1),
        }

        # Suggestions based on highest contributors
        suggestions = []
        # Sort by contributor value
        contrib_order = sorted(breakdown.items(), key=lambda kv: kv[1], reverse=True)
        top_keys = [k for k, _ in contrib_order[:3]]
        for key in top_keys:
            if key == "vuln" and open_v:
                suggestions.append({"action": "patch_top_vuln", "reason": "High vulnerability risk"})
            if key == "exposure":
                suggestions.append({"action": "restrict_exposure", "reason": "High exposure"})
                if entity.get("type") == "asset":
                    suggestions.append({"action": "isolate_host", "reason": "Reduce attack surface quickly"})
            if key == "controls":
                if not controls.get("mfa_enabled", False):
                    suggestions.append({"action": "enable_mfa", "reason": "Missing MFA"})
                if entity.get("type") == "asset" and not controls.get("edr_installed", False):
                    suggestions.append({"action": "install_edr", "reason": "Missing EDR"})
                if not controls.get("logging", False):
                    suggestions.append({"action": "enable_logging", "reason": "Missing logging"})
            if key == "anomalies":
                suggestions.append({"action": "review_anomalies", "reason": "Recent anomalous behavior"})
            if key == "incidents" and incidents > 0:
                suggestions.append({"action": "close_incidents", "reason": "Open incidents"})
        # Deduplicate suggestions keeping order
        seen = set()
        dedup_suggestions = []
        for s in suggestions:
            if s["action"] not in seen:
                dedup_suggestions.append(s)
                seen.add(s["action"])

        return {
            "score": score,
            "breakdown": breakdown,
            "suggestions": dedup_suggestions
        }

    def recompute_all(self, store):
        ents = store.get_all()
        for e in ents:
            r = self.compute_entity(e)
            e["risk"] = r
            store.set_entity(e)

    def recompute_entity(self, store, entity_id):
        e = store.get(entity_id)
        if not e:
            return
        r = self.compute_entity(e)
        e["risk"] = r
        store.set_entity(e)

