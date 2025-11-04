import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify

from config import docs_glob, include_exts, chunk_max_chars, chunk_overlap, default_top_k, qa_tests_path
from qa_engine import QAEngine
from test_runner import QATestRunner

app = Flask(__name__)

engine = QAEngine(docs_glob=docs_glob, include_exts=include_exts, max_chars=chunk_max_chars, overlap=chunk_overlap)
engine.load()

test_runner = QATestRunner(engine=engine, tests_path=qa_tests_path)


@app.get("/health")
def health():
    return jsonify({"status": "ok", **engine.stats()})


@app.post("/qa")
def qa():
    data = request.get_json(force=True, silent=True) or {}
    question = data.get("question")
    if not question:
        return jsonify({"error": "Missing 'question'"}), 400
    top_k = data.get("top_k", default_top_k)
    result = engine.answer(question, top_k=top_k)
    return jsonify(result)


@app.post("/tests/run")
def run_tests():
    data = request.get_json(force=True, silent=True) or {}
    fail_fast = bool(data.get("fail_fast", False))
    only_ids = data.get("only", None)
    result = test_runner.run(fail_fast=fail_fast, only_ids=set(only_ids) if isinstance(only_ids, list) else None)
    status = 200 if result.get("failures", 0) == 0 else 422
    return jsonify(result), status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))



def create_app():
    return app
