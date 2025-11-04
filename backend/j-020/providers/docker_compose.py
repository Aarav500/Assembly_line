import os
import shutil
import subprocess
import json
import random
import string
from typing import Dict, Any, List

from .base import BaseProvider, ProviderError


def _rand_suffix(n=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

class DockerComposeProvider(BaseProvider):
    def __init__(self, data_dir: str, templates_dir: str):
        super().__init__(data_dir, templates_dir)
        self.compose_cmd = self._detect_compose_cmd()

    def _detect_compose_cmd(self) -> List[str]:
        # Prefer 'docker compose' then fallback to 'docker-compose'
        try:
            subprocess.run(["docker", "compose", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return ["docker", "compose"]
        except Exception:
            pass
        try:
            subprocess.run(["docker-compose", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return ["docker-compose"]
        except Exception:
            raise ProviderError("Docker Compose is not available. Install Docker and Docker Compose.")

    def _run(self, args: List[str], cwd: str, timeout: int = 120) -> subprocess.CompletedProcess:
        cmd = self.compose_cmd + args
        return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, text=True)

    def _template_path(self, template: str) -> str:
        path = os.path.join(self.templates_dir, template)
        if not os.path.isdir(path):
            raise ProviderError(f"Template '{template}' not found at {path}")
        return path

    def _workdir(self, sandbox_id: str) -> str:
        return os.path.join(self.data_dir, "sandboxes", sandbox_id, "workdir")

    def _project_name(self, sandbox_id: str) -> str:
        return f"sbx_{sandbox_id[:8]}_{_rand_suffix()}"

    def provision(self, sandbox_id: str, template: str, env: Dict[str, str]) -> Dict[str, Any]:
        tpath = self._template_path(template)
        wdir = self._workdir(sandbox_id)
        if os.path.exists(wdir):
            shutil.rmtree(wdir, ignore_errors=True)
        os.makedirs(os.path.dirname(wdir), exist_ok=True)
        shutil.copytree(tpath, wdir)

        project_name = self._project_name(sandbox_id)
        env_vars = dict(env or {})
        env_vars.setdefault("SANDBOX_ID", sandbox_id)
        env_vars.setdefault("PROJECT_NAME", project_name)

        # Write .env to compose dir
        env_file_path = os.path.join(wdir, ".env")
        with open(env_file_path, "w") as f:
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")

        # Compose up
        up = self._run(["-p", project_name, "up", "-d"], cwd=wdir)
        if up.returncode != 0:
            # try cleanup
            try:
                self._run(["-p", project_name, "down", "-v"], cwd=wdir, timeout=60)
            except Exception:
                pass
            raise ProviderError(f"Failed to bring up compose: {up.stderr.strip() or up.stdout.strip()}")

        ports = self._collect_ports(wdir, project_name)
        return {
            "project": project_name,
            "workdir": wdir,
            "env": env_vars,
            "ports": ports,
        }

    def _collect_ports(self, wdir: str, project_name: str) -> List[dict]:
        # Try JSON format first (Compose v2)
        res = self._run(["-p", project_name, "ps", "--format", "json"], cwd=wdir)
        if res.returncode == 0:
            try:
                data = json.loads(res.stdout or "[]")
                ports = []
                for svc in data:
                    publishers = svc.get("Publishers") or []
                    for p in publishers:
                        ports.append({
                            "service": svc.get("Name"),
                            "container_port": p.get("TargetPort"),
                            "protocol": p.get("Protocol"),
                            "host_ip": p.get("PublishedIp") or "0.0.0.0",
                            "host_port": p.get("PublishedPort"),
                        })
                return ports
            except Exception:
                pass
        # Fallback: parse text output
        res = self._run(["-p", project_name, "ps"], cwd=wdir)
        ports = []
        if res.returncode == 0:
            lines = (res.stdout or "").splitlines()
            for line in lines[1:]:
                if "->" in line:
                    # crude parse
                    try:
                        parts = line.split()
                        svc = parts[0]
                        mapping = parts[-1]
                        # e.g. 0.0.0.0:49176->80/tcp
                        host, right = mapping.split("->")
                        host_ip, host_port = host.split(":") if ":" in host else ("0.0.0.0", host)
                        cont_port, proto = right.split("/")
                        ports.append({
                            "service": svc,
                            "container_port": int(cont_port),
                            "protocol": proto,
                            "host_ip": host_ip,
                            "host_port": int(host_port),
                        })
                    except Exception:
                        continue
        return ports

    def teardown(self, sandbox_id: str, provider_data: Dict[str, Any]) -> None:
        project = (provider_data or {}).get("project")
        wdir = (provider_data or {}).get("workdir")
        if not project or not wdir:
            # nothing to do
            return
        down = self._run(["-p", project, "down", "-v"], cwd=wdir)
        if down.returncode != 0:
            # try without -v
            self._run(["-p", project, "down"], cwd=wdir)

    def status(self, sandbox_id: str, provider_data: Dict[str, Any]) -> Dict[str, Any]:
        project = (provider_data or {}).get("project")
        wdir = (provider_data or {}).get("workdir")
        if not project or not wdir:
            return {"state": "unknown"}
        res = self._run(["-p", project, "ps", "--format", "json"], cwd=wdir)
        state = "unknown"
        services = []
        if res.returncode == 0:
            try:
                data = json.loads(res.stdout or "[]")
                for svc in data:
                    services.append({
                        "name": svc.get("Name"),
                        "state": svc.get("State"),
                    })
                # If any service is running -> running, else stopped
                if any(s.get("state") == "running" for s in services):
                    state = "running"
                elif all(s.get("state") == "exited" for s in services) and services:
                    state = "stopped"
                else:
                    state = "unknown"
            except Exception:
                state = "unknown"
        else:
            # fallback
            res2 = self._run(["-p", project, "ps"], cwd=wdir)
            if res2.returncode == 0 and res2.stdout:
                if "running" in res2.stdout:
                    state = "running"
                elif "Exit" in res2.stdout or "exited" in res2.stdout:
                    state = "stopped"
        ports = self._collect_ports(wdir, project)
        return {"state": state, "services": services, "ports": ports}

    def stop(self, sandbox_id: str, provider_data: Dict[str, Any]) -> None:
        project = (provider_data or {}).get("project")
        wdir = (provider_data or {}).get("workdir")
        if not project or not wdir:
            return
        self._run(["-p", project, "stop"], cwd=wdir)

    def start(self, sandbox_id: str, provider_data: Dict[str, Any]) -> None:
        project = (provider_data or {}).get("project")
        wdir = (provider_data or {}).get("workdir")
        if not project or not wdir:
            return
        self._run(["-p", project, "start"], cwd=wdir)

