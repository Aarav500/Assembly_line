import argparse
import os
import sys
import time
from pathlib import Path

from .engine import RunbookEngine
from .utils.config import load_config
from .utils.logger import get_logger
from .utils.notifier import Notifier
from .utils.incident_store import IncidentStore
from .self_healing.actions import Actions
from .self_healing.checks import Checks


def build_engine(args):
    root_dir = Path(__file__).resolve().parent.parent
    config_path = Path(args.config) if args.config else root_dir / "config" / "config.yaml"
    config = load_config(config_path)

    logger = get_logger("runbook", level=config.get("logging", {}).get("level", "INFO"), json_output=config.get("logging", {}).get("json", True), file_path=config.get("logging", {}).get("file"))

    store = IncidentStore(base_dir=Path(config.get("incident_store", {}).get("base_dir", "./incidents")))
    notifier = Notifier(config.get("notifications", {}), logger=logger)

    runbook_dir = root_dir / "runbook_automation" / "runbooks"
    actions = Actions(config=config, logger=logger, store=store, notifier=notifier)
    checks = Checks(config=config, logger=logger)

    engine = RunbookEngine(
        config=config,
        runbook_dir=runbook_dir,
        store=store,
        notifier=notifier,
        logger=logger,
        actions=actions,
        checks=checks,
    )
    return engine, logger


def main(argv=None):
    parser = argparse.ArgumentParser(prog="runbook-automation", description="Automated runbooks for common incidents with self-healing and documentation")
    parser.add_argument("command", choices=["list", "run", "simulate"], help="Command to execute")
    parser.add_argument("--incident", "-i", dest="incident", help="Incident/runbook ID to run (e.g., cpu_spike)")
    parser.add_argument("--config", "-c", dest="config", help="Path to config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Do not apply changes, simulate steps")
    parser.add_argument("--force", action="store_true", help="Force run even if trigger not met")
    parser.add_argument("--target-service", dest="target_service", help="Target service name (for service-related runbooks)")
    parser.add_argument("--mount-point", dest="mount_point", help="Target mount point (for disk runbooks)")
    parser.add_argument("--context", nargs="*", help="Additional context key=value")

    args = parser.parse_args(argv)

    engine, logger = build_engine(args)

    if args.command == "list":
        runbooks = engine.list_runbooks()
        for rb in runbooks:
            print(f"{rb['id']}: {rb['name']} - {rb.get('description','')}")
        return 0

    if not args.incident:
        print("--incident is required for run/simulate", file=sys.stderr)
        return 2

    # Build context
    extra_ctx = {}
    if args.context:
        for kv in args.context:
            if "=" in kv:
                k, v = kv.split("=", 1)
                extra_ctx[k] = v
    if args.target_service:
        extra_ctx["target_service"] = args.target_service
    if args.mount_point:
        extra_ctx["mount_point"] = args.mount_point

    dry = args.dry_run or args.command == "simulate"

    try:
        result = engine.run(args.incident, context=extra_ctx, dry_run=dry, force=args.force)
        if result.get("status") == "completed":
            logger.info({"event": "runbook_completed", "incident": args.incident, "id": result.get("incident_id")})
            print(f"Incident {result.get('incident_id')} completed: {result.get('summary')}")
            return 0
        elif result.get("status") == "skipped":
            print(f"Runbook skipped: {result.get('reason')}")
            return 0
        else:
            print(f"Runbook failed: {result}", file=sys.stderr)
            return 1
    except KeyboardInterrupt:
        logger.warning({"event": "interrupted"})
        return 130
    except Exception as e:
        logger.exception({"event": "error", "error": str(e)})
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

