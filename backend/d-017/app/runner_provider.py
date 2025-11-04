import subprocess
import shlex
import uuid
from typing import Optional

class DockerRunnerProvider:
    def __init__(self, image: str, repo_owner: str, repo_name: str, scope: str = "repo", org: str = "", mount_docker_sock: bool = True, network: str = "", runner_workdir: str = "/_work"):
        self.image = image
        self.owner = repo_owner
        self.repo = repo_name
        self.scope = scope
        self.org = org
        self.mount_docker_sock = mount_docker_sock
        self.network = network
        self.runner_workdir = runner_workdir

    def _repo_url(self) -> str:
        if self.scope == "org":
            return f"https://github.com/{self.org}"
        return f"https://github.com/{self.owner}/{self.repo}"

    def provision(self, name: str, registration_token: str, labels: str) -> str:
        cmd = [
            "docker", "run", "-d", "--restart=unless-stopped",
            "--name", name,
            "-e", f"REPO_URL={self._repo_url()}",
            "-e", f"RUNNER_NAME={name}",
            "-e", f"RUNNER_TOKEN={registration_token}",
            "-e", f"LABELS={labels}",
            "-e", f"RUNNER_WORKDIR={self.runner_workdir}",
        ]
        if self.network:
            cmd += ["--network", self.network]
        if self.mount_docker_sock:
            cmd += ["-v", "/var/run/docker.sock:/var/run/docker.sock"]
        cmd.append(self.image)
        # Execute
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        container_id = out.strip()
        return container_id

    def terminate(self, name_or_id: str) -> None:
        try:
            subprocess.check_output(["docker", "rm", "-f", name_or_id], stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError:
            # Already gone
            pass


