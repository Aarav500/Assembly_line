import os
import sys
import argparse
import json
import requests

DEFAULT_BASE = os.environ.get("REGISTRY_BASE", "http://localhost:8000")
TOKEN = os.environ.get("REGISTRY_TOKEN")

def auth_headers():
    if TOKEN:
        return {"Authorization": f"Bearer {TOKEN}"}
    return {}


def cmd_upload_artifact(args):
    url = f"{args.base}/artifacts"
    files = {"file": open(args.file, "rb")}
    data = {"name": args.name}
    if args.tag:
        data["tag"] = args.tag
    r = requests.post(url, files=files, data=data, headers=auth_headers())
    print(json.dumps(r.json(), indent=2))
    r.raise_for_status()


def cmd_tag_artifact(args):
    url = f"{args.base}/artifacts/{args.name}/tags"
    payload = {"tag": args.tag, "hash": args.hash}
    r = requests.post(url, json=payload, headers=auth_headers())
    print(json.dumps(r.json(), indent=2))
    r.raise_for_status()


def cmd_list_artifacts(args):
    url = f"{args.base}/artifacts/{args.name}"
    r = requests.get(url)
    print(json.dumps(r.json(), indent=2))


def cmd_download_artifact(args):
    if args.tag:
        url = f"{args.base}/artifacts/{args.name}/tags/{args.tag}"
    else:
        url = f"{args.base}/artifacts/{args.name}/{args.hash}"
    r = requests.get(url)
    r.raise_for_status()
    out = args.output or os.path.basename(url)
    with open(out, "wb") as f:
        f.write(r.content)
    print(f"Saved to {out}")


def cmd_upload_module(args):
    url = f"{args.base}/modules/{args.name}/{args.version}"
    files = {"file": open(args.file, "rb")}
    data = {}
    if args.metadata:
        data["metadata"] = args.metadata
    r = requests.post(url, files=files, data=data, headers=auth_headers())
    print(json.dumps(r.json(), indent=2))
    r.raise_for_status()


def cmd_list_modules(args):
    url = f"{args.base}/modules"
    r = requests.get(url)
    print(json.dumps(r.json(), indent=2))


def cmd_list_versions(args):
    url = f"{args.base}/modules/{args.name}"
    r = requests.get(url)
    print(json.dumps(r.json(), indent=2))


def cmd_download_module(args):
    url = f"{args.base}/modules/{args.name}/{args.version}"
    r = requests.get(url)
    r.raise_for_status()
    out = args.output or os.path.basename(url)
    with open(out, "wb") as f:
        f.write(r.content)
    print(f"Saved to {out}")


def main():
    parser = argparse.ArgumentParser(description="Infra registry CLI")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Base URL of registry")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("upload-artifact")
    p.add_argument("name")
    p.add_argument("file")
    p.add_argument("--tag")
    p.set_defaults(func=cmd_upload_artifact)

    p = sub.add_parser("tag-artifact")
    p.add_argument("name")
    p.add_argument("tag")
    p.add_argument("hash")
    p.set_defaults(func=cmd_tag_artifact)

    p = sub.add_parser("list-artifacts")
    p.add_argument("name")
    p.set_defaults(func=cmd_list_artifacts)

    p = sub.add_parser("download-artifact")
    p.add_argument("name")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--hash")
    g.add_argument("--tag")
    p.add_argument("--output")
    p.set_defaults(func=cmd_download_artifact)

    p = sub.add_parser("upload-module")
    p.add_argument("name")
    p.add_argument("version")
    p.add_argument("file")
    p.add_argument("--metadata")
    p.set_defaults(func=cmd_upload_module)

    p = sub.add_parser("list-modules")
    p.set_defaults(func=cmd_list_modules)

    p = sub.add_parser("list-versions")
    p.add_argument("name")
    p.set_defaults(func=cmd_list_versions)

    p = sub.add_parser("download-module")
    p.add_argument("name")
    p.add_argument("version")
    p.add_argument("--output")
    p.set_defaults(func=cmd_download_module)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    args.func(args)

if __name__ == "__main__":
    main()

