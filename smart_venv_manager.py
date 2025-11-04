"""
Smart Virtual Environment Manager
Automatically creates separate venvs for conflicting dependencies
"""

import os
import sys
import json
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SmartVenvManager:
    """
    Manages multiple virtual environments based on dependency conflicts
    """

    def __init__(self, service_path: str):
        self.service_path = Path(service_path)
        self.service_name = self.service_path.name
        self.venvs_dir = self.service_path / ".venvs"
        self.venvs_dir.mkdir(exist_ok=True)

        # Track modules and their assigned venvs
        self.module_venv_map = {}  # {module_path: venv_name}
        self.venv_requirements = {}  # {venv_name: set(requirements)}
        self.venv_modules = {}  # {venv_name: [module_paths]}

        self.mapping_file = self.service_path / "venv_mapping.json"
        self.load_mapping()

    def load_mapping(self):
        """Load existing venv mappings"""
        if self.mapping_file.exists():
            with open(self.mapping_file, 'r') as f:
                data = json.load(f)
                self.module_venv_map = data.get('module_venv_map', {})
                self.venv_requirements = data.get('venv_requirements', {})
                self.venv_modules = data.get('venv_modules', {})

    def save_mapping(self):
        """Save venv mappings"""
        with open(self.mapping_file, 'w') as f:
            json.dump({
                'module_venv_map': self.module_venv_map,
                'venv_requirements': {k: list(v) for k, v in self.venv_requirements.items()},
                'venv_modules': self.venv_modules
            }, f, indent=2)

    def extract_module_requirements(self, module_path: Path) -> Set[str]:
        """Extract requirements from module imports"""
        requirements = set()

        try:
            with open(module_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all import statements
            import re
            imports = re.findall(r'^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)', content, re.MULTILINE)

            # Map to package names
            for imp in imports:
                base_package = imp.split('.')[0]
                if base_package not in ['sys', 'os', 'json', 're', 'datetime', 'time',
                                        'pathlib', 'logging', 'typing', 'collections']:
                    requirements.add(base_package)

        except Exception as e:
            logger.warning(f"Could not extract requirements from {module_path}: {e}")

        return requirements

    def check_requirements_file(self, module_path: Path) -> Set[str]:
        """Check if module has its own requirements.txt"""
        req_file = module_path.parent / f"{module_path.stem}_requirements.txt"
        if req_file.exists():
            with open(req_file, 'r') as f:
                return set(line.strip() for line in f if line.strip() and not line.startswith('#'))
        return set()

    def requirements_compatible(self, req1: Set[str], req2: Set[str]) -> bool:
        """Check if two requirement sets are compatible"""

        # Extract package names and versions
        def parse_req(req: str) -> Tuple[str, str]:
            if '==' in req:
                pkg, ver = req.split('==')
                return pkg.strip(), ver.strip()
            elif '>=' in req or '<=' in req or '>' in req or '<' in req:
                # Complex version constraint, consider incompatible for safety
                return req.split('>')[0].split('<')[0].split('=')[0].strip(), 'complex'
            return req.strip(), 'any'

        packages1 = {parse_req(r)[0]: parse_req(r) for r in req1}
        packages2 = {parse_req(r)[0]: parse_req(r) for r in req2}

        # Check for version conflicts
        for pkg in set(packages1.keys()) & set(packages2.keys()):
            _, ver1 = packages1[pkg]
            _, ver2 = packages2[pkg]

            if ver1 != 'any' and ver2 != 'any' and ver1 != ver2:
                logger.warning(f"Conflict detected: {pkg} versions {ver1} vs {ver2}")
                return False

        return True

    def find_compatible_venv(self, requirements: Set[str]) -> str:
        """Find an existing compatible venv or create new one"""
        # Try to find compatible existing venv
        for venv_name, venv_reqs in self.venv_requirements.items():
            if self.requirements_compatible(requirements, venv_reqs):
                logger.info(f"Found compatible venv: {venv_name}")
                return venv_name

        # Create new venv
        venv_name = f"venv_{len(self.venv_requirements) + 1}"
        logger.info(f"Creating new venv: {venv_name} for conflicting requirements")
        self.create_venv(venv_name, requirements)
        return venv_name

    def create_venv(self, venv_name: str, requirements: Set[str]):
        """Create a new virtual environment"""
        venv_path = self.venvs_dir / venv_name

        if not venv_path.exists():
            logger.info(f"Creating virtual environment: {venv_path}")
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)

            # Install requirements
            if requirements:
                pip_path = venv_path / 'bin' / 'pip' if os.name != 'nt' else venv_path / 'Scripts' / 'pip.exe'

                # Upgrade pip
                subprocess.run([str(pip_path), 'install', '--upgrade', 'pip'], check=True)

                # Install packages
                for req in requirements:
                    try:
                        logger.info(f"Installing {req} in {venv_name}")
                        subprocess.run([str(pip_path), 'install', req], check=True)
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to install {req}: {e}")

        self.venv_requirements[venv_name] = requirements

    def assign_module_to_venv(self, module_path: Path) -> str:
        """Assign a module to appropriate venv"""
        module_rel_path = str(module_path.relative_to(self.service_path))

        # Check if already assigned
        if module_rel_path in self.module_venv_map:
            return self.module_venv_map[module_rel_path]

        # Extract requirements
        requirements = self.extract_module_requirements(module_path)
        file_requirements = self.check_requirements_file(module_path)
        all_requirements = requirements | file_requirements

        # Find or create compatible venv
        venv_name = self.find_compatible_venv(all_requirements)

        # Update mappings
        self.module_venv_map[module_rel_path] = venv_name
        if venv_name not in self.venv_modules:
            self.venv_modules[venv_name] = []
        self.venv_modules[venv_name].append(module_rel_path)

        logger.info(f"Assigned {module_rel_path} → {venv_name}")
        return venv_name

    def process_all_modules(self):
        """Process all Python modules in the service"""
        logger.info(f"Processing modules in {self.service_path}")

        for module_path in self.service_path.rglob("*.py"):
            if module_path.name == "__init__.py" or module_path.name.startswith("test_"):
                continue

            if ".venvs" in str(module_path):
                continue

            try:
                self.assign_module_to_venv(module_path)
            except Exception as e:
                logger.error(f"Error processing {module_path}: {e}")

        self.save_mapping()
        self.generate_reports()

    def generate_reports(self):
        """Generate reports about venv structure"""
        report_path = self.service_path / "venv_report.txt"

        with open(report_path, 'w') as f:
            f.write(f"Virtual Environment Report for {self.service_name}\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"Total VEnvs Created: {len(self.venv_requirements)}\n")
            f.write(f"Total Modules: {len(self.module_venv_map)}\n\n")

            for venv_name, modules in self.venv_modules.items():
                f.write(f"\n{venv_name}:\n")
                f.write(f"  Requirements: {', '.join(self.venv_requirements.get(venv_name, []))}\n")
                f.write(f"  Modules ({len(modules)}):\n")
                for module in modules:
                    f.write(f"    - {module}\n")

        logger.info(f"Report generated: {report_path}")

    def get_module_venv_path(self, module_path: str) -> Path:
        """Get the venv path for a module"""
        venv_name = self.module_venv_map.get(module_path, 'venv_1')
        return self.venvs_dir / venv_name

    def generate_run_script(self, module_path: str, output_path: Path):
        """Generate a script to run module with correct venv"""
        venv_name = self.module_venv_map.get(module_path, 'venv_1')
        venv_path = self.venvs_dir / venv_name

        if os.name == 'nt':  # Windows
            python_path = venv_path / 'Scripts' / 'python.exe'
            script_content = f'@echo off\n"{python_path}" "{module_path}" %*\n'
            script_ext = '.bat'
        else:  # Unix
            python_path = venv_path / 'bin' / 'python'
            script_content = f'#!/bin/bash\n"{python_path}" "{module_path}" "$@"\n'
            script_ext = '.sh'

        script_path = output_path / f"run_{Path(module_path).stem}{script_ext}"
        with open(script_path, 'w') as f:
            f.write(script_content)

        if os.name != 'nt':
            os.chmod(script_path, 0o755)

        return script_path


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Smart VEnv Manager')
    parser.add_argument('service_path', help='Path to service directory (backend/frontend/infrastructure)')
    parser.add_argument('--process', action='store_true', help='Process all modules and create venvs')
    parser.add_argument('--report', action='store_true', help='Generate report only')

    args = parser.parse_args()

    manager = SmartVenvManager(args.service_path)

    if args.process:
        manager.process_all_modules()
    elif args.report:
        manager.generate_reports()
    else:
        print("Use --process to process modules or --report to generate report")


if __name__ == '__main__':
    main()