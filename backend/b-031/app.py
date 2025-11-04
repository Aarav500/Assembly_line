import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, render_template
from personas import generate_reactions, normalize_persona_names

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/react")
def api_react():
    # Support both JSON and form submissions
    payload = {}
    if request.is_json:
        payload = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict(flat=True)

    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({
            "error": {
                "code": "invalid_input",
                "message": "Missing required field: message"
            }
        }), 400

    personas = payload.get("personas")
    if isinstance(personas, str):
        # allow comma-separated string
        personas = [p.strip() for p in personas.split(",") if p.strip()]
    elif isinstance(personas, list):
        personas = [str(p).strip() for p in personas if str(p).strip()]

    # defaults to all if none provided
    if not personas:
        personas = ["child", "pm", "ceo"]

    tone = (payload.get("tone") or "neutral").strip().lower()
    style = (payload.get("style") or "detailed").strip().lower()

    # Optional: max_lines constraint
    try:
        max_lines = int(payload.get("max_lines")) if payload.get("max_lines") is not None else None
    except ValueError:
        return jsonify({
            "error": {
                "code": "invalid_input",
                "message": "max_lines must be an integer"
            }
        }), 400

    # Optional seed for deterministic output
    seed = payload.get("seed")

    try:
        normalized_personas = normalize_persona_names(personas)
        reactions = generate_reactions(
            message=message,
            personas=normalized_personas,
            tone=tone,
            style=style,
            max_lines=max_lines,
            seed=seed,
        )
    except ValueError as e:
        return jsonify({
            "error": {
                "code": "invalid_input",
                "message": str(e)
            }
        }), 400

    return jsonify({
        "input": {
            "message": message,
            "personas": normalized_personas,
            "tone": tone,
            "style": style,
            "max_lines": max_lines,
        },
        "reactions": reactions,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app


@app.route('/feedback', methods=['POST'])
def _auto_stub_feedback():
    return 'Auto-generated stub for /feedback', 200


@app.route('/personas', methods=['GET'])
def _auto_stub_personas():
    return 'Auto-generated stub for /personas', 200
