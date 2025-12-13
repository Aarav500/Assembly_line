import argparse
import json
import os
import posixpath
import shlex
import stat
import sys
import time
from pathlib import Path

import paramiko

DEFAULT_EXCLUDES = {
    ".git",
    "__pycache__",
}

TOPLEVEL_FILES = [
    "docker-compose.simple.yml",
    ".dockerignore",
]

DIRECTORIES = [
    "app",
    "docker",
]

REMOTE_BOOTSTRAP = "deploy/remote_bootstrap.sh"


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_target(config: dict, name: str) -> dict:
    for h in config.get("hosts", []):
        if h.get("name") == name:
            return h
    raise SystemExit(f"Target '{name}' not found in config")


def expanduser_path(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


def ssh_connect(host: str, port: int, user: str, key_path: str) -> paramiko.SSHClient:
    pkey = None
    key_path = expanduser_path(key_path)
    if key_path:
        try:
            pkey = paramiko.RSAKey.from_private_key_file(key_path)
        except Exception:
            pkey = paramiko.Ed25519Key.from_private_key_file(key_path)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=user, pkey=pkey)
    return client


def run_cmd(ssh: paramiko.SSHClient, cmd: str, timeout: int | None = None, get_pty: bool = False) -> tuple[int, str, str]:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=get_pty)
    out = stdout.read().decode()
    err = stderr.read().decode()
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def sftp_mkdirs(sftp: paramiko.SFTPClient, remote_dir: str):
    parts = remote_dir.strip("/").split("/")
    path = ""
    for part in parts:
        path = posixpath.join(path, part)
        try:
            sftp.stat("/" + path)
        except FileNotFoundError:
            sftp.mkdir("/" + path)


def sftp_put_file(sftp: paramiko.SFTPClient, local_path: Path, remote_path: str, mode: int | None = None):
    sftp.put(str(local_path), remote_path)
    if mode is not None:
        sftp.chmod(remote_path, mode)


def upload_directory(sftp: paramiko.SFTPClient, local_dir: Path, remote_dir: str):
    for root, dirs, files in os.walk(local_dir):
        # filter excludes
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
        rel_root = os.path.relpath(root, start=str(local_dir))
        target_root = remote_dir if rel_root == "." else posixpath.join(remote_dir, rel_root.replace("\\", "/"))
        try:
            sftp.stat(target_root)
        except FileNotFoundError:
            sftp.mkdir(target_root)
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                continue
            lp = Path(root) / f
            rp = posixpath.join(target_root, f)
            sftp.put(str(lp), rp)


def write_env_temp(env_dict: dict) -> Path:
    from tempfile import NamedTemporaryFile

    content_lines = []
    for k, v in (env_dict or {}).items():
        content_lines.append(f"{k}={v}")
    if not content_lines:
        content_lines.append("FLASK_ENV=production")
        content_lines.append("APP_PORT=80")
        content_lines.append("APP_MESSAGE=Hello from Oracle VM")
    tmp = NamedTemporaryFile("w", delete=False, encoding="utf-8")
    tmp.write("\n".join(content_lines) + "\n")
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


def deploy(target: dict, env_file: Path | None, skip_bootstrap: bool):
    host = target["host"]
    port = int(target.get("port", 22))
    user = target["user"]
    key = target.get("ssh_key")
    remote_dir = target.get("remote_dir", "/opt/flaskapp")
    project_name = target.get("project_name", "flaskapp")
    env_vars = target.get("env", {})

    app_port = int(env_vars.get("APP_PORT", 80))

    print(f"Connecting to {user}@{host}:{port} ...")
    ssh = ssh_connect(host, port, user, key)
    sftp = ssh.open_sftp()

    try:
        sftp_mkdirs(sftp, remote_dir)

        # Upload bootstrap script
        remote_bootstrap_path = posixpath.join(remote_dir, "remote_bootstrap.sh")
        sftp_put_file(sftp, Path(REMOTE_BOOTSTRAP), remote_bootstrap_path, mode=0o755)

        # Upload toplevel files
        for f in TOPLEVEL_FILES:
            lp = Path(f)
            rp = posixpath.join(remote_dir, lp.name)
            sftp_put_file(sftp, lp, rp)

        # Upload directories needed for build
        for d in DIRECTORIES:
            local_d = Path(d)
            remote_d = posixpath.join(remote_dir, d)
            try:
                sftp.stat(remote_d)
            except FileNotFoundError:
                sftp.mkdir(remote_d)
            upload_directory(sftp, local_d, remote_d)

        # Upload .env
        if env_file:
            lp_env = env_file
        else:
            lp_env = write_env_temp(env_vars)
        try:
            sftp_put_file(sftp, lp_env, posixpath.join(remote_dir, ".env"))
        finally:
            if not env_file and lp_env.exists():
                try:
                    os.remove(lp_env)
                except Exception:
                    pass

        # Bootstrap remote host (idempotent)
        if not skip_bootstrap:
            print("Running remote bootstrap (idempotent)...")
            cmd = f"sudo bash {shlex.quote(remote_bootstrap_path)} {shlex.quote(str(app_port))}"
            rc, out, err = run_cmd(ssh, cmd, get_pty=True)
            if rc != 0:
                print(out)
                print(err, file=sys.stderr)
                raise SystemExit(f"Bootstrap failed with exit code {rc}")

        # Compose up (idempotent)
        print("Building and starting services via docker compose ...")
        compose_cmd = (
            f"cd {shlex.quote(remote_dir)} && "
            f"sudo docker compose -p {shlex.quote(project_name)} up -d --build --remove-orphans"
        )
        rc, out, err = run_cmd(ssh, compose_cmd, get_pty=True)
        if rc != 0:
            print(out)
            print(err, file=sys.stderr)
            raise SystemExit(f"docker compose up failed with exit code {rc}")

        # Health check
        print("Waiting for health endpoint ...")
        health_cmd = f"timeout 30 bash -lc 'for i in $(seq 1 30); do curl -fsS http://127.0.0.1:{app_port}/healthz && exit 0; sleep 1; done; exit 1'"
        rc, out, err = run_cmd(ssh, health_cmd)
        if rc == 0:
            print("Service healthy: /healthz responded ok")
        else:
            print("Warning: health check failed; verify manually", file=sys.stderr)

        print("Deployment complete")

    finally:
        sftp.close()
        ssh.close()


def main():
    parser = argparse.ArgumentParser(description="Idempotent SSH/docker-compose deploy to Oracle VM")
    parser.add_argument("--config", default="deploy/deploy_config.example.json", help="Path to deploy config JSON")
    parser.add_argument("--target", required=True, help="Target name from config")
    parser.add_argument("--env-file", default=None, help="Path to .env file to upload (overrides config env)")
    parser.add_argument("--skip-bootstrap", action="store_true", help="Skip remote bootstrap")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    target = select_target(config, args.target)

    env_file = Path(args.env_file) if args.env_file else None
    if env_file and not env_file.exists():
        raise SystemExit(f"Env file not found: {env_file}")

    deploy(target, env_file, args.skip_bootstrap)


if __name__ == "__main__":
    main()

