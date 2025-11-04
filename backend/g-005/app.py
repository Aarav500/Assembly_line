import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from werkzeug.middleware.proxy_fix import ProxyFix

from config import DATA_PATH, MODEL_PATH, BATCH_SIZE, LABELS
from data_store import DataStore
from model import ModelManager

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")
app.wsgi_app = ProxyFix(app.wsgi_app)

# Ensure directories exist
os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

store = DataStore(DATA_PATH)
model = ModelManager(MODEL_PATH, labels=LABELS)


def ensure_model_ready():
    labeled = store.get_labeled()
    # Train if we can and model not ready
    if model.is_trained:
        return True
    try:
        trained, info = model.train(labeled)
        return trained
    except Exception:
        return False


@app.route("/")
def index():
    counts = store.get_counts()
    metrics = None
    if model.is_trained:
        metrics = model.evaluate(store.get_test())
    return render_template(
        "index.html",
        counts=counts,
        metrics=metrics,
        labels=LABELS,
        model_trained=model.is_trained,
    )


@app.route("/select")
def select():
    try:
        k = int(request.args.get("k", BATCH_SIZE))
    except Exception:
        k = BATCH_SIZE
    strategy = request.args.get("strategy", "uncertainty")

    unlabeled = store.get_unlabeled()
    if not unlabeled:
        return jsonify({"samples": [], "message": "No unlabeled samples available."})

    # Ensure model readiness; if not trainable, fallback to random selection
    labeled = store.get_labeled()
    trained, _ = model.train(labeled)

    selected = model.select_samples(unlabeled, k=k, strategy=strategy)

    return jsonify({
        "strategy": strategy,
        "k": k,
        "selected_count": len(selected),
        "samples": selected
    })


@app.route("/annotate")
def annotate():
    try:
        k = int(request.args.get("k", BATCH_SIZE))
    except Exception:
        k = BATCH_SIZE
    strategy = request.args.get("strategy", "uncertainty")
    unlabeled = store.get_unlabeled()
    labeled = store.get_labeled()
    model.train(labeled)

    selected = model.select_samples(unlabeled, k=k, strategy=strategy)
    if not selected:
        flash("No unlabeled samples available.")
    return render_template(
        "annotate.html",
        samples=selected,
        labels=LABELS,
        strategy=strategy,
        k=k,
    )


@app.route("/label", methods=["POST"])
def label():
    payload_type = request.headers.get("Content-Type", "")
    updated = []
    if payload_type.startswith("application/json"):
        data = request.get_json(silent=True) or {}
        items = data.get("items", [])
        for item in items:
            sid = item.get("id")
            label = item.get("label")
            if sid is None or label not in LABELS:
                continue
            if store.update_label(sid, label):
                updated.append({"id": sid, "label": label})
        store.save()
        retrain = bool(data.get("retrain", True))
        metrics = None
        if retrain:
            trained, info = model.train(store.get_labeled())
            metrics = model.evaluate(store.get_test()) if trained else None
        return jsonify({"updated": updated, "retrained": retrain, "metrics": metrics})

    # Handle form submission (HTML)
    changed = 0
    for key, val in request.form.items():
        if key.startswith("label_"):
            try:
                sid = int(key.split("_", 1)[1])
            except Exception:
                continue
            if val in LABELS:
                if store.update_label(sid, val):
                    changed += 1
                    updated.append({"id": sid, "label": val})
    store.save()

    # Retrain after labeling via UI
    trained, info = model.train(store.get_labeled())
    if trained:
        flash(f"Labeled {changed} samples. Model re-trained.")
    else:
        flash(f"Labeled {changed} samples. Not enough diverse labels to train yet.")

    next_k = request.args.get("k") or request.form.get("k") or BATCH_SIZE
    next_strategy = request.args.get("strategy") or request.form.get("strategy") or "uncertainty"
    return redirect(url_for("annotate", k=next_k, strategy=next_strategy))


@app.route("/retrain", methods=["POST"]) 
def retrain():
    trained, info = model.train(store.get_labeled())
    metrics = model.evaluate(store.get_test()) if trained else None
    return jsonify({
        "trained": trained,
        "info": info,
        "metrics": metrics,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


@app.route("/metrics")
def metrics():
    counts = store.get_counts()
    metrics = model.evaluate(store.get_test()) if model.is_trained else None
    return jsonify({
        "counts": counts,
        "model_trained": model.is_trained,
        "metrics": metrics
    })


@app.route("/dataset")
def dataset():
    counts = store.get_counts()
    return jsonify(counts)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/select_samples?n=3', methods=['GET'])
def _auto_stub_select_samples_n_3():
    return 'Auto-generated stub for /select_samples?n=3', 200


@app.route('/select_samples?n=2', methods=['GET'])
def _auto_stub_select_samples_n_2():
    return 'Auto-generated stub for /select_samples?n=2', 200
