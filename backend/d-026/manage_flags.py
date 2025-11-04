import os
import sys
import argparse
from feature_flags import FileKV, _boolify


def parse_value(val: str):
    if val is None:
        return None
    lb = val.lower()
    if lb in ("true", "false", "1", "0", "yes", "no", "on", "off"):
        return _boolify(lb, default=False)
    # try int
    try:
        return int(val)
    except ValueError:
        pass
    # fallback string
    return val


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage feature flags in a JSON file (deployment-time KV store)")
    parser.add_argument("command", choices=["get", "set", "unset", "list"], help="Command to execute")
    parser.add_argument("name", nargs="?", help="Flag name for get/set/unset")
    parser.add_argument("value", nargs="?", help="Value for set (true/false/1/0/strings)")
    parser.add_argument("--file", "-f", default=os.getenv("FEATURE_FLAGS_FILE", "flags.json"), help="Path to flags JSON file")

    args = parser.parse_args(argv)

    kv = FileKV(args.file)

    if args.command == "list":
        data = kv.all()
        for k, v in sorted(data.items()):
            print(f"{k}={v}")
        return 0

    if not args.name:
        print("Error: name is required for this command", file=sys.stderr)
        return 1

    name = args.name

    if args.command == "get":
        v = kv.get(name)
        if v is None:
            print("<unset>")
        else:
            print(v)
        return 0

    if args.command == "unset":
        data = kv.all()
        if name in data:
            del data[name]
            # write back
            for k, v in list(data.items()):
                pass
            # Reuse set to persist by writing all keys
            # Simpler: overwrite file via internal method - emulate by clearing and setting
            # Since FileKV doesn't expose bulk write, emulate by setting dummy then rewrite
            # We'll directly re-initialize kv to force write
            # Build new file
            import json, tempfile, shutil
            directory = os.path.dirname(args.file) or "."
            fd, tmp_path = tempfile.mkstemp(prefix="flags.", suffix=".json", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                    json.dump(data, tmp, indent=2, sort_keys=True)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                shutil.move(tmp_path, args.file)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            print(f"Unset {name}")
        else:
            print(f"{name} was not set")
        return 0

    if args.command == "set":
        if args.value is None:
            print("Error: value is required for set", file=sys.stderr)
            return 1
        val = parse_value(args.value)
        kv.set(name, val)
        print(f"Set {name}={val}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

