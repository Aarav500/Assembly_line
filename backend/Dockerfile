# ============================================
# Backend Service - Multi-VEnv Support
# Handles per-module requirements (001_requirements.txt, 002_requirements.txt, etc.)
# ============================================

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ============================================
# System Dependencies
# ============================================
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    git \
    wget \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Upgrade pip and install base tools
# ============================================
RUN pip install --upgrade pip setuptools wheel

# Install Flask for health check endpoint
RUN pip install flask gunicorn

# ============================================
# Copy smart venv manager FIRST
# ============================================
COPY smart_venv_manager.py /app/

# ============================================
# Copy all application code
# ============================================
COPY . /app/

# ============================================
# Create necessary directories
# ============================================
RUN mkdir -p \
    /app/.venvs \
    /app/logs \
    /app/data \
    /app/data/uploads \
    /app/data/temp

# ============================================
# Process modules and create virtual environments
# This scans all module directories (001, 002, etc.)
# and creates separate venvs based on their requirements
# ============================================
RUN echo "=== Processing modules and creating virtual environments ===" && \
    python smart_venv_manager.py /app --process || \
    echo "Warning: VEnv processing completed with warnings"

# ============================================
# Create module runner script
# This script automatically uses the correct venv for each module
# ============================================
RUN cat > /app/run_module.sh << 'EOFSCRIPT'
#!/bin/bash
set -e

MODULE_NAME="${1}"
shift

if [ -z "$MODULE_NAME" ]; then
    echo "Usage: run_module.sh <module_name> [script.py] [args...]"
    echo "Example: run_module.sh 001 app.py"
    exit 1
fi

# Load venv mapping
if [ -f /app/venv_mapping.json ]; then
    VENV_NAME=$(python3 -c "
import json
import sys
try:
    with open('/app/venv_mapping.json') as f:
        mapping = json.load(f)
        module_map = mapping.get('module_venv_map', {})
        venv = module_map.get('${MODULE_NAME}', 'venv_default')
        print(venv)
except Exception as e:
    print('venv_default', file=sys.stderr)
    print('venv_default')
")

    PYTHON_PATH="/app/.venvs/$VENV_NAME/bin/python"

    if [ -f "$PYTHON_PATH" ]; then
        echo "✓ Running module $MODULE_NAME with $VENV_NAME"
        cd "/app/$MODULE_NAME" 2>/dev/null || cd /app
        exec "$PYTHON_PATH" "$@"
    else
        echo "⚠ VEnv $VENV_NAME not found, using system Python"
        cd "/app/$MODULE_NAME" 2>/dev/null || cd /app
        exec python3 "$@"
    fi
else
    echo "⚠ No venv mapping found, using system Python"
    cd "/app/$MODULE_NAME" 2>/dev/null || cd /app
    exec python3 "$@"
fi
EOFSCRIPT

RUN chmod +x /app/run_module.sh

# ============================================
# Create health check endpoint
# ============================================
RUN cat > /app/health.py << 'EOFHEALTH'
"""
Backend Health Check Endpoint
Provides status of backend service and venv information
"""
from flask import Flask, jsonify
import json
import os
import sys

app = Flask(__name__)

@app.route('/')
def index():
    """Landing page to help operators find the right endpoints"""
    base_url = os.environ.get('VM_PUBLIC_IP') or 'localhost'
    return jsonify({
        'message': 'Backend control plane is running',
        'next_steps': [
            'Use /health to verify container status',
            'Use /modules to inspect per-module virtual environments',
            'Access the nginx entrypoint on http://%s/ for the dashboard/front-end' % base_url,
            'If you intended to hit the API, prefix your path with /api/ when using nginx',
        ]
    }), 200

@app.route('/health')
def health():
    """Health check endpoint"""
    venv_info = {
        'total_venvs': 0,
        'total_modules': 0,
        'venvs': {}
    }

    # Read venv mapping
    if os.path.exists('/app/venv_mapping.json'):
        try:
            with open('/app/venv_mapping.json') as f:
                data = json.load(f)
                venv_requirements = data.get('venv_requirements', {})
                venv_modules = data.get('venv_modules', {})

                venv_info['total_venvs'] = len(venv_requirements)
                venv_info['total_modules'] = len(data.get('module_venv_map', {}))

                for venv_name, modules in venv_modules.items():
                    venv_info['venvs'][venv_name] = {
                        'module_count': len(modules),
                        'modules': modules[:5]  # First 5 modules
                    }
        except Exception as e:
            venv_info['error'] = str(e)

    return jsonify({
        'status': 'healthy',
        'service': 'backend',
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'venv_info': venv_info
    }), 200

@app.route('/modules')
def list_modules():
    """List all modules and their venv assignments"""
    if os.path.exists('/app/venv_mapping.json'):
        with open('/app/venv_mapping.json') as f:
            return jsonify(json.load(f)), 200
    return jsonify({'error': 'No mapping found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
EOFHEALTH

# ============================================
# Create startup script
# ============================================
RUN cat > /app/start.sh << 'EOFSTART'
#!/bin/bash
set -e

echo "=== Backend Service Starting ==="
echo "Service: Backend"
echo "Environment: ${ENVIRONMENT:-production}"
echo "VM IP: ${VM_PUBLIC_IP:-unknown}"

# Show venv summary
if [ -f /app/venv_report.txt ]; then
    echo ""
    echo "=== Virtual Environment Summary ==="
    head -n 15 /app/venv_report.txt
fi

echo ""
echo "=== Starting Backend API ==="
exec gunicorn -b 0.0.0.0:5000 app:app --workers ${WORKERS:-2} --timeout 60 --access-logfile - --error-logfile -
EOFSTART

RUN chmod +x /app/start.sh

# ============================================
# Expose port
# ============================================
EXPOSE 5000

# ============================================
# Health check
# ============================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# ============================================
# Run
# ============================================
CMD ["/app/start.sh"]