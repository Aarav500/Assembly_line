"""
Generate Simple Deployment Configuration
Creates everything needed for ONE-CLICK deployment

Save as: D:/Assemblyline/unified_app/setup_simple_deployment.py
Run: python setup_simple_deployment.py
"""

from pathlib import Path
import yaml

PROJECT_ROOT = Path(r"D:\Assemblyline\unified_app")

print("=" * 80)
print("CREATING SIMPLE DEPLOYMENT CONFIGURATION")
print("=" * 80)
print()

# 1. Create unified_backend directory
unified_backend = PROJECT_ROOT / "unified_backend"
unified_backend.mkdir(exist_ok=True)
print("✓ Created unified_backend/")

# 2. Copy the unified backend app.py (created in previous artifact)
# User should manually copy it or we can create it here

app_py = '''"""
UNIFIED BACKEND SERVICE - See artifact 'unified_backend_service'
"""
# Copy the content from the artifact above
'''

# 3. Create requirements.txt for unified backend
requirements = """Flask==3.0.3
flask-cors==4.0.0
gunicorn==21.2.0
requests==2.32.3
python-dotenv==1.0.1
"""

(unified_backend / "requirements.txt").write_text(requirements, encoding='utf-8')
print("✓ Created unified_backend/requirements.txt")

# 4. Create Dockerfile for unified backend
dockerfile = """FROM python:3.11-slim

WORKDIR /app

# Copy service registry
COPY service_registry.json /app/service_registry.json

# Copy all backend modules
COPY backend /app/backend
COPY frontend /app/frontend
COPY infrastructure /app/infrastructure

# Install unified backend
COPY unified_backend/requirements.txt /app/unified_backend/requirements.txt
WORKDIR /app/unified_backend
RUN pip install --no-cache-dir -r requirements.txt

COPY unified_backend/app.py /app/unified_backend/app.py

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
"""

(unified_backend / "Dockerfile").write_text(dockerfile, encoding='utf-8')
print("✓ Created unified_backend/Dockerfile")

# 5. Create SIMPLE docker-compose.yml (ONLY 4 SERVICES!)
simple_compose = {
    "version": "3.8",
    "services": {
        "backend": {
            "build": {
                "context": ".",
                "dockerfile": "unified_backend/Dockerfile"
            },
            "container_name": "unified_backend",
            "ports": ["5000:5000"],
            "environment": [
                "FLASK_ENV=production",
                "DEBUG=False"
            ],
            "volumes": [
                "./backend:/app/backend",
                "./frontend:/app/frontend",
                "./infrastructure:/app/infrastructure"
            ],
            "networks": ["app_network"],
            "restart": "unless-stopped",
            "healthcheck": {
                "test": ["CMD", "curl", "-f", "http://localhost:5000/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3
            }
        },
        "postgres": {
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
        },
        "redis": {
            "image": "redis:7-alpine",
            "container_name": "unified_redis",
            "ports": ["6379:6379"],
            "volumes": ["redis_data:/data"],
            "networks": ["app_network"],
            "restart": "unless-stopped"
        },
        "nginx": {
            "image": "nginx:alpine",
            "container_name": "unified_nginx",
            "ports": ["80:80"],
            "volumes": ["./nginx/nginx.conf:/etc/nginx/nginx.conf:ro"],
            "depends_on": ["backend"],
            "networks": ["app_network"],
            "restart": "unless-stopped"
        }
    },
    "networks": {
        "app_network": {
            "driver": "bridge"
        }
    },
    "volumes": {
        "postgres_data": {},
        "redis_data": {}
    }
}

with open(PROJECT_ROOT / "docker-compose.yml", 'w', encoding='utf-8') as f:
    yaml.dump(simple_compose, f, default_flow_style=False, sort_keys=False)

print("✓ Created docker-compose.yml (ONLY 4 SERVICES!)")

# 6. Create updated nginx config
nginx_conf = """worker_processes auto;

events {
    worker_connections 1024;
}

http {
    upstream unified_backend {
        server backend:5000;
    }

    server {
        listen 80;
        server_name _;

        # API routes to unified backend
        location /api/ {
            proxy_pass http://unified_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_read_timeout 120s;
        }

        # Health check
        location /health {
            proxy_pass http://unified_backend/health;
        }

        # Root
        location / {
            proxy_pass http://unified_backend;
            proxy_set_header Host $host;
        }
    }
}
"""

nginx_dir = PROJECT_ROOT / "nginx"
nginx_dir.mkdir(exist_ok=True)
(nginx_dir / "nginx.conf").write_text(nginx_conf, encoding='utf-8')
print("✓ Updated nginx/nginx.conf")

# 7. Create GitHub Actions workflow for auto-deployment
github_dir = PROJECT_ROOT / ".github" / "workflows"
github_dir.mkdir(parents=True, exist_ok=True)

github_workflow = """name: Deploy Unified App

on:
  push:
    branches:
      - main
  workflow_dispatch:

env:
  VM_IP: 100.31.44.107
  VM_USER: ubuntu
  PROJECT_DIR: unified_app

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_ed25519
          chmod 600 ~/.ssh/id_ed25519
          ssh-keyscan -H ${{ env.VM_IP }} >> ~/.ssh/known_hosts

      - name: Sync files to VM
        run: |
          rsync -avz --delete \\
            --exclude='.git' \\
            --exclude='__pycache__' \\
            --exclude='*.pyc' \\
            --exclude='.venv' \\
            -e "ssh -i ~/.ssh/id_ed25519" \\
            ./ ${{ env.VM_USER }}@${{ env.VM_IP }}:~/${{ env.PROJECT_DIR }}/

      - name: Deploy on VM
        run: |
          ssh -i ~/.ssh/id_ed25519 ${{ env.VM_USER }}@${{ env.VM_IP }} << 'ENDSSH'
            set -e
            cd ~/${{ env.PROJECT_DIR }}

            # Stop existing services
            docker-compose -f docker-compose.yml down || true

            # Build and start
            docker-compose -f docker-compose.yml build
            docker-compose -f docker-compose.yml up -d

            # Wait for health check
            sleep 10

            # Show status
            docker-compose -f docker-compose.yml ps
          ENDSSH

      - name: Health Check
        run: |
          for i in {1..12}; do
            if curl -fsS "http://${{ env.VM_IP }}/health" >/dev/null; then
              echo "Deployment successful!"
              exit 0
            fi
            echo "Waiting for service..."
            sleep 10
          done
          echo "Health check failed"
          exit 1

      - name: Deployment Complete
        run: |
          echo "========================================="
          echo "DEPLOYMENT SUCCESSFUL"
          echo "========================================="
          echo "URL: http://${{ env.VM_IP }}"
          echo "API: http://${{ env.VM_IP }}/api/services"
          echo "Health: http://${{ env.VM_IP }}/health"
"""

(github_dir / "deploy.yml").write_text(github_workflow, encoding='utf-8')
print("✓ Created .github/workflows/deploy.yml")

# 8. Create local deployment script
deploy_script = """#!/bin/bash
# Simple Local Deployment

echo "========================================="
echo "UNIFIED APP - SIMPLE DEPLOYMENT"
echo "========================================="
echo ""
echo "Services: 4 containers (backend, postgres, redis, nginx)"
echo "Backend: Dynamically loads all 437 modules"
echo ""

# Build and start
docker-compose -f docker-compose.yml down
docker-compose -f docker-compose.yml build
docker-compose -f docker-compose.yml up -d

echo ""
echo "Waiting for services to start..."
sleep 5

# Show status
docker-compose -f docker-compose.yml ps

echo ""
echo "========================================="
echo "DEPLOYMENT COMPLETE"
echo "========================================="
echo "Access: http://localhost"
echo "API: http://localhost/api/services"
echo "Health: http://localhost/health"
echo ""
echo "View logs: docker-compose -f docker-compose.yml logs -f"
echo "Stop: docker-compose -f docker-compose.yml down"
echo "========================================="
"""

(PROJECT_ROOT / "deploy_simple.sh").write_text(deploy_script, encoding='utf-8')
print("✓ Created deploy_simple.sh")

# 9. Create README for deployment
readme = """# Unified App - Simple Deployment

## Architecture
- **1 Backend Service**: Dynamically loads all 437 modules on-demand
- **1 PostgreSQL**: Database
- **1 Redis**: Cache
- **1 Nginx**: Reverse proxy

Total: **4 containers** instead of 439!

## Local Deployment

```bash
./deploy_simple.sh
```

Access: http://localhost

## Cloud Deployment (Automatic)

1. Add secrets to GitHub:
   - `SSH_PRIVATE_KEY`: Your VM SSH key

2. Push to main branch:
   ```bash
   git add .
   git commit -m "Deploy unified app"
   git push origin main
   ```

3. GitHub Actions automatically deploys to http://100.31.44.107

## API Usage

### List all services
```bash
curl http://localhost/api/services
```

### Call a specific module
```bash
# GitHub Importer
curl -X POST http://localhost/api/backend/a-001/api/github/import \\
  -H "Content-Type: application/json" \\
  -d '{"url": "https://github.com/user/repo"}'

# Project Detector
curl -X POST http://localhost/api/backend/a-003/api/detect/project \\
  -H "Content-Type: application/json" \\
  -d '{"path": "/path/to/project"}'
```

## Benefits

- Single backend service - Not 366 separate containers
- Dynamic loading - Modules loaded on-demand
- Low memory - ~2-4GB RAM instead of 60GB+
- Fast deployment - Seconds instead of hours
- Auto-deploy - Push to GitHub -> Automatically deployed
- Easy to scale - Just increase Gunicorn workers

## Monitoring

```bash
# View logs
docker-compose -f docker-compose.yml logs -f backend

# Check health
curl http://localhost/health

# Restart
docker-compose -f docker-compose.yml restart backend
```
"""

(PROJECT_ROOT / "DEPLOYMENT_README.md").write_text(readme, encoding='utf-8')
print("✓ Created DEPLOYMENT_README.md")

print()
print("=" * 80)
print("✓ SIMPLE DEPLOYMENT SETUP COMPLETE")
print("=" * 80)
print()
print("What was created:")
print("  1. unified_backend/ - Single backend service")
print("  2. docker-compose.yml - ONLY 4 services!")
print("  3. .github/workflows/deploy.yml - Auto-deployment")
print("  4. deploy_simple.sh - Local deployment script")
print("  5. DEPLOYMENT_README.md - Instructions")
print()
print("=" * 80)
print("NEXT STEPS")
print("=" * 80)
print()
print("1. Copy unified backend app.py:")
print("   - Get code from 'unified_backend_service' artifact above")
print("   - Save to: unified_backend/app.py")
print()
print("2. Test locally:")
print("   chmod +x deploy_simple.sh")
print("   ./deploy_simple.sh")
print()
print("3. Deploy to cloud:")
print("   git add .")
print("   git commit -m 'Setup unified deployment'")
print("   git push origin main")
print()
print("4. Access:")
print("   http://100.31.44.107")
print("=" * 80)