#!/usr/bin/env python3
import argparse
import os
import sys
from app import create_app
from app.config_loader import load_and_validate_config


def cmd_validate(args) -> int:
    try:
        _ = load_and_validate_config(config_dir=args.config_dir, env=args.env)
        print(f"Configuration for env='{args.env}' is valid.")
        return 0
    except Exception as e:
        print(f"Validation failed: {e}", file=sys.stderr)
        return 1


def cmd_runserver(args) -> int:
    app = create_app(env=args.env, config_dir=args.config_dir)
    cfg = app.config.get("APP_CONFIG", {})
    host = cfg.get("app", {}).get("host", "0.0.0.0")
    port = int(cfg.get("app", {}).get("port", 5000))
    debug = bool(cfg.get("app", {}).get("debug", False))
    app.run(host=host, port=port, debug=debug)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Configuration management utilities")
    parser.add_argument("--env", default=os.getenv("APP_ENV", "development"), help="App environment (development|production|testing)")
    parser.add_argument("--config-dir", default=os.getenv("APP_CONFIG_DIR", os.path.join(os.getcwd(), "config")), help="Path to config directory")

    subparsers = parser.add_subparsers(dest="command")

    p_val = subparsers.add_parser("validate-config", help="Validate merged configuration")
    p_val.set_defaults(func=cmd_validate)

    p_run = subparsers.add_parser("runserver", help="Run Flask dev server")
    p_run.set_defaults(func=cmd_runserver)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

