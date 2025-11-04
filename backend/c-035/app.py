import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import subprocess
import sys
import shlex

app = Flask(__name__)

# Whitelist of allowed commands
ALLOWED_COMMANDS = {'pytest', 'pip', 'python'}

@app.route('/')
def home():
    return jsonify({"message": "Dev Tools CLI Generator", "status": "running"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/cli/run', methods=['POST'])
def run_command():
    data = request.get_json()
    command = data.get('command', '')

    if not command:
        return jsonify({"error": "No command provided"}), 400

    # Parse command safely
    try:
        cmd_parts = shlex.split(command)
    except ValueError as e:
        return jsonify({"error": "Invalid command format"}), 400

    if not cmd_parts:
        return jsonify({"error": "No command provided"}), 400

    # Validate base command is in whitelist
    base_command = cmd_parts[0]
    if base_command not in ALLOWED_COMMANDS:
        return jsonify({"error": f"Command '{base_command}' not allowed. Allowed commands: {list(ALLOWED_COMMANDS)}"}), 403

    try:
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False  # Explicitly set shell=False for security
        )
        return jsonify({
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Command timeout"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/cli/available', methods=['GET'])
def available_commands():
    commands = [
        {"name": "pytest", "description": "Run tests"},
        {"name": "pip", "description": "Package manager"},
        {"name": "python", "description": "Python interpreter"}
    ]
    return jsonify({"commands": commands})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

def create_app():
    return app
