import argparse
import json
import sys
from pathlib import Path

from config import Config
from db import get_session, engine
from models import Base, Migration, Approval
from safety_checks import analyze
from executor import dry_run as exec_dry_run, apply as exec_apply

# Ensure tables exist
with engine.begin() as conn:
    Base.metadata.create_all(bind=conn)


def cmd_submit(args):
    sql_text = None
    if args.file:
        sql_text = Path(args.file).read_text(encoding='utf-8')
    else:
        sql_text = sys.stdin.read()
    if not sql_text:
        print("No SQL provided", file=sys.stderr)
        sys.exit(1)
    target_env = (args.env or 'dev').lower()
    if target_env not in Config.TARGET_DBS:
        print(f"Unknown env '{target_env}'. Known: {', '.join(Config.TARGET_DBS.keys())}")
        sys.exit(2)
    issues = analyze(sql_text)
    status = 'needs_approval'
    if any(i.get('severity') == 'error' for i in issues):
        status = 'blocked'

    with get_session() as session:
        mig = Migration(
            title=args.title,
            description=args.description,
            created_by=args.user,
            target_env=target_env,
            sql=sql_text,
            status=status,
        )
        session.add(mig)
        session.flush()
        mig.set_issues(issues)
        try:
            with open(mig.sql_file_path(), 'w', encoding='utf-8') as f:
                f.write(sql_text)
        except Exception:
            pass
        session.add(mig)
        print(json.dumps(mig.to_dict(), indent=2))


def cmd_list(args):
    with get_session() as session:
        q = session.query(Migration)
        if args.status:
            q = q.filter(Migration.status == args.status)
        for m in q.order_by(Migration.created_at.desc()).all():
            print(f"[{m.id}] {m.title} env={m.target_env} status={m.status} created_at={m.created_at}")


def cmd_dry_run(args):
    with get_session() as session:
        mig = session.get(Migration, args.id)
        if not mig:
            print("Migration not found", file=sys.stderr)
            sys.exit(1)
        ok, log = exec_dry_run(mig.sql, mig.target_env)
        mig.dry_run_status = 'success' if ok else 'failed'
        mig.dry_run_log = log
        session.add(mig)
        print(log)
        sys.exit(0 if ok else 3)


def cmd_approve(args):
    with get_session() as session:
        mig = session.get(Migration, args.id)
        if not mig:
            print("Migration not found", file=sys.stderr)
            sys.exit(1)
        app = Approval(migration_id=mig.id, user=args.user, role=args.role.lower(), comment=args.comment)
        session.add(app)
        session.flush()
        # Update status if ready
        roles_required = set(Config.REQUIRED_ROLES.get(mig.target_env, []))
        roles_present = set(a.role for a in mig.approvals)
        if roles_required.issubset(roles_present) and mig.status != 'blocked':
            mig.status = 'approved'
        else:
            mig.status = 'needs_approval'
        session.add(mig)
        print(json.dumps(mig.to_dict(), indent=2))


def cmd_apply(args):
    with get_session() as session:
        mig = session.get(Migration, args.id)
        if not mig:
            print("Migration not found", file=sys.stderr)
            sys.exit(1)
        issues = mig.get_issues()
        if any(i.get('severity') == 'error' for i in issues):
            print("Blocking issues present; cannot apply", file=sys.stderr)
            sys.exit(2)
        required = set(Config.REQUIRED_ROLES.get(mig.target_env, []))
        present = set(a.role for a in mig.approvals)
        if not required.issubset(present):
            print(f"Missing approvals: {sorted(required - present)}", file=sys.stderr)
            sys.exit(2)
        if mig.dry_run_status != 'success' and not args.force:
            print("Dry-run not successful. Use --force to override.", file=sys.stderr)
            sys.exit(2)
        ok, log = exec_apply(mig.sql, mig.target_env)
        mig.apply_status = 'success' if ok else 'failed'
        mig.apply_log = log
        if ok:
            mig.status = 'applied'
            from datetime import datetime
            mig.applied_at = datetime.utcnow()
        else:
            mig.status = 'failed'
        session.add(mig)
        print(log)
        sys.exit(0 if ok else 3)


def main():
    parser = argparse.ArgumentParser(description='DB Migration Pipeline CLI')
    sub = parser.add_subparsers(dest='cmd')

    p_sub = sub.add_parser('submit', help='Submit a migration')
    p_sub.add_argument('--title', required=True)
    p_sub.add_argument('--description', default='')
    p_sub.add_argument('--user', default='cli')
    p_sub.add_argument('--env', default='dev')
    p_sub.add_argument('--file', help='SQL file path. If omitted, read from stdin')
    p_sub.set_defaults(func=cmd_submit)

    p_list = sub.add_parser('list', help='List migrations')
    p_list.add_argument('--status', help='Filter by status')
    p_list.set_defaults(func=cmd_list)

    p_dry = sub.add_parser('dry-run', help='Dry-run a migration')
    p_dry.add_argument('id', type=int)
    p_dry.set_defaults(func=cmd_dry_run)

    p_appr = sub.add_parser('approve', help='Approve a migration')
    p_appr.add_argument('id', type=int)
    p_appr.add_argument('--user', required=True)
    p_appr.add_argument('--role', required=True, help='Approval role (e.g., owner, dba)')
    p_appr.add_argument('--comment', default='')
    p_appr.set_defaults(func=cmd_approve)

    p_apply = sub.add_parser('apply', help='Apply a migration')
    p_apply.add_argument('id', type=int)
    p_apply.add_argument('--force', action='store_true', help='Apply even if dry-run not successful')
    p_apply.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    if not hasattr(args, 'func'):
        parser.print_help()
        return
    args.func(args)

if __name__ == '__main__':
    main()

