# ============================================
# Infrastructure Service - Monitoring & Health Dashboard
# Multi-VEnv Support + System Monitoring
# ============================================

FROM python:3.11-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ============================================
# System Dependencies + Docker CLI
# ============================================
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    git \
    wget \
    build-essential \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Install Python packages for monitoring
# ============================================
RUN pip install --upgrade pip setuptools wheel && \
    pip install \
    flask \
    gunicorn \
    psutil \
    docker \
    requests

# ============================================
# Copy smart venv manager
# ============================================
COPY smart_venv_manager.py /app/

# ============================================
# Copy all application code
# ============================================
COPY . /app/

# ============================================
# Create directories
# ============================================
RUN mkdir -p \
    /app/.venvs \
    /app/logs \
    /app/data

# ============================================
# Process modules
# ============================================
RUN echo "=== Processing infrastructure modules ===" && \
    python smart_venv_manager.py /app --process || \
    echo "Warning: VEnv processing completed with warnings"

# ============================================
# Create comprehensive monitoring dashboard
# ============================================
RUN cat > /app/app.py << 'EOFAPP'
"""
Infrastructure Monitoring Dashboard
Real-time monitoring of all services and modules
"""
from flask import Flask, jsonify, render_template_string
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import subprocess

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Unified App - Infrastructure Dashboard</title>
    <meta http-equiv="refresh" content="60">
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            background: rgba(255,255,255,0.05);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
        }
        h1 {
            color: #4CAF50;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .vm-info {
            color: #888;
            font-size: 0.9em;
            margin-top: 10px;
        }
        .vm-info strong { color: #4CAF50; }

        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            padding: 25px;
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            transition: transform 0.2s;
        }
        .card:hover {
            transform: translateY(-5px);
            border-color: #4CAF50;
        }
        .card h3 {
            color: #888;
            font-size: 0.9em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        .card .value {
            font-size: 2.5em;
            font-weight: bold;
            color: #4CAF50;
        }

        .services-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .service-card {
            background: rgba(255,255,255,0.05);
            padding: 25px;
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .service-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .service-name {
            font-size: 1.5em;
            font-weight: bold;
        }
        .status-badge {
            padding: 6px 15px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .status-healthy { background: #4CAF50; color: white; }
        .status-error { background: #f44336; color: white; }
        .status-warning { background: #ff9800; color: white; }

        .service-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 15px;
        }
        .stat {
            text-align: center;
            padding: 10px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
        }
        .stat-label {
            color: #888;
            font-size: 0.8em;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #4CAF50;
        }

        .venv-list {
            margin-top: 15px;
            max-height: 150px;
            overflow-y: auto;
        }
        .venv-item {
            padding: 8px;
            background: rgba(255,255,255,0.03);
            border-radius: 5px;
            margin-bottom: 5px;
            font-size: 0.85em;
        }

        footer {
            text-align: center;
            color: #666;
            margin-top: 30px;
            padding: 20px;
        }
        .timestamp {
            color: #888;
            font-size: 0.9em;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .live-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #4CAF50;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🏥 Infrastructure Dashboard</h1>
            <div class="vm-info">
                <strong>VM:</strong> {{ vm_ip }} |
                <strong>Status:</strong> <span class="live-indicator"></span>Live |
                <strong>Updated:</strong> {{ timestamp }}
            </div>
        </header>

        <div class="summary">
            <div class="card">
                <h3>Services</h3>
                <div class="value">{{ services|length }}</div>
            </div>
            <div class="card">
                <h3>Total Modules</h3>
                <div class="value">{{ total_modules }}</div>
            </div>
            <div class="card">
                <h3>Total VEnvs</h3>
                <div class="value">{{ total_venvs }}</div>
            </div>
            <div class="card">
                <h3>Uptime</h3>
                <div class="value" style="font-size:1.8em;">{{ uptime }}</div>
            </div>
        </div>

        <div class="services-grid">
            {% for service in services %}
            <div class="service-card">
                <div class="service-header">
                    <div class="service-name">{{ service.name }}</div>
                    <span class="status-badge status-{{ service.status }}">
                        {{ service.status.upper() }}
                    </span>
                </div>

                <div class="service-stats">
                    <div class="stat">
                        <div class="stat-label">Modules</div>
                        <div class="stat-value">{{ service.modules }}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">VEnvs</div>
                        <div class="stat-value">{{ service.venvs }}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Port</div>
                        <div class="stat-value">{{ service.port }}</div>
                    </div>
                </div>

                <div style="margin-top:15px;">
                    <a href="{{ service.url }}" target="_blank"
                       style="color:#4CAF50;text-decoration:none;">
                        🔗 {{ service.url }}
                    </a>
                </div>

                {% if service.venv_details %}
                <div class="venv-list">
                    {% for venv, count in service.venv_details.items() %}
                    <div class="venv-item">
                        <strong>{{ venv }}:</strong> {{ count }} modules
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>

        <footer>
            <div class="timestamp">
                Auto-refresh every 60 seconds | Last update: {{ timestamp }}
            </div>
            <div style="margin-top:10px;color:#444;">
                Unified App Infrastructure v1.0
            </div>
        </footer>
    </div>
</body>
</html>
"""

def get_service_info(service_name):
    """Get detailed info about a service"""
    mapping_file = f"/app/../{service_name}/venv_mapping.json"

    info = {
        'modules': 0,
        'venvs': 0,
        'status': 'unknown',
        'venv_details': {}
    }

    if os.path.exists(mapping_file):
        try:
            with open(mapping_file) as f:
                data = json.load(f)
                info['modules'] = len(data.get('module_venv_map', {}))
                info['venvs'] = len(data.get('venv_requirements', {}))
                info['status'] = 'healthy'

                # Get venv details
                venv_modules = data.get('venv_modules', {})
                for venv_name, modules in venv_modules.items():
                    info['venv_details'][venv_name] = len(modules)
        except Exception as e:
            info['status'] = 'error'

    return info

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'infrastructure'}), 200

@app.route('/')
def dashboard():
    services = []
    total_modules = 0
    total_venvs = 0

    for svc_name, port in [('backend', 5000), ('frontend', 3000), ('infrastructure', 8080)]:
        info = get_service_info(svc_name)
        services.append({
            'name': svc_name.title(),
            'status': info['status'],
            'modules': info['modules'],
            'venvs': info['venvs'],
            'port': port,
            'url': f'http://140.245.12.100:{port}',
            'venv_details': info['venv_details']
        })
        total_modules += info['modules']
        total_venvs += info['venvs']

    return render_template_string(
        DASHBOARD_HTML,
        services=services,
        total_modules=total_modules,
        total_venvs=total_venvs,
        vm_ip='140.245.12.100',
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        uptime='Live'
    )

@app.route('/api/status')
def api_status():
    services = {}
    for svc_name in ['backend', 'frontend', 'infrastructure']:
        services[svc_name] = get_service_info(svc_name)
    return jsonify(services), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting Infrastructure Dashboard on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
EOFAPP

# ============================================
# Expose port
# ============================================
EXPOSE 8080

# ============================================
# Health check
# ============================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# ============================================
# Run
# ============================================
CMD ["python", "/app/app.py"]