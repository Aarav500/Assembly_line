import threading
import time
import random
import uuid
from datetime import datetime, timedelta


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


class DataStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.entities = {}

    def init_sample_data(self):
        # Sample assets and users
        sample = []
        random.seed(42)
        # Assets
        for i in range(1, 8):
            ent_id = str(uuid.uuid4())
            vulns = []
            for v in range(random.randint(1, 4)):
                vulns.append({
                    "id": f"CVE-{random.randint(2016, 2025)}-{random.randint(1000,99999)}",
                    "severity": round(random.uniform(3.0, 9.8), 1),
                    "status": "open"
                })
            sample.append({
                "id": ent_id,
                "type": "asset",
                "name": f"srv-app-{i:02d}",
                "criticality": round(random.uniform(0.4, 0.95), 2),
                "exposure": round(random.uniform(0.2, 0.9), 2),
                "vulnerabilities": vulns,
                "controls": {
                    "edr_installed": random.random() > 0.5,
                    "logging": random.random() > 0.5,
                    "mfa_enabled": False
                },
                "anomalies": round(random.uniform(0.0, 6.0), 2),
                "incidents": random.randint(0, 3),
                "last_seen": now_iso(),
                "risk": {}
            })
        # Users
        for i in range(1, 6):
            ent_id = str(uuid.uuid4())
            sample.append({
                "id": ent_id,
                "type": "user",
                "name": f"user{i:02d}@example.com",
                "criticality": round(random.uniform(0.3, 0.8), 2),
                "exposure": round(random.uniform(0.1, 0.6), 2),
                "vulnerabilities": [],
                "controls": {
                    "mfa_enabled": random.random() > 0.4,
                    "edr_installed": False,
                    "logging": True
                },
                "anomalies": round(random.uniform(0.0, 5.0), 2),
                "incidents": random.randint(0, 2),
                "last_seen": now_iso(),
                "risk": {}
            })
        with self._lock:
            self.entities = {e["id"]: e for e in sample}

    def get_all(self):
        with self._lock:
            return [self._copy_entity(e) for e in self.entities.values()]

    def get(self, entity_id):
        with self._lock:
            e = self.entities.get(entity_id)
            return self._copy_entity(e) if e else None

    def update(self, entity_id, updates: dict):
        with self._lock:
            e = self.entities.get(entity_id)
            if not e:
                return False
            e.update(updates)
            e["last_seen"] = now_iso()
            return True

    def set_entity(self, entity):
        with self._lock:
            self.entities[entity["id"]] = entity

    def apply_action(self, entity_id, action):
        with self._lock:
            ent = self.entities.get(entity_id)
            if not ent:
                return {"ok": False, "error": "Not found"}
            etype = ent.get("type")
            # Define effects
            if action == "patch_top_vuln":
                open_v = [v for v in ent.get("vulnerabilities", []) if v.get("status") == "open"]
                if not open_v:
                    return {"ok": False, "error": "No open vulnerabilities"}
                # Patch the highest severity vuln
                top = sorted(open_v, key=lambda x: x.get("severity", 0), reverse=True)[0]
                for v in ent["vulnerabilities"]:
                    if v["id"] == top["id"]:
                        v["status"] = "patched"
                return {"ok": True}
            elif action == "restrict_exposure":
                ent["exposure"] = round(max(0.0, ent.get("exposure", 0.0) - 0.2), 2)
                return {"ok": True}
            elif action == "enable_mfa":
                ent.setdefault("controls", {})["mfa_enabled"] = True
                return {"ok": True}
            elif action == "install_edr":
                if etype != "asset":
                    return {"ok": False, "error": "EDR applicable to assets only"}
                ent.setdefault("controls", {})["edr_installed"] = True
                return {"ok": True}
            elif action == "enable_logging":
                ent.setdefault("controls", {})["logging"] = True
                return {"ok": True}
            elif action == "isolate_host":
                if etype != "asset":
                    return {"ok": False, "error": "Isolation for assets only"}
                ent["exposure"] = round(max(0.0, ent.get("exposure", 0.0) - 0.5), 2)
                ent["anomalies"] = round(max(0.0, ent.get("anomalies", 0.0) - 1.0), 2)
                return {"ok": True}
            elif action == "review_anomalies":
                ent["anomalies"] = round(max(0.0, ent.get("anomalies", 0.0) - 2.0), 2)
                return {"ok": True}
            elif action == "close_incidents":
                ent["incidents"] = max(0, ent.get("incidents", 0) - 1)
                return {"ok": True}
            elif action == "rotate_keys":
                if etype != "asset":
                    return {"ok": False, "error": "Key rotation for assets only"}
                # reduce exposure and anomalies slightly
                ent["exposure"] = round(max(0.0, ent.get("exposure", 0.0) - 0.1), 2)
                ent["anomalies"] = round(max(0.0, ent.get("anomalies", 0.0) - 0.5), 2)
                return {"ok": True}
            else:
                return {"ok": False, "error": f"Unknown action: {action}"}

    def random_drift(self):
        with self._lock:
            for ent in self.entities.values():
                # chance to add a vuln to assets
                if ent["type"] == "asset" and random.random() < 0.25:
                    ent.setdefault("vulnerabilities", []).append({
                        "id": f"CVE-{random.randint(2019, 2025)}-{random.randint(1000,99999)}",
                        "severity": round(random.uniform(4.0, 9.8), 1),
                        "status": "open"
                    })
                # anomalies drift
                ent["anomalies"] = round(max(0.0, min(10.0, ent.get("anomalies", 0.0) + random.uniform(-0.5, 0.8))), 2)
                # occasional incident
                if random.random() < 0.1:
                    ent["incidents"] = min(5, ent.get("incidents", 0) + 1)
                # exposure slight random walk
                ent["exposure"] = round(max(0.0, min(1.0, ent.get("exposure", 0.0) + random.uniform(-0.05, 0.05))), 2)
                ent["last_seen"] = now_iso()

    def _copy_entity(self, e):
        if not e:
            return None
        import copy
        return copy.deepcopy(e)

