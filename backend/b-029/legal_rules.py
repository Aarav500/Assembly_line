from datetime import datetime
from typing import Dict, Any, List, Tuple

SEVERITY_WEIGHTS = {
    'low': 1,
    'medium': 3,
    'high': 6,
    'critical': 10,
}

GDPR_JURIS_FLAGS = {"EU", "EEA", "UK", "CH"}
CCPA_JURIS_FLAGS = {"US-CA", "CA", "California"}

class RuleEngine:
    def __init__(self):
        pass

    def run(self, inv: Dict[str, Any]) -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = []

        org = inv.get('org', {})
        jurisdictions = set([j.strip() for j in (org.get('jurisdictions') or [])])
        targets_gdpr = bool(jurisdictions & GDPR_JURIS_FLAGS)
        targets_ccpa = bool(jurisdictions & CCPA_JURIS_FLAGS)

        # GDPR checks
        if targets_gdpr:
            findings += self._gdpr_checks(inv)
        # CCPA/CPRA checks
        if targets_ccpa:
            findings += self._ccpa_checks(inv)

        # General best-practice checks
        findings += self._general_security_checks(inv)
        findings += self._retention_checks(inv)

        score, level = self._score(findings)

        checklist = self._build_checklist(findings)

        return {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'org': {
                'name': org.get('name'),
                'jurisdictions': list(jurisdictions),
            },
            'summary': {
                'total_findings': len(findings),
                'risk_score': score,
                'risk_level': level,
                'by_severity': self._by_severity(findings),
            },
            'findings': findings,
            'checklist': checklist,
        }

    def _gdpr_checks(self, inv: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings = []
        org = inv.get('org', {})
        dpo_assigned = org.get('dpo_assigned')
        ropa = inv.get('ropa', {})

        datasets = inv.get('datasets', [])
        for ds in datasets:
            ds_name = ds.get('name') or 'unnamed-dataset'
            category = (ds.get('category') or '').lower()
            lawful_basis = ds.get('lawful_basis')
            consent_mgmt = ds.get('consent_management') or {}
            lia_conducted = ds.get('lia_conducted')

            # Lawful basis required for personal data
            if category in ('personal', 'sensitive'):
                if not lawful_basis:
                    findings.append(self._finding(
                        f'gdpr-lawful-basis-missing::{ds_name}',
                        f'Lawful basis missing for dataset "{ds_name}"',
                        'GDPR requires a lawful basis for processing personal data.',
                        'high',
                        'GDPR',
                        {'dataset': ds_name},
                        [
                            'Identify purpose(s) and select a lawful basis (Art. 6).',
                            'Document the decision and update privacy notice.'
                        ]
                    ))
                elif lawful_basis == 'consent':
                    if not consent_mgmt.get('consent_recorded'):
                        findings.append(self._finding(
                            f'gdpr-consent-records-missing::{ds_name}',
                            f'Consent records not maintained for "{ds_name}"',
                            'When relying on consent, records must be kept and withdrawal enabled.',
                            'high',
                            'GDPR',
                            {'dataset': ds_name},
                            [
                                'Implement verifiable consent capture and logs.',
                                'Enable easy withdrawal and honor it across systems.'
                            ]
                        ))
                elif lawful_basis == 'legitimate_interests':
                    if not lia_conducted:
                        findings.append(self._finding(
                            f'gdpr-lia-missing::{ds_name}',
                            f'LIA not conducted for "{ds_name}"',
                            'Legitimate interests require a balancing test (LIA).',
                            'medium',
                            'GDPR',
                            {'dataset': ds_name},
                            [
                                'Conduct and document a Legitimate Interests Assessment.',
                                'Record mitigations and review periodically.'
                            ]
                        ))

            # Data minimization & purpose limitation
            for f in ds.get('fields', []) or []:
                if (f.get('pii') or f.get('sensitive')) and not f.get('purpose'):
                    findings.append(self._finding(
                        f'gdpr-purpose-missing::{ds_name}::{f.get("name")}',
                        f'Purpose missing for field "{f.get("name")}" in "{ds_name}"',
                        'Personal data must be collected for specified, explicit purposes.',
                        'medium',
                        'GDPR',
                        {'dataset': ds_name, 'field': f.get('name')},
                        [
                            'Define and document purposes for this field.',
                            'Remove the field if it is not necessary.'
                        ]
                    ))

            # High-risk processing suggests DPIA
            high_risk_flags = [
                category == 'sensitive',
                bool(ds.get('children_data')),
                bool(ds.get('systematic_monitoring')),
                bool(ds.get('large_scale')),
            ]
            if any(high_risk_flags) and not ds.get('dpia_conducted'):
                findings.append(self._finding(
                    f'gdpr-dpia-needed::{ds_name}',
                    f'Consider DPIA for "{ds_name}"',
                    'High-risk processing likely requires a DPIA (Art. 35).',
                    'high',
                    'GDPR',
                    {'dataset': ds_name},
                    [
                        'Perform a Data Protection Impact Assessment.',
                        'Engage DPO and record outcomes and mitigations.'
                    ]
                ))

            # International transfers
            for tr in ds.get('transfers', []) or []:
                safeguard = tr.get('safeguard')
                rc = (tr.get('recipient_country') or '').upper()
                if rc and rc not in {'EEA', 'EU', 'UK', 'CH'} and safeguard in (None, '', 'None', 'none'):
                    findings.append(self._finding(
                        f'gdpr-transfer-safeguards-missing::{ds_name}::{rc}',
                        f'Safeguards missing for transfer to {rc} in "{ds_name}"',
                        'Cross-border transfers require appropriate safeguards (e.g., SCCs).',
                        'critical',
                        'GDPR',
                        {'dataset': ds_name, 'recipient_country': rc},
                        [
                            'Put in place SCCs/BCRs or confirm adequacy decision.',
                            'Assess transfer impact and document supplementary measures.'
                        ]
                    ))

            # Children data age
            if ds.get('children_data') and not ds.get('age_known'):
                findings.append(self._finding(
                    f'gdpr-children-age-unknown::{ds_name}',
                    f'Children data age not verified for "{ds_name}"',
                    'Processing children data requires age verification and parental consent (where applicable).',
                    'high',
                    'GDPR',
                    {'dataset': ds_name},
                    [
                        'Implement age gating/verification.',
                        'Obtain parental consent where required.'
                    ]
                ))

        # ROPA
        if not (ropa.get('maintained') or ropa.get('last_updated_days')):
            findings.append(self._finding(
                'gdpr-ropa-missing',
                'Record of Processing Activities (ROPA) not maintained',
                'Controllers must maintain ROPA (Art. 30) where applicable.',
                'medium',
                'GDPR',
                {},
                [
                    'Establish and maintain an up-to-date ROPA.',
                    'Include purposes, categories, recipients, retention and security.'
                ]
            ))

        # DPO
        if org.get('requires_dpo') and not dpo_assigned:
            findings.append(self._finding(
                'gdpr-dpo-missing',
                'DPO not assigned where required',
                'Certain processing requires a Data Protection Officer (Art. 37).',
                'medium',
                'GDPR',
                {},
                [
                    'Appoint a qualified DPO and publish contact details.'
                ]
            ))

        # Breach notification preparedness
        breach = inv.get('breach', {})
        if breach:
            if breach.get('detection_time_hours') and breach.get('detection_time_hours') > 72:
                findings.append(self._finding(
                    'gdpr-breach-detection-slow',
                    'Breach detection exceeds 72 hours',
                    'Controllers must notify authorities within 72 hours of becoming aware of a breach.',
                    'medium',
                    'GDPR',
                    {},
                    [
                        'Improve detection and escalation to ensure timely notification.'
                    ]
                ))
            if not breach.get('notification_procedure'):
                findings.append(self._finding(
                    'gdpr-breach-procedure-missing',
                    'No breach notification procedure documented',
                    'A clear incident response and notification procedure is expected.',
                    'medium',
                    'GDPR',
                    {},
                    [
                        'Document incident response and notification workflows.',
                        'Run tabletop exercises and train staff.'
                    ]
                ))

        # DSAR SLA
        dsar = inv.get('dsar', {})
        if dsar:
            if not dsar.get('contact_channel'):
                findings.append(self._finding(
                    'gdpr-dsar-contact-missing',
                    'DSAR contact channel missing',
                    'Provide clear means for data subjects to exercise rights.',
                    'medium',
                    'GDPR',
                    {},
                    [
                        'Add a DSAR contact/form and publish in privacy notice.'
                    ]
                ))
            if (dsar.get('response_time_days') or 0) > 30:
                findings.append(self._finding(
                    'gdpr-dsar-sla-exceeded',
                    'DSAR response time exceeds 30 days',
                    'GDPR requires responses without undue delay, within one month.',
                    'medium',
                    'GDPR',
                    {},
                    [
                        'Improve DSAR processing to meet 30-day SLA.'
                    ]
                ))

        # Cookie consent
        for ck in inv.get('cookies', []) or []:
            if ck.get('purpose') in ('analytics', 'advertising', 'functional') and not ck.get('prior_consent'):
                findings.append(self._finding(
                    f'gdpr-cookie-consent-missing::{ck.get("name")}',
                    f'Consent missing for cookie "{ck.get("name")}"',
                    'Non-essential cookies require prior consent.',
                    'high',
                    'GDPR',
                    {'cookie': ck.get('name')},
                    [
                        'Implement a compliant consent banner with granular choices.',
                        'Do not set non-essential cookies before consent.'
                    ]
                ))

        return findings

    def _ccpa_checks(self, inv: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings = []

        dsar = inv.get('dsar', {})
        if (dsar.get('response_time_days') or 0) > 45:
            findings.append(self._finding(
                'ccpa-dsar-sla-exceeded',
                'Consumer request response time exceeds 45 days',
                'CCPA/CPRA requires responses within 45 days, extendable with notice.',
                'medium',
                'CCPA/CPRA',
                {},
                [
                    'Improve fulfillment workflow to meet 45-day SLA.'
                ]
            ))

        datasets = inv.get('datasets', [])
        for ds in datasets:
            ds_name = ds.get('name') or 'unnamed-dataset'
            category = (ds.get('category') or '').lower()

            # Do Not Sell or Share
            if ds.get('sell_share_to_third_parties') or ds.get('targeted_advertising'):
                if not dsar.get('opt_out_mechanism'):
                    findings.append(self._finding(
                        f'ccpa-do-not-sell-share-missing::{ds_name}',
                        'Do Not Sell or Share mechanism missing',
                        'If selling or sharing personal information, provide a clear opt-out link.',
                        'high',
                        'CCPA/CPRA',
                        {'dataset': ds_name},
                        [
                            'Add a "Do Not Sell or Share My Personal Information" link.',
                            'Honor GPC signals and document opt-outs.'
                        ]
                    ))

            # Sensitive Personal Information limitations
            if category == 'sensitive':
                if not dsar.get('limit_use_sensitive_info_mechanism'):
                    findings.append(self._finding(
                        f'ccpa-sensitive-limit-missing::{ds_name}',
                        'Sensitive PI use/limit mechanism missing',
                        'Provide a right to limit use and disclosure of sensitive PI.',
                        'high',
                        'CCPA/CPRA',
                        {'dataset': ds_name},
                        [
                            'Offer a mechanism to limit use/disclosure of sensitive PI.'
                        ]
                    ))

            # Children under 16 require opt-in
            if ds.get('children_data') and not ds.get('age_known'):
                findings.append(self._finding(
                    f'ccpa-children-age-unknown::{ds_name}',
                    'Children data age not verified',
                    'Selling data of consumers under 16 requires opt-in; under 13 requires parental consent.',
                    'high',
                    'CCPA/CPRA',
                    {'dataset': ds_name},
                    [
                        'Implement age gating and obtain appropriate opt-in consent.'
                    ]
                ))

            # Notice at collection and data categories
            if category in ('personal', 'sensitive') and not ds.get('notice_at_collection'):
                findings.append(self._finding(
                    f'ccpa-notice-at-collection-missing::{ds_name}',
                    'Notice at collection missing',
                    'Provide notice at or before the point of collection with categories and purposes.',
                    'medium',
                    'CCPA/CPRA',
                    {'dataset': ds_name},
                    [
                        'Publish a Notice at Collection specifying categories, purposes, retention, and sharing.'
                    ]
                ))

            # Contracts with service providers
            if ds.get('processor') and not ds.get('dpa_in_place'):
                findings.append(self._finding(
                    f'ccpa-service-provider-contract-missing::{ds_name}',
                    'Service provider contract missing',
                    'Written contract must prohibit retaining/using data for other purposes.',
                    'medium',
                    'CCPA/CPRA',
                    {'dataset': ds_name},
                    [
                        'Execute service provider/contractor agreements with required terms.'
                    ]
                ))

        return findings

    def _general_security_checks(self, inv: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings = []
        for ds in inv.get('datasets', []) or []:
            ds_name = ds.get('name') or 'unnamed-dataset'
            category = (ds.get('category') or '').lower()
            enc = ds.get('encryption_at_rest')
            pseudo = ds.get('pseudonymization')
            access = ds.get('access_controls') or []

            if category == 'sensitive' and not enc:
                findings.append(self._finding(
                    f'sec-encryption-missing::{ds_name}',
                    f'Encryption at rest missing for "{ds_name}"',
                    'Sensitive data should be encrypted at rest.',
                    'high',
                    'Both',
                    {'dataset': ds_name},
                    [
                        'Enable encryption at rest (disk/DB-level).'
                    ]
                ))

            if category in ('personal', 'sensitive') and 'least_privilege' not in [a.lower() for a in access]:
                findings.append(self._finding(
                    f'sec-access-controls-weak::{ds_name}',
                    f'Least privilege not enforced for "{ds_name}"',
                    'Access controls should enforce least privilege.',
                    'medium',
                    'Both',
                    {'dataset': ds_name},
                    [
                        'Implement role-based access and periodic access reviews.'
                    ]
                ))

            if category in ('personal', 'sensitive') and not pseudo:
                findings.append(self._finding(
                    f'sec-pseudonymization-missing::{ds_name}',
                    f'Pseudonymization not implemented for "{ds_name}"',
                    'Pseudonymization or tokenization reduces risk.',
                    'low',
                    'Both',
                    {'dataset': ds_name},
                    [
                        'Introduce pseudonymization/tokenization where feasible.'
                    ]
                ))
        return findings

    def _retention_checks(self, inv: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings = []
        policy = inv.get('retention_policy') or {}
        default_max_days = policy.get('default_max_days')
        deletion_window = policy.get('deletion_window_days') or 30

        for ds in inv.get('datasets', []) or []:
            ds_name = ds.get('name') or 'unnamed-dataset'
            category = (ds.get('category') or '').lower()
            rp = ds.get('retention_period_days')
            lb = ds.get('lawful_basis')

            if (rp is None) or (isinstance(rp, int) and rp <= 0):
                findings.append(self._finding(
                    f'retention-missing::{ds_name}',
                    f'Retention period missing for "{ds_name}"',
                    'Define retention aligned with purposes and legal obligations.',
                    'medium',
                    'Both',
                    {'dataset': ds_name},
                    [
                        'Define a concrete retention period and review schedule.',
                        'Document deletion/anonymization procedures.'
                    ]
                ))
            elif default_max_days and rp > default_max_days and lb != 'legal_obligation':
                findings.append(self._finding(
                    f'retention-exceeds-policy::{ds_name}',
                    f'Retention exceeds policy for "{ds_name}"',
                    f'Dataset is retained {rp} days, exceeding default maximum of {default_max_days}.',
                    'medium',
                    'Both',
                    {'dataset': ds_name},
                    [
                        f'Reduce retention to <= {default_max_days} days or justify exception.',
                        f'Schedule deletion within {deletion_window} days for out-of-policy records.'
                    ]
                ))

        return findings

    def _by_severity(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        out = {k: 0 for k in SEVERITY_WEIGHTS.keys()}
        for f in findings:
            sev = f.get('severity')
            if sev in out:
                out[sev] += 1
        return out

    def _score(self, findings: List[Dict[str, Any]]) -> Tuple[int, str]:
        score = 0
        for f in findings:
            score += SEVERITY_WEIGHTS.get(f.get('severity'), 0)
        # Simple bucketing
        if score >= 50:
            level = 'critical'
        elif score >= 25:
            level = 'high'
        elif score >= 10:
            level = 'medium'
        else:
            level = 'low'
        return score, level

    def _build_checklist(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        items = []
        for f in findings:
            items.append({
                'id': f['id'],
                'title': f['title'],
                'severity': f['severity'],
                'regulation': f['regulation'],
                'remediation': f['remediation']
            })
        # De-duplicate by title
        unique = {}
        for i in items:
            key = (i['title'], i['severity'])
            if key not in unique:
                unique[key] = i
        return list(unique.values())

    def _finding(self, fid: str, title: str, description: str, severity: str, regulation: str, affected: Dict[str, Any], remediation: List[str]):
        return {
            'id': fid,
            'title': title,
            'description': description,
            'severity': severity,
            'regulation': regulation,
            'affected': affected,
            'remediation': remediation,
        }

