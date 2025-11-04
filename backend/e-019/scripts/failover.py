#!/usr/bin/env python3
import argparse
import json
import os
import sys

# Allow running from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import Config
from app.failover import FailoverManager
from app import state_manager


def cmd_status(mgr: FailoverManager) -> int:
    try:
        mgr.cfg.validate()
        eval = mgr.evaluate()
        print(json.dumps({
            "active_region": eval["active_region"],
            "primary_ok": eval["primary_ok"],
            "secondary_ok": eval["secondary_ok"],
            "state": eval["state"],
        }, indent=2))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_check(mgr: FailoverManager) -> int:
    return cmd_status(mgr)


def cmd_failover(mgr: FailoverManager, target: str | None) -> int:
    try:
        mgr.cfg.validate()
        if target:
            if target in ("primary", "secondary"):
                target = mgr.cfg.primary_region if target == "primary" else mgr.cfg.secondary_region
            res = mgr.set_active(target, reason="cli-manual")
            print(json.dumps(res, indent=2))
        else:
            res = mgr.evaluate_and_act()
            print(json.dumps(res, indent=2))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_failback(mgr: FailoverManager) -> int:
    try:
        mgr.cfg.validate()
        res = mgr.failback()
        print(json.dumps(res, indent=2))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_dns_sync(mgr: FailoverManager) -> int:
    try:
        mgr.cfg.validate()
        res = mgr.sync_dns()
        print(json.dumps(res, indent=2))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def cmd_simulate(mgr: FailoverManager, region: str, down: bool) -> int:
    try:
        key = region if region in ("primary", "secondary") else None
        if not key:
            raise ValueError("region must be 'primary' or 'secondary'")
        st = state_manager.set_simulated_outage(mgr.cfg.state_file, key, down)
        print(json.dumps({"state": st}, indent=2))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-region failover CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("check")

    p_failover = sub.add_parser("failover")
    p_failover.add_argument("--to", dest="target", help="primary|secondary|<region>")

    sub.add_parser("failback")

    sub.add_parser("dns-sync")

    p_sim = sub.add_parser("simulate")
    p_sim.add_argument("--region", required=True, choices=["primary", "secondary"])
    p_sim.add_argument("--down", action="store_true")
    p_sim.add_argument("--up", action="store_true")

    args = parser.parse_args()

    cfg = Config()
    mgr = FailoverManager(cfg)

    if args.cmd == "status":
        return cmd_status(mgr)
    if args.cmd == "check":
        return cmd_check(mgr)
    if args.cmd == "failover":
        return cmd_failover(mgr, args.target)
    if args.cmd == "failback":
        return cmd_failback(mgr)
    if args.cmd == "dns-sync":
        return cmd_dns_sync(mgr)
    if args.cmd == "simulate":
        if args.down and args.up:
            print("--down and --up are mutually exclusive", file=sys.stderr)
            return 2
        if not args.down and not args.up:
            print("Specify either --down or --up", file=sys.stderr)
            return 2
        down = bool(args.down)
        return cmd_simulate(mgr, args.region, down)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

