import os
import re
from datetime import datetime, timezone
from typing import Dict, Optional

from .utils import read_text


class GenericDetector:
    @staticmethod
    def now_iso():
        return datetime.now(timezone.utc).isoformat()

    def detect(self, root: str) -> dict:
        info: Dict = {}
        try:
            readme_path = self._find_readme(root)
            if readme_path:
                info["readme_path"] = readme_path
                title, desc = self._parse_readme(readme_path)
                info["project_name"] = title
                info["description"] = desc
        except Exception as e:
            info["readme_error"] = str(e)
        
        try:
            license_path = self._find_license(root)
            if license_path:
                info["license_path"] = license_path
                info["license"] = self._detect_license(license_path)
        except Exception as e:
            info["license_error"] = str(e)
        
        try:
            env_path = self._find_env(root)
            if env_path:
                info["env_path"] = env_path
                info["env"] = self._parse_env(env_path)
        except Exception as e:
            info["env_error"] = str(e)
        
        try:
            tests = self._detect_tests(root)
            if tests:
                info["tests"] = tests
        except Exception as e:
            info["tests_error"] = str(e)
        
        # languages/frameworks may be augmented by specific detectors
        info["languages"] = []
        info["frameworks"] = []
        return info

    def _find_readme(self, root: str) -> Optional[str]:
        try:
            names = ["README.md", "Readme.md", "readme.md", "README.rst", "README.txt", "readme.txt"]
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
                for n in names:
                    if n in filenames:
                        return os.path.join(dirpath, n)
        except Exception:
            pass
        return None

    def _parse_readme(self, path: str):
        try:
            text = read_text(path) or ''
            title = None
            desc = None
            for line in text.splitlines():
                if not title:
                    if line.strip().startswith('# '):
                        title = line.strip().lstrip('#').strip()
                        continue
                if title and line.strip():
                    desc = line.strip()
                    break
            if not title:
                title = os.path.basename(os.path.dirname(path))
            return title, desc
        except Exception:
            return os.path.basename(os.path.dirname(path)), None

    def _find_license(self, root: str) -> Optional[str]:
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
                for fn in filenames:
                    if fn.upper().startswith("LICENSE") or fn.upper().startswith("COPYING"):
                        return os.path.join(dirpath, fn)
        except Exception:
            pass
        return None

    def _detect_license(self, path: str) -> Optional[str]:
        try:
            text = (read_text(path) or '').lower()
            if 'mit license' in text or 'permission is hereby granted, free of charge' in text:
                return 'MIT'
            if 'apache license' in text and 'version 2.0' in text:
                return 'Apache-2.0'
            if 'gnu general public license' in text and 'version 3' in text:
                return 'GPL-3.0'
            if 'gnu general public license' in text and 'version 2' in text:
                return 'GPL-2.0'
            if 'bsd' in text and '3-clause' in text:
                return 'BSD-3-Clause'
            if 'bsd' in text and '2-clause' in text:
                return 'BSD-2-Clause'
        except Exception:
            pass
        return None

    def _find_env(self, root: str) -> Optional[str]:
        try:
            names = [".env", ".env.example", ".env.sample"]
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
                for n in names:
                    if n in filenames:
                        return os.path.join(dirpath, n)
        except Exception:
            pass
        return None

    def _parse_env(self, path: str) -> dict:
        try:
            text = read_text(path) or ''
            env_vars = {}
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, _, value = line.partition('=')
                    env_vars[key.strip()] = value.strip()
            return env_vars
        except Exception:
            return {}

    def _detect_tests(self, root: str) -> Optional[dict]:
        try:
            test_dirs = []
            test_files = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "venv", ".venv", "__pycache__"}]
                if any(d in ['test', 'tests', '__tests__', 'spec'] for d in os.path.basename(dirpath).split()):
                    test_dirs.append(dirpath)
                for fn in filenames:
                    if fn.startswith('test_') or fn.endswith('_test.py') or fn.endswith('.test.js') or fn.endswith('.spec.js'):
                        test_files.append(os.path.join(dirpath, fn))
            if test_dirs or test_files:
                return {"test_dirs": test_dirs, "test_files": test_files}
        except Exception:
            pass
        return None