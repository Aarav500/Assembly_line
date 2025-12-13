"""
REAL INTEGRATION ENGINE
Actually scans your code and builds accurate integration files

Save as: D:/Assemblyline/unified_app/build_integration.py
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Set
import re
import ast

PROJECT_ROOT = Path(r"D:\Assemblyline\unified_app")


class ModuleScanner:
    """Scans actual module code to extract real information"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.backend_dir = project_root / "backend"
        self.frontend_dir = project_root / "frontend"
        self.infra_dir = project_root / "infrastructure"

    def scan_all_modules(self) -> Dict:
        """Scan all directories and extract module info"""
        print("\n" + "=" * 80)
        print("SCANNING ACTUAL CODE")
        print("=" * 80 + "\n")

        registry = {
            "backend": {},
            "frontend": {},
            "infrastructure": {}
        }

        # Scan backend
        if self.backend_dir.exists():
            registry["backend"] = self._scan_directory(self.backend_dir, "backend")

        # Scan frontend
        if self.frontend_dir.exists():
            registry["frontend"] = self._scan_directory(self.frontend_dir, "frontend")

        # Scan infrastructure
        if self.infra_dir.exists():
            registry["infrastructure"] = self._scan_directory(self.infra_dir, "infrastructure")

        return registry

    def _scan_directory(self, directory: Path, service_type: str) -> Dict:
        """Scan a directory for modules"""
        modules = {}

        for item in sorted(directory.iterdir()):
            if not item.is_dir():
                continue

            # Check if it's a module directory (has app.py)
            app_py = item / "app.py"
            if not app_py.exists():
                continue

            module_name = item.name
            print(f"  📦 Found module: {service_type}/{module_name}")

            # Extract module info
            info = self._analyze_module(item, service_type)
            modules[module_name] = info

        return modules

    def _analyze_module(self, module_path: Path, service_type: str) -> Dict:
        """Analyze a single module"""
        info = {
            "name": module_path.name,
            "path": str(module_path.relative_to(self.project_root)),
            "port": self._calculate_port(module_path.name, service_type),
            "health_endpoint": "/health",
            "api_endpoints": [],
            "dependencies": [],
            "has_dockerfile": False,
            "has_requirements": False,
            "has_tests": False,
            "description": "Auto-detected module"
        }

        # Parse app.py for endpoints
        app_py = module_path / "app.py"
        if app_py.exists():
            info["api_endpoints"] = self._extract_endpoints(app_py)

        # Parse requirements.txt
        req_file = module_path / "requirements.txt"
        if req_file.exists():
            info["has_requirements"] = True
            info["dependencies"] = self._extract_dependencies(req_file)

        # Check for Dockerfile
        dockerfile = module_path / "Dockerfile"
        if dockerfile.exists():
            info["has_dockerfile"] = True

        # Check for tests
        test_dirs = [
            module_path / "tests",
            module_path / f"tests_{module_path.name}",
            module_path / "test"
        ]
        info["has_tests"] = any(d.exists() for d in test_dirs)

        # Extract description from README if exists
        readme = module_path / "README.md"
        if readme.exists():
            desc = self._extract_description(readme)
            if desc:
                info["description"] = desc

        return info

    def _calculate_port(self, module_name: str, service_type: str) -> int:
        """Calculate port based on module name and type"""
        base_ports = {
            "backend": 5000,
            "frontend": 6000,
            "infrastructure": 7000
        }

        base = base_ports.get(service_type, 5000)

        # Extract number from module name (e.g., a-001 -> 1)
        match = re.search(r'-(\d+)$', module_name)
        if match:
            offset = int(match.group(1))
            return base + offset

        return base + 1

    def _extract_endpoints(self, app_py: Path) -> List[str]:
        """Extract Flask routes from app.py"""
        endpoints = []

        try:
            content = app_py.read_text(encoding='utf-8', errors='ignore')

            # Find @app.route decorators
            pattern = r'@app\.route\([\'"]([^\'"]+)[\'"]'
            matches = re.findall(pattern, content)
            endpoints = list(set(matches))  # Remove duplicates

        except Exception as e:
            print(f"    ⚠️ Error parsing {app_py}: {e}")

        return sorted(endpoints)

    def _extract_dependencies(self, req_file: Path) -> List[str]:
        """Extract dependencies from requirements.txt"""
        deps = []

        try:
            lines = req_file.read_text(encoding='utf-8', errors='ignore').split('\n')

            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Extract package name (before version specifier)
                pkg = re.split(r'[<>=!~\[]', line)[0].strip()
                if pkg and pkg not in ['imp', 'map', 'click']:  # Skip builtin/invalid
                    deps.append(pkg)

            # Only keep first 10 real dependencies
            deps = [d for d in deps if len(d) > 1 and not d.startswith('_')][:10]

        except Exception:
            pass

        return deps

    def _extract_description(self, readme: Path) -> str:
        """Extract description from README"""
        try:
            content = readme.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')

            for i, line in enumerate(lines):
                if '## Description' in line and i + 1 < len(lines):
                    desc = lines[i + 1].strip()
                    if desc and desc != "TODO: Add usage instructions":
                        return desc
        except:
            pass

        return None


class IntegrationGenerator:
    """Generates all integration files"""

    def __init__(self, registry: Dict, project_root: Path):
        self.registry = registry
        self.project_root = project_root

    def generate_all(self):
        """Generate all integration files"""
        print("\n" + "=" * 80)
        print("GENERATING INTEGRATION FILES")
        print("=" * 80 + "\n")

        self.generate_service_registry()
        self.generate_docker_compose()
        self.generate_orchestrator()
        self.generate_frontend_dashboard()
        self.generate_scripts()
        self.generate_nginx_config()

        print("\n" + "=" * 80)
        print("✓ ALL INTEGRATION FILES GENERATED")
        print("=" * 80 + "\n")

    def generate_service_registry(self):
        """Generate service_registry.json"""
        filepath = self.project_root / "service_registry.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.registry, f, indent=2)

        total = sum(len(v) for v in self.registry.values())
        print(f"✓ Generated service_registry.json ({total} modules)")

    def generate_docker_compose(self):
        """Generate docker-compose.simple.yml with ALL services"""
        filepath = self.project_root / "docker-compose.simple.yml"

        compose = {
            "version": "3.8",
            "services": {},
            "networks": {
                "app_network": {"driver": "bridge"}
            },
            "volumes": {
                "postgres_data": {},
                "redis_data": {}
            }
        }

        # Add all backend services
        for module_name, info in self.registry.get("backend", {}).items():
            compose["services"][module_name] = {
                "build": f"./{info['path']}",
                "container_name": f"unified_{module_name}",
                "ports": [f"{info['port']}:5000"],
                "environment": ["FLASK_ENV=production"],
                "networks": ["app_network"],
                "healthcheck": {
                    "test": ["CMD", "curl", "-f", "http://localhost:5000/health"],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3
                },
                "restart": "unless-stopped"
            }

        # Add all frontend services
        for module_name, info in self.registry.get("frontend", {}).items():
            compose["services"][module_name] = {
                "build": f"./{info['path']}",
                "container_name": f"unified_{module_name}",
                "ports": [f"{info['port']}:3000"],
                "networks": ["app_network"],
                "restart": "unless-stopped"
            }

        # Add all infrastructure services
        for module_name, info in self.registry.get("infrastructure", {}).items():
            compose["services"][module_name] = {
                "build": f"./{info['path']}",
                "container_name": f"unified_{module_name}",
                "ports": [f"{info['port']}:8080"],
                "networks": ["app_network"],
                "restart": "unless-stopped"
            }

        # Add PostgreSQL
        compose["services"]["postgres"] = {
            "image": "postgres:15-alpine",
            "container_name": "unified_postgres",
            "environment": [
                "POSTGRES_DB=unified_db",
                "POSTGRES_USER=unified_user",
                "POSTGRES_PASSWORD=unified_pass"
            ],
            "ports": ["5432:5432"],
            "volumes": ["postgres_data:/var/lib/postgresql/data"],
            "networks": ["app_network"],
            "restart": "unless-stopped"
        }

        # Add Redis
        compose["services"]["redis"] = {
            "image": "redis:7-alpine",
            "container_name": "unified_redis",
            "ports": ["6379:6379"],
            "volumes": ["redis_data:/data"],
            "networks": ["app_network"],
            "restart": "unless-stopped"
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

        print(f"✓ Generated docker-compose.simple.yml ({len(compose['services'])} services)")

    def generate_orchestrator(self):
        """Generate orchestrator service"""
        orchestrator_dir = self.project_root / "orchestrator"
        orchestrator_dir.mkdir(exist_ok=True)

        # app.py
        app_code = '''"""
Unified API Orchestrator
Routes requests to appropriate microservices
"""

import os
import json
import requests
from pathlib import Path
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load service registry
REGISTRY_PATH = Path(__file__).parent.parent / "service_registry.json"
with open(REGISTRY_PATH) as f:
    REGISTRY = json.load(f)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "orchestrator"})

@app.route('/api/services')
def list_services():
    """List all available services"""
    all_services = []
    for category, modules in REGISTRY.items():
        for module_name, info in modules.items():
            all_services.append({
                "name": module_name,
                "category": category,
                "port": info["port"],
                "endpoints": info.get("api_endpoints", [])
            })
    return jsonify({"services": all_services, "total": len(all_services)})

@app.route('/api/<category>/<module>/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_request(category, module, endpoint):
    """Proxy requests to specific module"""

    # Find module in registry
    if category not in REGISTRY or module not in REGISTRY[category]:
        return jsonify({"error": "Module not found"}), 404

    module_info = REGISTRY[category][module]
    port = module_info["port"]

    # Build target URL
    target_url = f"http://{module}:{5000}/{endpoint}"

    # Forward request
    try:
        if request.method == 'GET':
            resp = requests.get(target_url, params=request.args, timeout=30)
        elif request.method == 'POST':
            resp = requests.post(target_url, json=request.get_json(), timeout=30)
        elif request.method == 'PUT':
            resp = requests.put(target_url, json=request.get_json(), timeout=30)
        elif request.method == 'DELETE':
            resp = requests.delete(target_url, timeout=30)

        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get('Content-Type'))

    except requests.exceptions.ConnectionError:
        return jsonify({"error": f"Module {module} is not reachable"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
'''

        (orchestrator_dir / "app.py").write_text(app_code)

        # requirements.txt
        requirements = "Flask==3.0.3\nflask-cors==4.0.0\nrequests==2.32.3\ngunicorn==21.2.0\nPyYAML==6.0.1\n"
        (orchestrator_dir / "requirements.txt").write_text(requirements)

        # Dockerfile
        dockerfile = """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app:app"]
"""
        (orchestrator_dir / "Dockerfile").write_text(dockerfile)

        print("✓ Generated orchestrator/")

    def generate_frontend_dashboard(self):
        """Generate master dashboard"""
        dashboard_dir = self.project_root / "frontend" / "master-dashboard"
        dashboard_dir.mkdir(parents=True, exist_ok=True)

        # Simple Flask app serving dashboard
        app_code = '''from flask import Flask, render_template, jsonify
import json
from pathlib import Path

app = Flask(__name__)

@app.route('/')
def dashboard():
    registry_path = Path(__file__).parent.parent.parent / "service_registry.json"
    with open(registry_path) as f:
        registry = json.load(f)
    return render_template('dashboard.html', registry=registry)

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
'''

        (dashboard_dir / "app.py").write_text(app_code)

        print("✓ Generated frontend/master-dashboard/")

    def generate_scripts(self):
        """Generate management scripts"""

        # start_all.sh
        start_script = """#!/bin/bash
echo "Starting all services..."
docker-compose up --build -d
echo "All services started"
docker-compose ps
"""
        (self.project_root / "start_all.sh").write_text(start_script, encoding='utf-8')

        # stop_all.sh
        stop_script = """#!/bin/bash
echo "Stopping all services..."
docker-compose down
echo "All services stopped"
"""
        (self.project_root / "stop_all.sh").write_text(stop_script, encoding='utf-8')

        print("✓ Generated management scripts")

    def generate_nginx_config(self):
        """Generate nginx configuration"""
        nginx_config = """worker_processes auto;

events {
    worker_connections 1024;
}

http {
    upstream orchestrator {
        server orchestrator:8000;
    }

    server {
        listen 80;
        server_name _;

        location /api/ {
            proxy_pass http://orchestrator;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location / {
            proxy_pass http://orchestrator;
            proxy_set_header Host $host;
        }
    }
}
"""

        nginx_dir = self.project_root / "nginx"
        nginx_dir.mkdir(exist_ok=True)
        (nginx_dir / "nginx.conf").write_text(nginx_config)

        print("✓ Generated nginx/nginx.conf")


def main():
    """Main execution"""
    print("\n" + "=" * 80)
    print("REAL INTEGRATION ENGINE")
    print("=" * 80)

    # Scan modules
    scanner = ModuleScanner(PROJECT_ROOT)
    registry = scanner.scan_all_modules()

    # Print summary
    print("\n" + "=" * 80)
    print("SCAN SUMMARY")
    print("=" * 80)
    for category, modules in registry.items():
        print(f"  {category}: {len(modules)} modules")
    print()

    # Generate integration
    generator = IntegrationGenerator(registry, PROJECT_ROOT)
    generator.generate_all()

    print("\n" + "=" * 80)
    print("DONE! Next steps:")
    print("=" * 80)
    print("1. Review generated files")
    print("2. Run: docker-compose up --build -d")
    print("3. Access orchestrator: http://localhost:8000")
    print("4. View services: http://localhost:8000/api/services")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()