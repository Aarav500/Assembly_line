import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from summarization.chunker import chunk_text
from summarization.summarizer import FrequencySummarizer

app = Flask(__name__)
summarizer = FrequencySummarizer()


def _clamp(value, min_v, max_v, default):
    try:
        v = float(value)
        return max(min_v, min(max_v, v))
    except Exception:
        return default


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/", methods=["GET"]) 
def index():
    return jsonify({
        "name": "Chunking and Summarization Pipeline",
        "endpoints": {
            "POST /summarize": {
                "body": {
                    "text": "string (required)",
                    "chunk_size": "int words, default 500",
                    "overlap": "int words, default 50",
                    "chunk_summary_ratio": "float 0-1, default 0.2",
                    "final_summary_ratio": "float 0-1, default 0.3",
                    "max_chunk_summary_sentences": "int, optional",
                    "max_final_summary_sentences": "int, optional"
                }
            }
        }
    })


@app.route("/summarize", methods=["POST"]) 
def summarize():
    if not request.is_json:
        return jsonify({"error": "Expected application/json"}), 400

    data = request.get_json(silent=True) or {}
    text = data.get("text", "")

    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Field 'text' is required and must be a non-empty string."}), 400

    # Parameters with sane defaults
    chunk_size = int(data.get("chunk_size", 500))
    overlap = int(data.get("overlap", 50))

    # clamp ratios
    chunk_summary_ratio = _clamp(data.get("chunk_summary_ratio", 0.2), 0.05, 0.9, 0.2)
    final_summary_ratio = _clamp(data.get("final_summary_ratio", 0.3), 0.05, 0.9, 0.3)

    max_chunk_summary_sentences = data.get("max_chunk_summary_sentences")
    max_final_summary_sentences = data.get("max_final_summary_sentences")

    if not isinstance(chunk_size, int) or chunk_size <= 0:
        return jsonify({"error": "chunk_size must be a positive integer"}), 400
    if not isinstance(overlap, int) or overlap < 0:
        return jsonify({"error": "overlap must be a non-negative integer"}), 400

    words = text.split()
    word_count = len(words)

    # Chunk text
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    # Summarize each chunk
    chunk_results = []
    for idx, ch in enumerate(chunks):
        ch_summary = summarizer.summarize(
            ch["text"], ratio=chunk_summary_ratio, max_sentences=max_chunk_summary_sentences
        )
        chunk_results.append({
            "index": idx,
            "start_word": ch["start_word"],
            "end_word": ch["end_word"],
            "word_count": len(ch["text"].split()),
            "summary": ch_summary,
        })

    # Combine chunk summaries then summarize again for global summary
    combined = "\n".join([c["summary"] for c in chunk_results if c["summary"].strip()]) or text
    final_summary = summarizer.summarize(
        combined,
        ratio=final_summary_ratio,
        max_sentences=max_final_summary_sentences,
    )

    response = {
        "meta": {
            "input_word_count": word_count,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "chunk_count": len(chunks),
            "chunk_summary_ratio": chunk_summary_ratio,
            "final_summary_ratio": final_summary_ratio,
        },
        "summary": final_summary,
        "chunks": chunk_results,
    }

    return jsonify(response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)



def create_app():
    return app


@app.route('/chunk', methods=['POST'])
def _auto_stub_chunk():
    return 'Auto-generated stub for /chunk', 200
