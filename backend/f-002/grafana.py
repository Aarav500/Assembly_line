import os
import re
import json
import hashlib
import requests


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-") or "project"


def make_uid(prefix: str, name: str, suffix: str = "", maxlen: int = 40) -> str:
    s = slugify(name)
    base = f"{prefix}-{s}"
    if suffix:
        base = f"{base}-{suffix}"
    if len(base) <= maxlen:
        return base
    h = hashlib.sha1(name.encode()).hexdigest()[:8]
    parts = [prefix, h]
    if suffix:
        parts.append(suffix)
    uid = "-".join(parts)
    return uid[:maxlen]


def make_uids(project_name: str) -> dict:
    return {
        "folder_uid": make_uid("fold", project_name, ""),
        "overview_uid": make_uid("ovw", project_name, "ov"),
        "detail_uid": make_uid("dtl", project_name, "dt"),
    }


class GrafanaClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if api_token:
            self.session.headers.update({
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            })

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _req(self, method: str, path: str, expected=(200, 201, 202), **kwargs):
        resp = self.session.request(method, self._url(path), timeout=30, **kwargs)
        if resp.status_code not in (expected if isinstance(expected, (list, tuple)) else (expected,)):
            try:
                detail = resp.json()
            except Exception:
                detail = {"message": resp.text}
            raise Exception(f"Grafana API {method} {path} failed: {resp.status_code} {detail}")
        if resp.content:
            try:
                return resp.json()
            except ValueError:
                return resp.text
        return None

    def ensure_folder(self, folder_uid: str, title: str) -> dict:
        # Try create
        payload = {"uid": folder_uid, "title": title}
        try:
            created = self._req("POST", "/api/folders", json=payload, expected=(200, 201))
        except Exception:
            created = None
        # Get by uid
        data = self._req("GET", f"/api/folders/uid/{folder_uid}")
        return {"id": data["id"], "uid": data["uid"], "title": data["title"]}

    def delete_folder(self, folder_uid: str):
        self._req("DELETE", f"/api/folders/{folder_uid}", expected=(200, 202))

    def upsert_dashboard(self, dashboard: dict, folder_id: int) -> dict:
        body = {
            "dashboard": dashboard,
            "folderId": folder_id,
            "overwrite": True,
            "message": "Managed by prebuilt-grafana-dashboards app",
        }
        res = self._req("POST", "/api/dashboards/db", json=body, expected=(200, 202))
        return {
            "status": res.get("status"),
            "uid": res.get("uid"),
            "url": f"{self.base_url}{res.get('url')}" if res.get("url") else None,
            "slug": res.get("slug"),
        }

    def delete_dashboard(self, uid: str):
        self._req("DELETE", f"/api/dashboards/uid/{uid}", expected=(200, 202))


# Dashboard builders

def base_dashboard(uid: str, title: str, desc: str, project: str, tags=None):
    return {
        "id": None,
        "uid": uid,
        "title": title,
        "tags": ["managed", "project", slugify(project)] + (tags or []),
        "timezone": "browser",
        "schemaVersion": 38,
        "version": 1,
        "refresh": "30s",
        "time": {"from": "now-24h", "to": "now"},
        "timepicker": {"refresh_intervals": ["5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h"], "hidden": False},
        "style": "dark",
        "fiscalYearStartMonth": 0,
        "weekStart": "",
        "editable": True,
        "graphTooltip": 1,
        "description": desc,
        "links": [],
        "annotations": {"list": [{"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True, "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"}]},
        "templating": {
            "list": [
                {
                    "type": "constant",
                    "name": "project",
                    "label": "Project",
                    "query": project,
                    "current": {"text": project, "value": project, "selected": True},
                    "hide": 2
                }
            ]
        },
        "panels": []
    }


def ds_ref(ds_uid: str, ds_type: str):
    return {"type": ds_type, "uid": ds_uid}


def panel_stat(id_, title, grid, expr, ds_uid, ds_type, link_dashboard_uid=None):
    p = {
        "id": id_,
        "type": "stat",
        "title": title,
        "gridPos": grid,
        "datasource": ds_ref(ds_uid, ds_type),
        "options": {
            "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
            "orientation": "auto",
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "auto",
            "textMode": "auto",
        },
        "targets": [
            {"refId": "A", "expr": expr, "legendFormat": "", "exemplar": True}
        ],
        "fieldConfig": {
            "defaults": {
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 80}]}
            },
            "overrides": []
        },
    }
    if link_dashboard_uid:
        p["links"] = [{"title": "View details", "type": "dashboard", "dashboardUid": link_dashboard_uid, "includeVars": True, "targetBlank": False}]
    return p


def panel_timeseries(id_, title, grid, expr, ds_uid, ds_type, unit=None, link_dashboard_uid=None):
    p = {
        "id": id_,
        "type": "timeseries",
        "title": title,
        "gridPos": grid,
        "datasource": ds_ref(ds_uid, ds_type),
        "fieldConfig": {
            "defaults": {
                "unit": unit or "",
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 80}]}
            },
            "overrides": []
        },
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "single"}
        },
        "targets": [
            {"refId": "A", "expr": expr, "legendFormat": "", "exemplar": True}
        ]
    }
    if link_dashboard_uid:
        p["links"] = [{"title": "View details", "type": "dashboard", "dashboardUid": link_dashboard_uid, "includeVars": True, "targetBlank": False}]
    return p


def build_overview_dashboard(project: str, overview_uid: str, detail_uid: str, ds_uid: str, ds_type: str) -> dict:
    d = base_dashboard(
        uid=overview_uid,
        title=f"{project} • Overview",
        desc=f"Overview metrics for {project}. Click panels to drill down.",
        project=project,
        tags=["overview"],
    )

    d["links"].append({"title": "Open Detail", "type": "dashboard", "dashboardUid": detail_uid, "includeVars": True})

    panels = []
    panels.append(panel_stat(1, "Builds (24h)", {"h": 8, "w": 8, "x": 0, "y": 0},
                             f"sum(increase(ci_build_total{{project=\"$project\"}}[24h]))",
                             ds_uid, ds_type, link_dashboard_uid=detail_uid))
    panels.append(panel_stat(2, "Errors (24h)", {"h": 8, "w": 8, "x": 8, "y": 0},
                             f"sum(increase(app_errors_total{{project=\"$project\"}}[24h]))",
                             ds_uid, ds_type, link_dashboard_uid=detail_uid))
    panels.append(panel_stat(3, "p95 Latency (ms)", {"h": 8, "w": 8, "x": 16, "y": 0},
                             f"histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{project=\"$project\"}}[5m]))) * 1000",
                             ds_uid, ds_type, link_dashboard_uid=detail_uid))

    panels.append(panel_timeseries(4, "Request Rate (rps)", {"h": 10, "w": 24, "x": 0, "y": 8},
                                   f"sum(rate(http_requests_total{{project=\"$project\"}}[5m]))",
                                   ds_uid, ds_type, unit="req/s", link_dashboard_uid=detail_uid))

    d["panels"] = panels
    return d


def build_detail_dashboard(project: str, detail_uid: str, overview_uid: str, ds_uid: str, ds_type: str) -> dict:
    d = base_dashboard(
        uid=detail_uid,
        title=f"{project} • Detail",
        desc=f"Detailed metrics for {project}.",
        project=project,
        tags=["detail"],
    )

    d["links"].append({"title": "Back to Overview", "type": "dashboard", "dashboardUid": overview_uid, "includeVars": True})

    panels = []
    panels.append(panel_timeseries(10, "Error rate (5m)", {"h": 10, "w": 12, "x": 0, "y": 0},
                                   f"sum(rate(app_errors_total{{project=\"$project\"}}[5m]))",
                                   ds_uid, ds_type, unit="req/s"))

    panels.append(panel_timeseries(11, "Latency p50/p95/p99 (ms)", {"h": 10, "w": 12, "x": 12, "y": 0},
                                   f"histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket{{project=\"$project\"}}[5m]))) * 1000",
                                   ds_uid, ds_type, unit="ms"))

    # Additional quantiles overlay using overrides typically; here we add extra targets
    panels[-1]["targets"].append({"refId": "B", "expr": f"histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{project=\"$project\"}}[5m]))) * 1000"})
    panels[-1]["targets"].append({"refId": "C", "expr": f"histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{{project=\"$project\"}}[5m]))) * 1000"})

    panels.append(panel_timeseries(12, "Requests by status", {"h": 10, "w": 24, "x": 0, "y": 10},
                                   f"sum by (status) (rate(http_requests_total{{project=\"$project\"}}[5m]))",
                                   ds_uid, ds_type, unit="req/s"))

    panels.append(panel_timeseries(13, "CPU usage (cores)", {"h": 8, "w": 12, "x": 0, "y": 20},
                                   f"sum(rate(container_cpu_usage_seconds_total{{project=\"$project\"}}[5m]))",
                                   ds_uid, ds_type, unit="cores"))

    panels.append(panel_timeseries(14, "Memory working set (bytes)", {"h": 8, "w": 12, "x": 12, "y": 20},
                                   f"sum(container_memory_working_set_bytes{{project=\"$project\"}})",
                                   ds_uid, ds_type, unit="bytes"))

    d["panels"] = panels
    return d

