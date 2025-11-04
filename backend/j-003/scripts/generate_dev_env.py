import json
import os
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]


def load_config(cfg_path: Path) -> Dict[str, Any]:
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return
    path.write_text(content, encoding="utf-8")
    print(f"Wrote {path}")


def generate_devcontainer(cfg: Dict[str, Any]) -> str:
    name = cfg.get("name", "python-flask-app")
    desc = cfg.get("description", "")
    stack = ",".join(cfg.get("stack", [])) if isinstance(cfg.get("stack"), list) else cfg.get("stack", "python")
    dc = cfg.get("devcontainer", {})
    py_ver = dc.get("pythonVersion", "3.12")
    ports = dc.get("forwardPorts", [5000])
    obj = {
        "name": name,
        "features": {
            "ghcr.io/devcontainers/features/python:1": {"version": str(py_ver)}
        },
        "remoteEnv": {
            "FLASK_APP": "wsgi:app",
            "FLASK_ENV": "development",
            "PYTHONUNBUFFERED": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        },
        "containerEnv": {
            "PROJECT_NAME": name,
            "PROJECT_DESCRIPTION": desc,
            "PROJECT_STACK": stack,
        },
        "forwardPorts": ports,
        "portsAttributes": {
            str(ports[0]): {"label": "Flask App", "onAutoForward": "notify"}
        },
        "postCreateCommand": "python -m pip install --upgrade pip && pip install -r requirements.txt -r requirements-dev.txt",
        "customizations": {
            "vscode": {
                "extensions": [
                    "ms-python.python",
                    "ms-python.vscode-pylance",
                    "ms-toolsai.jupyter",
                    "ms-azuretools.vscode-docker",
                ],
                "settings": {
                    "python.analysis.typeCheckingMode": "basic",
                    "editor.formatOnSave": True,
                    "python.formatting.provider": "black",
                },
            }
        },
    }
    return json.dumps(obj, indent=2)


def generate_vscode_launch(cfg: Dict[str, Any]) -> str:
    ports = cfg.get("devcontainer", {}).get("forwardPorts", [5000])
    obj = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "Python: Flask (module)",
                "type": "python",
                "request": "launch",
                "module": "flask",
                "justMyCode": True,
                "env": {"FLASK_APP": "wsgi:app", "FLASK_ENV": "development", "ENABLE_DEBUGPY": "0"},
                "args": ["run", "--host", "0.0.0.0", "--port", str(ports[0])],
                "jinja": True,
            },
            {
                "name": "Python: run.py (debugpy)",
                "type": "python",
                "request": "launch",
                "program": "${workspaceFolder}/run.py",
                "console": "integratedTerminal",
                "justMyCode": True,
                "env": {"ENABLE_DEBUGPY": "1", "DEBUGPY_WAIT_FOR_CLIENT": "0", "FLASK_ENV": "development"},
            },
        ],
    }
    return json.dumps(obj, indent=2)


def generate_vscode_extensions() -> str:
    obj = {
        "recommendations": [
            "ms-python.python",
            "ms-python.vscode-pylance",
            "ms-toolsai.jupyter",
            "ms-azuretools.vscode-docker",
        ]
    }
    return json.dumps(obj, indent=2)


def main(cfg_path: str = "project.config.json") -> None:
    cfg = load_config(ROOT / cfg_path)

    devcontainer_content = generate_devcontainer(cfg)
    vscode_launch_content = generate_vscode_launch(cfg)
    vscode_extensions_content = generate_vscode_extensions()

    write_if_changed(ROOT / ".devcontainer/devcontainer.json", devcontainer_content)
    write_if_changed(ROOT / ".vscode/launch.json", vscode_launch_content)
    write_if_changed(ROOT / ".vscode/extensions.json", vscode_extensions_content)


if __name__ == "__main__":
    path = os.environ.get("PROJECT_CONFIG_PATH", "project.config.json")
    main(path)

