#!/usr/bin/env python3
import argparse
import json
import os
from orchestrator.engine import Orchestrator

parser = argparse.ArgumentParser(description="Manage PR preview environments")
sub = parser.add_subparsers(dest="cmd")

c1 = sub.add_parser("create", help="Create/Update an environment")
c1.add_argument("pr", type=int)
c1.add_argument("clone_url")
c1.add_argument("ref", help="branch ref, e.g., feature/xyz")
c1.add_argument("--sha", default="")
c1.add_argument("--host", default=os.getenv("PUBLIC_HOST", "localhost"))
c1.add_argument("--base-port", type=int, default=int(os.getenv("BASE_PORT", "10080")))
c1.add_argument("--container-port", type=int, default=int(os.getenv("CONTAINER_PORT", "8000")))
c1.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""))

c2 = sub.add_parser("delete", help="Teardown an environment")
c2.add_argument("pr", type=int)
c2.add_argument("--host", default=os.getenv("PUBLIC_HOST", "localhost"))
c2.add_argument("--base-port", type=int, default=int(os.getenv("BASE_PORT", "10080")))
c2.add_argument("--container-port", type=int, default=int(os.getenv("CONTAINER_PORT", "8000")))

c3 = sub.add_parser("list", help="List environments")
c3.add_argument("--host", default=os.getenv("PUBLIC_HOST", "localhost"))
c3.add_argument("--base-port", type=int, default=int(os.getenv("BASE_PORT", "10080")))
c3.add_argument("--container-port", type=int, default=int(os.getenv("CONTAINER_PORT", "8000")))


def main():
    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    orch = Orchestrator(base_port=args.base_port, container_port=args.container_port, public_host=args.host)

    if args.cmd == "create":
        info = orch.ensure_environment(
            pr_number=args.pr,
            clone_url=args.clone_url,
            ref=args.ref,
            sha=args.sha or None,
            gh_token=args.token or None,
        )
        print(json.dumps(info, indent=2))
    elif args.cmd == "delete":
        info = orch.teardown_environment(args.pr)
        print(json.dumps(info, indent=2))
    elif args.cmd == "list":
        info = orch.list_environments()
        print(json.dumps(info, indent=2))

if __name__ == "__main__":
    main()

