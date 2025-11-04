import time
import uuid
from typing import Dict, List

from .github_client import GitHubClient
from .runner_provider import DockerRunnerProvider
from .db import Database


class FleetManager:
    def __init__(self, db: Database, config):
        self.db = db
        self.config = config
        self.gh = GitHubClient(
            token=config.GH_TOKEN,
            api_url=config.GH_API_URL,
            scope=config.SCOPE,
            owner=config.REPO_OWNER,
            repo=config.REPO_NAME,
            org=config.ORG_NAME,
        )
        self.provider = DockerRunnerProvider(
            image=config.DOCKER_IMAGE,
            repo_owner=config.REPO_OWNER,
            repo_name=config.REPO_NAME,
            scope=config.SCOPE,
            org=config.ORG_NAME,
            mount_docker_sock=config.MOUNT_DOCKER_SOCK,
            network=config.DOCKER_NETWORK,
            runner_workdir=config.RUNNER_WORKDIR,
        )

    def settings(self) -> Dict:
        s = self.db.all_settings()
        return {
            "min_capacity": int(s.get("min_capacity", self.config.MIN_CAPACITY)),
            "max_capacity": int(s.get("max_capacity", self.config.MAX_CAPACITY)),
            "desired_capacity": int(s.get("desired_capacity", self.config.DESIRED_CAPACITY)),
            "scale_down_idle_minutes": int(s.get("scale_down_idle_minutes", self.config.SCALE_DOWN_IDLE_MINUTES)),
            "labels": s.get("labels", self.config.RUNNER_LABELS),
            "name_prefix": s.get("name_prefix", self.config.RUNNER_NAME_PREFIX),
        }

    def set_settings(self, **kwargs):
        for key, val in kwargs.items():
            if val is None:
                continue
            if key in ("min_capacity", "max_capacity", "desired_capacity", "scale_down_idle_minutes"):
                self.db.set_setting(key, str(int(val)))
            elif key in ("labels", "name_prefix"):
                self.db.set_setting(key, str(val))

    def inventory(self) -> Dict:
        runners = self.db.list_runners()
        gh_runners = self.gh.list_runners()
        gh_by_name = {x.get("name"): x for x in gh_runners}
        items = []
        online = 0
        busy = 0
        for r in runners:
            gh = gh_by_name.get(r["name"]) or {}
            r_status = gh.get("status") or r["status"] or "unknown"
            is_busy = bool(gh.get("busy"))
            if r_status == "online":
                online += 1
            if is_busy:
                busy += 1
            items.append({
                "name": r["name"],
                "container_id": r["container_id"],
                "labels": r["labels"],
                "github_runner_id": gh.get("id") or r["github_runner_id"],
                "status": r_status,
                "busy": is_busy,
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "last_busy_at": r["last_busy_at"],
                "last_online_at": r["last_online_at"],
                "last_idle_since": r["last_idle_since"],
            })
        queued = self.gh.count_queued_workflow_runs()
        return {
            "runners": items,
            "counts": {
                "managed": len(runners),
                "online": online,
                "busy": busy,
                "idle": max(0, online - busy),
                "queued_runs": queued,
            },
        }

    def provision_one(self) -> Dict:
        s = self.settings()
        token = self.gh.get_registration_token()
        # unique name
        name = f"{s['name_prefix']}-{uuid.uuid4().hex[:8]}"
        container_id = self.provider.provision(name=name, registration_token=token, labels=s["labels"])
        self.db.upsert_runner(name, container_id=container_id, labels=s["labels"], status="provisioning")
        return {"name": name, "container_id": container_id}

    def terminate_runner(self, name: str) -> bool:
        r = self.db.get_runner(name)
        if not r:
            return False
        # Try to remove via Docker
        self.provider.terminate(r["container_id"] or name)
        # Try to remove from GitHub if known
        gh_runners = {x.get("name"): x for x in self.gh.list_runners()}
        gh = gh_runners.get(name)
        if gh:
            try:
                self.gh.remove_runner(gh.get("id"))
            except Exception:
                pass
        self.db.delete_runner(name)
        return True

    def reconcile(self) -> Dict:
        # Update DB status from GitHub
        gh_runners = {x.get("name"): x for x in self.gh.list_runners()}
        for r in self.db.list_runners():
            gh = gh_runners.get(r["name"]) or {}
            status = gh.get("status") or r["status"] or "unknown"
            self.db.update_runner_status_fields(
                name=r["name"],
                status=status,
                github_runner_id=gh.get("id") if gh else None,
                busy=bool(gh.get("busy")) if gh else None,
                online=True if gh.get("status") == "online" else None,
            )
        # Scaling decision
        queued = self.gh.count_queued_workflow_runs()
        inv = self.inventory()
        counts = inv["counts"]
        s = self.settings()
        current_online = counts["online"]
        current_busy = counts["busy"]
        # Policy: needed = max(min_capacity, min(max_capacity, busy + queued))
        needed = max(s["min_capacity"], min(s["max_capacity"], current_busy + queued))
        delta = needed - current_online
        actions = {"scaled_up": 0, "scaled_down": 0}
        if delta > 0:
            for _ in range(delta):
                try:
                    self.provision_one()
                    actions["scaled_up"] += 1
                except Exception:
                    break
        elif delta < 0:
            # Try to remove idle runners older than idle threshold
            idle_threshold = s["scale_down_idle_minutes"] * 60
            now = time.time()
            # Build candidates list from GH state
            gh_map = gh_runners
            candidates = []
            for r in self.db.list_runners():
                gh = gh_map.get(r["name"]) or {}
                if gh.get("status") == "online" and not gh.get("busy"):
                    # Idle
                    ts = _parse_time(r["last_idle_since"]) or _parse_time(r["last_online_at"]) or _parse_time(r["created_at"]) or now
                    idle_for = now - ts
                    if idle_for >= idle_threshold:
                        candidates.append(r["name"])
            to_remove = min(-delta, len(candidates))
            for name in candidates[:to_remove]:
                try:
                    if self.terminate_runner(name):
                        actions["scaled_down"] += 1
                except Exception:
                    pass
        inv_after = self.inventory()
        return {"decision": {"needed": needed, "delta": delta}, "actions": actions, "inventory": inv_after}


def _parse_time(s):
    import datetime
    if not s:
        return None
    try:
        dt = datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
        return dt.replace(tzinfo=datetime.timezone.utc).timestamp()
    except Exception:
        return None

