import os
import re
from typing import Dict, Optional
import yaml

from .utils import read_text


class DockerDetector:
    def detect(self, root: str) -> dict:
        info: Dict = {
            "dockerfile": {},
            "compose": {},
        }
        dockerfile_path = self._find_dockerfile(root)
        if dockerfile_path:
            info["dockerfile"] = self._parse_dockerfile(dockerfile_path)
        compose_path = self._find_compose(root)
        if compose_path:
            compose = self._parse_compose(compose_path)
            info["compose"] = compose
        return info

    def _find_dockerfile(self, root: str) -> Optional[str]:
        # Search Dockerfile and variants
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
            for fn in filenames:
                if fn == 'Dockerfile' or fn.lower().startswith('dockerfile'):
                    return os.path.join(dirpath, fn)
        return None

    def _find_compose(self, root: str) -> Optional[str]:
        candidates = {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
            for fn in filenames:
                if fn in candidates:
                    return os.path.join(dirpath, fn)
        return None

    def _parse_dockerfile(self, path: str) -> dict:
        text = read_text(path) or ''
        base_image = None
        exposed = []
        cmd = None
        entrypoint = None
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            if s.upper().startswith('FROM '):
                base_image = s.split(' ', 1)[1].strip()
            elif s.upper().startswith('EXPOSE '):
                ports = s.split(' ', 1)[1].strip().split()
                for p in ports:
                    p = p.strip()
                    if '/' in p:
                        p = p.split('/')[0]
                    try:
                        exposed.append(int(p))
                    except ValueError:
                        pass
            elif s.upper().startswith('CMD '):
                cmd = s[4:].strip()
            elif s.upper().startswith('ENTRYPOINT '):
                entrypoint = s[len('ENTRYPOINT '):].strip()
        return {
            "path": path,
            "base_image": base_image,
            "exposed_ports": sorted(set(exposed)) if exposed else None,
            "cmd": cmd,
            "entrypoint": entrypoint,
        }

    def _parse_compose(self, path: str) -> dict:
        text = read_text(path) or ''
        try:
            data = yaml.safe_load(text) or {}
        except Exception:
            data = {}
        services = {}
        all_ports = []
        svcs = data.get('services', {}) or {}
        for name, svc in svcs.items():
            ports = svc.get('ports') or []
            parsed_ports = []
            for p in ports:
                if isinstance(p, int):
                    parsed_ports.append({"published": p, "target": p})
                    all_ports.append(p)
                elif isinstance(p, str):
                    # formats: "8000:80" or "127.0.0.1:8000:80"
                    parts = p.split(':')
                    try:
                        if len(parts) == 2:
                            published, target = int(parts[0]), int(parts[1])
                            parsed_ports.append({"published": published, "target": target})
                            all_ports.append(published)
                        elif len(parts) == 3:
                            published, target = int(parts[1]), int(parts[2])
                            parsed_ports.append({"published": published, "target": target})
                            all_ports.append(published)
                    except Exception:
                        continue
            services[name] = {
                "image": svc.get('image'),
                "build": svc.get('build'),
                "ports": parsed_ports or None,
                "environment": svc.get('environment'),
                "command": svc.get('command'),
            }
        return {
            "path": path,
            "services": services or None,
            "ports": sorted(set(all_ports)) if all_ports else None,
        }

