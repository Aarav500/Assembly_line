import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.environ.get('DATABASE_URL', os.path.join('data','app.db'))


def seed():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Simple helper for ISO times
    now = datetime.utcnow()

    # Clear existing
    cur.executescript("""
    DELETE FROM evidences;
    DELETE FROM controls;
    DELETE FROM policies;
    DELETE FROM audit_logs;
    DELETE FROM users;
    """)

    # Policies
    policies = [
        (1, 'Access Control Policy', '1.3', 'SOC2', 'active', (now - timedelta(days=90)).isoformat()+'Z'),
        (2, 'Information Security Policy', '2.0', 'ISO27001', 'active', (now - timedelta(days=60)).isoformat()+'Z'),
        (3, 'Business Continuity Policy', '1.1', 'SOC2', 'active', (now - timedelta(days=30)).isoformat()+'Z'),
    ]
    cur.executemany("INSERT OR REPLACE INTO policies(id,name,version,framework,status,updated_at) VALUES (?,?,?,?,?,?)", policies)

    # Controls
    controls = [
        (1, 1, 'User Access Reviews', 'Quarterly review of user access', 'operational', 'security@acme.com', (now - timedelta(days=45)).isoformat()+'Z'),
        (2, 1, 'MFA Enforcement', 'All users must use MFA', 'operational', 'it@acme.com', (now - timedelta(days=20)).isoformat()+'Z'),
        (3, 2, 'Asset Inventory', 'Maintain inventory of assets', 'operational', 'itops@acme.com', (now - timedelta(days=10)).isoformat()+'Z'),
    ]
    cur.executemany("INSERT OR REPLACE INTO controls(id,policy_id,name,description,status,owner,updated_at) VALUES (?,?,?,?,?,?,?)", controls)

    # Evidences
    evidences = [
        (1, 1, 'csv', 's3://audit/acls_q1.csv', (now - timedelta(days=40)).isoformat()+'Z', 'collected', 'Quarterly ACL export'),
        (2, 2, 'screenshot', 'gs://evidence/mfa_admin.png', (now - timedelta(days=18)).isoformat()+'Z', 'collected', 'MFA enabled in admin portal'),
        (3, 3, 'report', 'file:///var/reports/asset_inventory.pdf', (now - timedelta(days=7)).isoformat()+'Z', 'collected', 'Monthly inventory report'),
    ]
    cur.executemany("INSERT OR REPLACE INTO evidences(id,control_id,type,uri,collected_at,status,notes) VALUES (?,?,?,?,?,?,?)", evidences)

    # Users
    users = [
        (1, 'Alice Smith', 'alice.smith@acme.com', 'Admin', 1, (now - timedelta(days=5)).isoformat()+'Z'),
        (2, 'Bob Jones', 'bob.jones@acme.com', 'Auditor', 1, (now - timedelta(days=3)).isoformat()+'Z'),
        (3, 'Charlie Doe', 'charlie.doe@acme.com', 'Engineer', 1, (now - timedelta(days=1)).isoformat()+'Z'),
    ]
    cur.executemany("INSERT OR REPLACE INTO users(id,name,email,role,active,updated_at) VALUES (?,?,?,?,?,?)", users)

    # Audit logs
    logs = []
    base = now - timedelta(days=30)
    for i in range(1, 51):
        ts = (base + timedelta(hours=i)).isoformat()+'Z'
        actor = users[i % len(users)][2]  # email
        action = 'update' if i % 3 == 0 else 'read'
        entity_type = 'control' if i % 2 == 0 else 'policy'
        entity_id = (i % 3) + 1
        details = {"ip": f"10.0.0.{i%255}", "user_agent": "seed/1.0"}
        logs.append((i, actor, action, entity_type, entity_id, ts, json_dumps(details)))
    cur.executemany("INSERT OR REPLACE INTO audit_logs(id,actor,action,entity_type,entity_id,timestamp,details_json) VALUES (?,?,?,?,?,?,?)", logs)

    conn.commit()
    conn.close()
    print("Seeded database at", DB_PATH)


def json_dumps(obj):
    import json
    return json.dumps(obj)


if __name__ == '__main__':
    seed()

