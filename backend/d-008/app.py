import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import subprocess
import json
import os

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"message": "Vulnerability Scanning API", "endpoints": ["/scan/trivy", "/scan/snyk", "/scan/combined"]})

@app.route('/scan/trivy', methods=['POST'])
def scan_trivy():
    data = request.get_json()
    target = data.get('target', '.')
    
    try:
        result = subprocess.run(
            ['trivy', 'fs', '--format', 'json', target],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            vulnerabilities = json.loads(result.stdout)
            mitigation = generate_mitigation(vulnerabilities, 'trivy')
            return jsonify({"scanner": "trivy", "vulnerabilities": vulnerabilities, "mitigation": mitigation})
        else:
            return jsonify({"error": "Trivy scan failed", "details": result.stderr}), 500
    except FileNotFoundError:
        return jsonify({"error": "Trivy not installed"}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Scan timeout"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/scan/snyk', methods=['POST'])
def scan_snyk():
    data = request.get_json()
    target = data.get('target', '.')
    
    try:
        result = subprocess.run(
            ['snyk', 'test', '--json', target],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        vulnerabilities = json.loads(result.stdout)
        mitigation = generate_mitigation(vulnerabilities, 'snyk')
        return jsonify({"scanner": "snyk", "vulnerabilities": vulnerabilities, "mitigation": mitigation})
    except FileNotFoundError:
        return jsonify({"error": "Snyk not installed"}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Scan timeout"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/scan/combined', methods=['POST'])
def scan_combined():
    data = request.get_json()
    target = data.get('target', '.')
    results = {"target": target, "scans": {}}
    
    # Run Trivy
    try:
        trivy_result = subprocess.run(
            ['trivy', 'fs', '--format', 'json', target],
            capture_output=True,
            text=True,
            timeout=60
        )
        if trivy_result.returncode == 0:
            results["scans"]["trivy"] = json.loads(trivy_result.stdout)
    except:
        results["scans"]["trivy"] = {"error": "Scan failed"}
    
    # Run Snyk
    try:
        snyk_result = subprocess.run(
            ['snyk', 'test', '--json', target],
            capture_output=True,
            text=True,
            timeout=60
        )
        results["scans"]["snyk"] = json.loads(snyk_result.stdout)
    except:
        results["scans"]["snyk"] = {"error": "Scan failed"}
    
    results["mitigation"] = generate_combined_mitigation(results["scans"])
    return jsonify(results)

def generate_mitigation(vulnerabilities, scanner):
    suggestions = []
    
    if scanner == 'trivy':
        if isinstance(vulnerabilities, dict) and 'Results' in vulnerabilities:
            for result in vulnerabilities.get('Results', []):
                for vuln in result.get('Vulnerabilities', []):
                    if 'FixedVersion' in vuln and vuln['FixedVersion']:
                        suggestions.append({
                            "package": vuln.get('PkgName'),
                            "current_version": vuln.get('InstalledVersion'),
                            "fixed_version": vuln.get('FixedVersion'),
                            "severity": vuln.get('Severity'),
                            "action": f"Update {vuln.get('PkgName')} to {vuln.get('FixedVersion')}"
                        })
    elif scanner == 'snyk':
        if isinstance(vulnerabilities, dict) and 'vulnerabilities' in vulnerabilities:
            for vuln in vulnerabilities.get('vulnerabilities', []):
                if 'upgradePath' in vuln:
                    suggestions.append({
                        "package": vuln.get('packageName'),
                        "severity": vuln.get('severity'),
                        "action": f"Apply upgrade path: {vuln.get('upgradePath')}"
                    })
    
    return suggestions if suggestions else [{"action": "No automated fixes available. Review vulnerabilities manually."}]

def generate_combined_mitigation(scans):
    all_suggestions = []
    
    for scanner, data in scans.items():
        if 'error' not in data:
            mitigations = generate_mitigation(data, scanner)
            all_suggestions.extend(mitigations)
    
    return all_suggestions if all_suggestions else [{"action": "No vulnerabilities found or no fixes available."}]

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def create_app():
    return app
