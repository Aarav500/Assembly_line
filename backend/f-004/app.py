import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import uuid
import time
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

traces = {}


def get_trace_id():
    return request.headers.get('X-Trace-Id', str(uuid.uuid4()))


def get_span_id():
    return str(uuid.uuid4())


@app.route('/service-a', methods=['GET'])
def service_a():
    trace_id = get_trace_id()
    span_id = get_span_id()
    
    logger.info(f"[TraceID: {trace_id}] [SpanID: {span_id}] Service A called")
    
    traces[trace_id] = traces.get(trace_id, [])
    traces[trace_id].append({
        'service': 'service-a',
        'span_id': span_id,
        'timestamp': time.time()
    })
    
    return jsonify({
        'service': 'service-a',
        'trace_id': trace_id,
        'span_id': span_id,
        'message': 'Service A processed request'
    })


@app.route('/service-b', methods=['GET'])
def service_b():
    trace_id = get_trace_id()
    span_id = get_span_id()
    parent_span_id = request.headers.get('X-Parent-Span-Id')
    
    logger.info(f"[TraceID: {trace_id}] [SpanID: {span_id}] [ParentSpanID: {parent_span_id}] Service B called")
    
    traces[trace_id] = traces.get(trace_id, [])
    traces[trace_id].append({
        'service': 'service-b',
        'span_id': span_id,
        'parent_span_id': parent_span_id,
        'timestamp': time.time()
    })
    
    return jsonify({
        'service': 'service-b',
        'trace_id': trace_id,
        'span_id': span_id,
        'parent_span_id': parent_span_id,
        'message': 'Service B processed request'
    })


@app.route('/job', methods=['POST'])
def trigger_job():
    trace_id = get_trace_id()
    span_id = get_span_id()
    
    logger.info(f"[TraceID: {trace_id}] [SpanID: {span_id}] Job triggered")
    
    traces[trace_id] = traces.get(trace_id, [])
    traces[trace_id].append({
        'service': 'job',
        'span_id': span_id,
        'timestamp': time.time(),
        'status': 'completed'
    })
    
    return jsonify({
        'service': 'job',
        'trace_id': trace_id,
        'span_id': span_id,
        'message': 'Job completed'
    })


@app.route('/trace/<trace_id>', methods=['GET'])
def get_trace(trace_id):
    if trace_id not in traces:
        return jsonify({'error': 'Trace not found'}), 404
    
    return jsonify({
        'trace_id': trace_id,
        'spans': traces[trace_id]
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)



def create_app():
    return app
