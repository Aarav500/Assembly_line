from datetime import datetime
from typing import Dict, List, Set, Tuple


class RetentionService:
    def __init__(self, storage, policy_cfg: dict):
        self.storage = storage
        self.policy_cfg = policy_cfg or {}

    @staticmethod
    def _parse_ts(ts: str) -> datetime:
        try:
            # Expect ISO with Z
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            return datetime.fromisoformat(ts)
        except Exception:
            # fallback from id prefix
            try:
                return datetime.strptime(ts.split("_")[0], "%Y%m%dT%H%M%SZ")
            except Exception:
                return datetime.min

    def _bucket_keys(self, dt: datetime) -> Dict[str, Tuple]:
        # Return keys for daily, weekly, monthly
        iso = dt.isocalendar()
        return {
            "daily": (dt.year, dt.month, dt.day),
            "weekly": (dt.year, iso.week),
            "monthly": (dt.year, dt.month),
        }

    def apply(self) -> Dict:
        items = self.storage.list_backups()
        # Sort newest first
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        daily_keep = int(self.policy_cfg.get("daily", 7) or 0)
        weekly_keep = int(self.policy_cfg.get("weekly", 4) or 0)
        monthly_keep = int(self.policy_cfg.get("monthly", 12) or 0)

        keep_ids: Set[str] = set()
        buckets_seen = {"daily": [], "weekly": [], "monthly": []}

        for item in items:
            dt = self._parse_ts(item.get("timestamp") or item.get("id", ""))
            keys = self._bucket_keys(dt)
            bid = item.get("id")
            # daily
            if daily_keep > 0:
                key = keys["daily"]
                if key not in buckets_seen["daily"]:
                    buckets_seen["daily"].append(key)
                    if len(buckets_seen["daily"]) <= daily_keep:
                        keep_ids.add(bid)
            # weekly
            if weekly_keep > 0:
                key = keys["weekly"]
                if key not in buckets_seen["weekly"]:
                    buckets_seen["weekly"].append(key)
                    if len(buckets_seen["weekly"]) <= weekly_keep:
                        keep_ids.add(bid)
            # monthly
            if monthly_keep > 0:
                key = keys["monthly"]
                if key not in buckets_seen["monthly"]:
                    buckets_seen["monthly"].append(key)
                    if len(buckets_seen["monthly"]) <= monthly_keep:
                        keep_ids.add(bid)

        delete_ids: List[str] = []
        for item in items:
            bid = item.get("id")
            if bid not in keep_ids:
                delete_ids.append(bid)

        deleted: List[str] = []
        for bid in delete_ids:
            try:
                self.storage.delete_backup(bid)
                deleted.append(bid)
            except Exception:
                continue

        return {
            "kept": sorted(list(keep_ids)),
            "deleted": deleted,
            "total_before": len(items),
            "total_after": len(items) - len(deleted),
            "policy": {
                "daily": daily_keep,
                "weekly": weekly_keep,
                "monthly": monthly_keep,
            },
        }

