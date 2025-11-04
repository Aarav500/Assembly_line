import json
import os
import sys
from cdn.purger import get_purger_from_env, PurgeError


def _read_changed_paths(manifest_path: str):
    if not manifest_path:
        return []
    if not os.path.exists(manifest_path):
        return []
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "paths" in data:
            return data.get("paths", [])
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def main():
    provider = os.getenv("CDN_PROVIDER", "")
    app_name = os.getenv("APP_NAME", "app")
    release = os.getenv("RELEASE_SHA", "")
    prev_release = os.getenv("PREVIOUS_RELEASE_SHA", "")
    purge_all_flag = (os.getenv("CDN_PURGE_ALL_ON_DEPLOY", "false").lower() in {"1", "true", "yes", "on"})
    changed_manifest = os.getenv("DEPLOY_CHANGED_PATHS_FILE", "")

    print(f"post_deploy: provider={provider} app={app_name} release={release} prev={prev_release} purge_all={purge_all_flag}")

    try:
        purger = get_purger_from_env()
    except PurgeError as e:
        print(f"Purger init error: {e}")
        sys.exit(2)

    # Strategy:
    # - If purge_all_flag, purge everything
    # - Else try tag-based purge using app key and previous release key (if available)
    # - For CloudFront, prefer path-based purge using changed paths manifest or fallback to /*

    try:
        if purge_all_flag:
            res = purger.purge_all(soft=True)
            print(json.dumps({"action": "purge_all", "result": str(res)}))
            return

        # Attempt tag/key purge
        keys = [f"app:{app_name}"]
        if prev_release:
            keys.append(f"release:{prev_release}")

        tag_res = purger.purge_keys(keys, soft=True)
        print(json.dumps({"action": "purge_keys", "keys": keys, "result": str(tag_res)}))

        # For CloudFront, also consider path purges if a manifest is provided
        if provider == "cloudfront":
            paths = _read_changed_paths(changed_manifest)
            if paths:
                res = purger.purge_paths(paths, soft=True)
                print(json.dumps({"action": "purge_paths", "paths": paths, "result": str(res)}))
            else:
                # Small fallback to invalidate everything if we can't target by tags
                res = purger.purge_all(soft=True)
                print(json.dumps({"action": "purge_all_fallback", "result": str(res)}))

    except PurgeError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()

