import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import json
from flask import Flask, request, jsonify, Response
from generator.synth import SyntheticDataGenerator
from generator.privacy import apply_privacy_rules

app = Flask(__name__)

generator = SyntheticDataGenerator()

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name": "Synthetic Data Generator",
        "version": "1.0.0",
        "endpoints": {
            "POST /generate": "Generate synthetic data from schema and privacy rules"
        }
    })

@app.route("/generate", methods=["POST"])
def generate():
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    if not isinstance(payload, dict):
        return jsonify({"error": "JSON body must be an object"}), 400

    rows = payload.get("rows", 100)
    schema = payload.get("schema")
    privacy = payload.get("privacy", {})
    output_format = (payload.get("format") or "json").lower()
    seed = payload.get("seed")

    if not isinstance(rows, int) or rows <= 0:
        return jsonify({"error": "'rows' must be a positive integer"}), 400

    if not isinstance(schema, (list, tuple)) or len(schema) == 0:
        return jsonify({"error": "'schema' must be a non-empty array of column definitions"}), 400

    try:
        df, meta = generator.generate(rows=rows, schema=schema, seed=seed)
        df = apply_privacy_rules(df, privacy=privacy, schema=schema)
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as ex:
        return jsonify({"error": f"Generation failed: {ex}"}), 500

    if output_format == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return Response(buf.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition": "attachment; filename=synthetic_data.csv"
        })
    elif output_format == "jsonl":
        # JSON Lines output
        buf = io.StringIO()
        for _, row in df.iterrows():
            buf.write(json.dumps(row.to_dict(), default=str))
            buf.write("\n")
        buf.seek(0)
        return Response(buf.getvalue(), mimetype="application/x-ndjson")
    else:
        data = json.loads(df.to_json(orient="records", date_format="iso"))
        return jsonify({
            "meta": {
                **meta,
                "rows": len(data)
            },
            "data": data
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200
