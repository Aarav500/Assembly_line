import os
from typing import Dict, Optional
import configparser

from .utils import read_text, load_toml, parse_requirements_text, detect_python_imports, guess_flask_port_from_code, find_flask_entrypoint


class PythonDetector:
    def detect(self, root: str) -> dict:
        info: dict = {
            "languages": [],
            "dependencies": {"default": {}, "dev": {}},
        }

        py_files = self._has_python_files(root)
        if not py_files:
            return info
        info["languages"].append("Python")

        # Versions and dependencies from common files
        pyproject_path = self._find_file(root, "pyproject.toml")
        if pyproject_path:
            info["pyproject_path"] = pyproject_path
            self._parse_pyproject(pyproject_path, info)

        pipfile_path = self._find_file(root, "Pipfile")
        if pipfile_path:
            info["pipfile_path"] = pipfile_path
            self._parse_pipfile(pipfile_path, info)

        # requirements files
        req_paths = self._find_requirements_files(root)
        info["requirements_paths"] = req_paths
        for rp in req_paths:
            text = read_text(rp) or ""
            deps = parse_requirements_text(text)
            # heuristic: requirements-dev or -test get into dev deps
            lower = os.path.basename(rp).lower()
            if any(x in lower for x in ["dev", "test", "tests"]):
                info["dependencies"]["dev"].update(deps)
            else:
                info["dependencies"]["default"].update(deps)

        setup_cfg = self._find_file(root, "setup.cfg")
        if setup_cfg:
            self._parse_setup_cfg(setup_cfg, info)

        runtime_txt = self._find_file(root, "runtime.txt")
        if runtime_txt and not info.get("python_version"):
            rt = (read_text(runtime_txt) or "").strip()
            if rt.startswith("python-"):
                info["python_version"] = rt.split("python-", 1)[1].strip()

        dot_python_version = self._find_file(root, ".python-version")
        if dot_python_version and not info.get("python_version"):
            pv = (read_text(dot_python_version) or "").strip()
            if pv:
                info["python_version"] = pv

        # Imports
        imports = detect_python_imports(root)
        info["imports"] = imports

        # Framework detection (Flask)
        has_flask = "flask" in {k.lower() for k in info["dependencies"]["default"].keys()} or "flask" in imports
        frameworks = []
        if has_flask:
            frameworks.append("Flask")
        info["frameworks"] = frameworks

        # Entry point and port
        entry = find_flask_entrypoint(root)
        if entry:
            info["entrypoint"] = f"python {entry}"
        if has_flask:
            port = guess_flask_port_from_code(root) or 5000
            info["port"] = port
        return info

    def _has_python_files(self, root: str) -> bool:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
            for fn in filenames:
                if fn.endswith('.py'):
                    return True
        return False

    def _find_file(self, root: str, name: str) -> Optional[str]:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
            if name in filenames:
                return os.path.join(dirpath, name)
        return None

    def _find_requirements_files(self, root: str):
        paths = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
            for fn in filenames:
                if fn.lower().startswith("requirements") and fn.lower().endswith((".txt", ".in")):
                    paths.append(os.path.join(dirpath, fn))
        return sorted(paths)

    def _parse_pyproject(self, path: str, info: dict):
        text = read_text(path) or ""
        try:
            data = load_toml(text)
        except Exception:
            return
        # PEP 621
        proj = data.get("project", {})
        deps_list = proj.get("dependencies", []) or []
        opt_deps = proj.get("optional-dependencies", {}) or {}
        requires_python = proj.get("requires-python")
        if requires_python and not info.get("python_version"):
            info["python_version"] = requires_python
        for item in deps_list:
            name, spec = self._split_pep508(item)
            if name:
                info["dependencies"]["default"].setdefault(name, spec or "*")
        for group, items in opt_deps.items():
            for item in items:
                name, spec = self._split_pep508(item)
                if name:
                    info["dependencies"]["dev"].setdefault(name, spec or "*")
        # Poetry
        poetry = data.get("tool", {}).get("poetry", {})
        p_deps = poetry.get("dependencies", {})
        dev_deps = poetry.get("dev-dependencies", {})
        if isinstance(p_deps, dict):
            py_ver = p_deps.get("python")
            if py_ver and not info.get("python_version"):
                info["python_version"] = str(py_ver)
            for k, v in p_deps.items():
                if k == "python":
                    continue
                info["dependencies"]["default"].setdefault(k, self._norm_dep_value(v))
        if isinstance(dev_deps, dict):
            for k, v in dev_deps.items():
                info["dependencies"]["dev"].setdefault(k, self._norm_dep_value(v))
        # PDM
        pdm = data.get("tool", {}).get("pdm", {})
        pdm_deps = pdm.get("dependencies", [])
        for item in pdm_deps:
            name, spec = self._split_pep508(item)
            if name:
                info["dependencies"]["default"].setdefault(name, spec or "*")

    def _parse_pipfile(self, path: str, info: dict):
        text = read_text(path) or ""
        try:
            data = load_toml(text)
        except Exception:
            return
        requires = data.get("requires", {})
        if isinstance(requires, dict):
            pv = requires.get("python_version") or requires.get("python_full_version")
            if pv and not info.get("python_version"):
                info["python_version"] = str(pv)
        for section, key in (("packages", "default"), ("dev-packages", "dev")):
            pkgs = data.get(section, {})
            if isinstance(pkgs, dict):
                for name, val in pkgs.items():
                    info["dependencies"][key].setdefault(name, self._norm_dep_value(val))

    def _parse_setup_cfg(self, path: str, info: dict):
        cp = configparser.ConfigParser()
        try:
            cp.read(path)
        except Exception:
            return
        if cp.has_section("options") and cp.has_option("options", "install_requires"):
            lines = cp.get("options", "install_requires").splitlines()
            deps = parse_requirements_text("\n".join(lines))
            info["dependencies"]["default"].update(deps)
        if cp.has_section("options.extras_require"):
            for key, value in cp.items("options.extras_require"):
                deps = parse_requirements_text(value)
                info["dependencies"]["dev"].update(deps)

    def _split_pep508(self, item: str):
        # simple split on first space or semicolon
        s = item.split(';', 1)[0].strip()
        if ' ' in s:
            name, spec = s.split(' ', 1)
            return name.strip(), spec.strip()
        return s, None

    def _norm_dep_value(self, val) -> str:
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            version = val.get("version")
            if version:
                return version
            path = val.get("path")
            if path:
                return f"file://{path}"
            git = val.get("git")
            if git:
                return f"git+{git}"
        return "*"
