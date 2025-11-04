import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import os
from flask import Flask, jsonify, request
from safe_exec.policy import SafeExecPolicy, load_default_policy
from safe_exec.executor import SafeExecutor, ExecutionError


def create_app():
    app = Flask(__name__)

    # Logging
    log_level = os.environ.get("SAFE_EXEC_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("safe-exec")

    # Load policy and executor
    policy = load_default_policy()
    executor = SafeExecutor(logger=logger)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/allowed-commands")
    def allowed_commands():
        # Expose a redacted view of the policy (no full filesystem paths if you prefer)
        return jsonify(policy.describe())

    @app.post("/exec")
    def exec_command():
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 415
        payload = request.get_json(silent=True) or {}
        cmd = payload.get("command")
        args = payload.get("args", [])
        workdir = payload.get("working_dir")

        # Basic payload validation
        if not isinstance(cmd, str) or not cmd:
            return jsonify({"error": "Invalid 'command'"}), 400
        if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
            return jsonify({"error": "'args' must be a list of strings"}), 400
        if workdir is not None and not isinstance(workdir, str):
            return jsonify({"error": "'working_dir' must be a string if provided"}), 400

        try:
            spec = policy.validate(cmd, args, working_dir=workdir)
        except ValueError as ve:
            logger.warning("Policy validation failed: %s", ve)
            return jsonify({"error": str(ve)}), 403

        try:
            result = executor.run(
                exec_path=spec.exec_path,
                args=spec.exec_args,
                cwd=spec.working_dir,
                timeout_seconds=spec.timeout_seconds,
            )
        except ExecutionError as ee:
            logger.warning("Execution error: %s", ee)
            return jsonify({"error": ee.public_message, "details": ee.details}), ee.http_status

        response = {
            "command": cmd,
            "args": args,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "truncated": result.truncated,
            "duration_ms": result.duration_ms,
        }
        return jsonify(response)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))



@app.route('/execute', methods=['POST'])
def _auto_stub_execute():
    return 'Auto-generated stub for /execute', 200
