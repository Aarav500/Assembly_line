import argparse
import json
import os
import sys
from typing import List
from cdn.purger import get_purger_from_env, PurgeError


def main():
    parser = argparse.ArgumentParser(description="Purge CDN caches")
    parser.add_argument("--provider", help="CDN provider (cloudflare|fastly|cloudfront)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="Purge everything")
    group.add_argument("--paths", nargs="*", help="Paths or URLs to purge")
    group.add_argument("--tags", nargs="*", help="Tags/keys to purge")
    group.add_argument("--keys", nargs="*", help="Alias for tags/keys to purge")
    parser.add_argument("--soft", action="store_true", default=True, help="Soft purge where supported (default)")
    parser.add_argument("--hard", dest="soft", action="store_false", help="Hard purge where supported")
    parser.add_argument("--dry-run", action="store_true", help="Do not perform actions, print instead")

    args = parser.parse_args()

    if args.provider:
        os.environ["CDN_PROVIDER"] = args.provider

    try:
        purger = get_purger_from_env()
    except PurgeError as e:
        print(f"Error: {e}")
        sys.exit(2)

    if args.dry_run:
        print("[dry-run] Would purge with:")
        print(json.dumps({
            "provider": os.getenv("CDN_PROVIDER"),
            "all": args.all,
            "paths": args.paths,
            "tags": args.tags or args.keys,
            "soft": args.soft
        }, indent=2))
        sys.exit(0)

    try:
        if args.all:
            res = purger.purge_all(soft=args.soft)
        elif args.paths is not None:
            res = purger.purge_paths(args.paths, soft=args.soft)
        else:
            keys: List[str] = []
            if args.tags:
                keys.extend(args.tags)
            if args.keys:
                keys.extend(args.keys)
            if not keys:
                print("Nothing to purge: provide --all, --paths, or --tags/--keys", file=sys.stderr)
                sys.exit(1)
            res = purger.purge_keys(keys, soft=args.soft)
        print(json.dumps({"ok": True, "result": res}, default=str))
    except PurgeError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()

