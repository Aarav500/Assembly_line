import json
from datetime import datetime
from app import create_app
from app.db import db
from app.models import Rule, Asset, Scan, Finding

app = create_app()

with app.app_context():
    # Clear existing data
    db.drop_all()
    db.create_all()

    # Rules
    rules = [
        Rule(key='CIS-1.1', title='Ensure MFA is enabled for root account', severity='High', service='IAM', remediation_guidance='Enable MFA for root user.'),
        Rule(key='CIS-2.2', title='Ensure CloudTrail is enabled in all regions', severity='Critical', service='CloudTrail', remediation_guidance='Enable CloudTrail in all regions.'),
        Rule(key='CIS-3.3', title='Ensure S3 buckets are not publicly accessible', severity='High', service='S3', remediation_guidance='Block public access to S3 buckets.'),
        Rule(key='CIS-4.1', title='Ensure EBS volumes are encrypted', severity='Medium', service='EBS', remediation_guidance='Enable EBS encryption by default.')
    ]
    for r in rules:
        db.session.add(r)
    db.session.flush()

    # Assets
    assets = [
        Asset(id='asset-ec2-1', name='i-0abc123', type='ec2', provider='aws', region='us-east-1', tags={'env':'prod'}),
        Asset(id='asset-s3-1', name='s3-prod-logs', type='s3', provider='aws', region='us-east-1', tags={'env':'prod'}),
        Asset(id='asset-iam-1', name='root-account', type='iam', provider='aws', region='global', tags={'owner':'secops'})
    ]
    for a in assets:
        db.session.add(a)
    db.session.flush()

    # Scan
    scan = Scan(provider='aws', status='Completed', started_at=datetime.utcnow(), finished_at=datetime.utcnow(), asset_count=len(assets))
    db.session.add(scan)
    db.session.flush()

    # Findings
    fnds = [
        Finding(scan_id=scan.id, asset_id='asset-iam-1', rule_id=rules[0].id, status='Open', state='Fail', severity=rules[0].severity, details={'mfa_enabled': False}),
        Finding(scan_id=scan.id, asset_id='asset-s3-1', rule_id=rules[2].id, status='Open', state='Fail', severity=rules[2].severity, details={'public_access': True}),
        Finding(scan_id=scan.id, asset_id='asset-ec2-1', rule_id=rules[3].id, status='Open', state='Pass', severity=rules[3].severity, details={'encrypted': True})
    ]
    for f in fnds:
        db.session.add(f)

    db.session.commit()
    print(json.dumps({
        'message': 'Seeded sample data',
        'scan_id': scan.id,
        'asset_ids': [a.id for a in assets],
        'rule_keys': [r.key for r in rules],
        'finding_ids': [f.id for f in fnds]
    }, indent=2))

