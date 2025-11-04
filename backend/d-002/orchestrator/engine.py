import os
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any

from .utils import run_cmd, safe_rmtree, sanitize_int

STATE_DIR = Path("environments")
STATE_FILE = STATE_DIR / "state.json"

NAME_PREFIX = "pr-preview-pr"
IMAGE_PREFIX = "pr-preview"

class Orchestrator:
    def __init__(self, base_port: int, container_port: int, public_host: str = "localhost"):
        self.base_port = base_port
        self.container_port = container_port
        self.public_host = public_host
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if not STATE_FILE.exists():
            STATE_FILE.write_text(json.dumps({}, indent=2))

    def _load_state(self) -> Dict[str, Any]:
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}

    def _save_state(self, data: Dict[str, Any]):
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(STATE_FILE)

    def _port_for(self, pr_number: int) -> int:
        return self.base_port + pr_number

    def _env_dir(self, pr_number: int) -> Path:
        return STATE_DIR / f"pr-{pr_number}"

    def _container_name(self, pr_number: int) -> str:
        return f"{NAME_PREFIX}{pr_number}"

    def _image_tag(self, pr_number: int, sha: str | None = None) -> str:
        base = f"{IMAGE_PREFIX}-pr{pr_number}"
        if sha:
            short = sha[:12]
            return f"{base}:{short}"
        return f"{base}:latest"

    def list_environments(self) -> Dict[str, Any]:
        st = self._load_state()
        # Enrich with live container state
        for key, meta in st.items():
            cname = meta.get("container")
            rc, out, _ = run_cmd(["docker", "ps", "--filter", f"name=^/{cname}$", "--format", "{{.Status}}"])
            meta["container_status"] = out.strip() if rc == 0 else "unknown"
        return st

    def _auth_clone_url(self, clone_url: str, gh_token: str | None) -> str:
        if not gh_token:
            return clone_url
        # insert token: https://TOKEN@github.com/owner/repo.git
        if clone_url.startswith("https://"):
            return clone_url.replace("https://", f"https://{gh_token}@", 1)
        return clone_url

    def ensure_environment(self, pr_number: int, clone_url: str, ref: str, sha: str | None = None, gh_token: str | None = None, env_overrides: Dict[str, str] | None = None) -> Dict[str, Any]:
        pr_number = sanitize_int(pr_number)
        if not pr_number:
            raise ValueError("Invalid PR number")

        port = self._port_for(pr_number)
        env_dir = self._env_dir(pr_number)
        container_name = self._container_name(pr_number)
        image_latest = self._image_tag(pr_number)
        image_sha = self._image_tag(pr_number, sha)

        # Prepare clean env dir
        if env_dir.exists():
            safe_rmtree(env_dir)
        env_dir.mkdir(parents=True, exist_ok=True)

        # Clone
        auth_url = self._auth_clone_url(clone_url, gh_token)
        rc, out, err = run_cmd(["git", "clone", "--depth", "1", "--branch", ref, auth_url, str(env_dir)])
        if rc != 0:
            safe_rmtree(env_dir)
            raise RuntimeError(f"git clone failed: {err or out}")

        # Build image
        # We assume Dockerfile exists at repo root
        rc, out, err = run_cmd(["docker", "build", "-t", image_latest, "-f", "Dockerfile", "."], cwd=str(env_dir))
        if rc != 0:
            safe_rmtree(env_dir)
            raise RuntimeError(f"docker build failed: {err or out}")

        if sha:
            run_cmd(["docker", "tag", image_latest, image_sha])

        # Stop existing container if any
        self._stop_container_if_exists(container_name)

        # Run container
        env = {
            "PR_NUMBER": str(pr_number),
            "PR_SHA": sha or "",
        }
        if env_overrides:
            env.update({k: v for k, v in env_overrides.items() if isinstance(v, str)})

        docker_env = []
        for k, v in env.items():
            docker_env += ["-e", f"{k}={v}"]

        rc, out, err = run_cmd([
            "docker", "run", "-d", "--restart", "unless-stopped",
            "--name", container_name,
            "-p", f"{port}:{self.container_port}",
            *docker_env,
            image_latest,
        ])
        if rc != 0:
            # Cleanup image/container on failure
            self._stop_container_if_exists(container_name)
            raise RuntimeError(f"docker run failed: {err or out}")

        url = f"http://{self.public_host}:{port}"

        # Update state
        state = self._load_state()
        key = f"pr-{pr_number}"
        state[key] = {
            "pr_number": pr_number,
            "port": port,
            "url": url,
            "container": container_name,
            "image": image_latest,
            "image_sha": image_sha,
            "sha": sha,
            "updated_at": int(time.time()),
        }
        self._save_state(state)

        return state[key]

    def teardown_environment(self, pr_number: int) -> Dict[str, Any]:
        pr_number = sanitize_int(pr_number)
        container_name = self._container_name(pr_number)
        env_dir = self._env_dir(pr_number)
        image_latest = self._image_tag(pr_number)

        info = {
            "pr_number": pr_number,
            "container": container_name,
            "removed": [],
        }

        self._stop_container_if_exists(container_name, info)

        # Remove images (best-effort)
        run_cmd(["docker", "rmi", "-f", image_latest])

        # Remove specific sha-tagged images if present in state
        state = self._load_state()
        key = f"pr-{pr_number}"
        if key in state and state[key].get("image_sha"):
            run_cmd(["docker", "rmi", "-f", state[key]["image_sha"]])

        # Remove env dir
        safe_rmtree(env_dir)

        # Update state
        if key in state:
            del state[key]
            self._save_state(state)

        return info

    def _stop_container_if_exists(self, name: str, info: Dict[str, Any] | None = None):
        rc, out, err = run_cmd(["docker", "ps", "-a", "--filter", f"name=^/{name}$", "-q"])
        cid = out.strip()
        if cid:
            run_cmd(["docker", "rm", "-f", name])
            if info is not None:
                info.setdefault("removed", []).append(name)

