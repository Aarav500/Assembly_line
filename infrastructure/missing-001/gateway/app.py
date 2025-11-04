import os
import logging
import threading
import time
import uuid
from urllib.parse import urljoin, urlencode

import yaml
import requests
from flask import Flask, request, Response, jsonify

# Basic logging
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("gateway")

app = Flask(__name__)

# -------------------- Config and Data Structures --------------------

def load_config(path: str):
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f)
    cfg = cfg or {}
    cfg.setdefault('gateway', {})
    cfg['gateway'].setdefault('retries', 0)
    cfg['gateway'].setdefault('timeout_sec', 5)
    cfg['gateway'].setdefault('healthcheck_interval_sec', 10)
    cfg['gateway'].setdefault('request_id_header', 'X-Request-ID')
    cfg['gateway'].setdefault('trust_x_forwarded', True)
    cfg.setdefault('routes', [])
    # Normalize routes
    for r in cfg['routes']:
        r.setdefault('methods', ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
        r.setdefault('strip_path', True)
        r.setdefault('healthcheck', '/health')
        r.setdefault('request_transform', {})
        r.setdefault('response_transform', {})
        r.setdefault('upstreams', [])
        for u in r['upstreams']:
            if isinstance(u, str):
                u_d = {'url': u}
            else:
                u_d = u
            u_d.setdefault('healthy', True)
            u_d.setdefault('last_checked', 0)
            u.clear(); u.update(u_d)
    return cfg

CONFIG_PATH = os.environ.get('GATEWAY_CONFIG', os.path.join(os.path.dirname(__file__), 'config.yml'))
CONFIG = load_config(CONFIG_PATH)

# -------------------- Utilities --------------------

HOP_BY_HOP_HEADERS = {
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'transfer-encoding', 'upgrade'
}

class RoundRobin:
    def __init__(self):
        self._idx = {}
        self._lock = threading.Lock()

    def next(self, key: str, items_len: int) -> int:
        with self._lock:
            cur = self._idx.get(key, -1)
            nxt = (cur + 1) % max(1, items_len)
            self._idx[key] = nxt
            return nxt

rr = RoundRobin()

class HealthChecker(threading.Thread):
    def __init__(self, config, interval):
        super().__init__(daemon=True)
        self.config = config
        self.interval = interval
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                for route in self.config['routes']:
                    for ups in route['upstreams']:
                        url = ups['url'].rstrip('/') + route.get('healthcheck', '/health')
                        try:
                            resp = requests.get(url, timeout=2)
                            ups['healthy'] = (200 <= resp.status_code < 300)
                        except Exception:
                            ups['healthy'] = False
                        ups['last_checked'] = time.time()
            except Exception as e:
                logger.warning(f"Health check error: {e}")
            time.sleep(self.interval)

health_checker = HealthChecker(CONFIG, CONFIG['gateway']['healthcheck_interval_sec'])
health_checker.start()

# -------------------- Routing Logic --------------------

def longest_prefix_match(path: str, routes):
    # Return (route_cfg, matched_prefix)
    best = None
    best_len = -1
    for r in routes:
        p = r['route'].rstrip('/')
        if not p:
            p = '/'
        if path == p or path.startswith(p + '/'):
            if len(p) > best_len:
                best = r
                best_len = len(p)
    return best


def choose_upstream(route):
    ups_list = route['upstreams']
    n = len(ups_list)
    if n == 0:
        return None
    start_idx = rr.next(route['name'], n)
    # Iterate through all to find healthy one
    for i in range(n):
        idx = (start_idx + i) % n
        if ups_list[idx].get('healthy', True):
            return ups_list[idx]
    # If none healthy, return None
    return None

# -------------------- Transformations --------------------

def rename_fields(obj, mapping):
    if not mapping:
        return obj
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            new_k = mapping.get(k, k)
            new_obj[new_k] = v
        return new_obj
    if isinstance(obj, list):
        return [rename_fields(x, mapping) if isinstance(x, (dict, list)) else x for x in obj]
    return obj


def apply_request_transform(route_cfg, method, headers, body, content_type):
    tcfg = route_cfg.get('request_transform', {}) or {}
    # Add headers
    add_headers = tcfg.get('add_headers', {}) or {}
    for hk, hv in add_headers.items():
        headers[hk] = hv

    # JSON transforms
    if content_type and 'application/json' in content_type.lower():
        try:
            import json
            data = json.loads(body.decode('utf-8') if isinstance(body, (bytes, bytearray)) else body)
            rename_map_all = (tcfg.get('json_rename_fields') or {}).get('*', {})
            rename_map_method = (tcfg.get('json_rename_fields') or {}).get(method, {})
            if rename_map_all:
                data = rename_fields(data, rename_map_all)
            if rename_map_method:
                data = rename_fields(data, rename_map_method)
            body = json.dumps(data).encode('utf-8')
        except Exception:
            pass
    return headers, body


def apply_response_transform(route_cfg, method, resp):
    tcfg = route_cfg.get('response_transform', {}) or {}
    content_type = resp.headers.get('Content-Type', '')
    if 'application/json' in content_type.lower():
        try:
            data = resp.json()
            rename_map_all = (tcfg.get('json_rename_fields') or {}).get('*', {})
            rename_map_method = (tcfg.get('json_rename_fields') or {}).get(method, {})
            if rename_map_all:
                data = rename_fields(data, rename_map_all)
            if rename_map_method:
                data = rename_fields(data, rename_map_method)
            import json
            new_body = json.dumps(data).encode('utf-8')
            # Replace body and adjust content-length
            headers = dict(resp.headers)
            headers['Content-Length'] = str(len(new_body))
            return Response(new_body, status=resp.status_code, headers=filter_response_headers(headers))
        except Exception:
            return Response(resp.content, status=resp.status_code, headers=filter_response_headers(resp.headers))
    return Response(resp.content, status=resp.status_code, headers=filter_response_headers(resp.headers))

# -------------------- Helpers --------------------

def gen_request_id():
    return str(uuid.uuid4())


def filter_request_headers(in_headers):
    out = {}
    for k, v in in_headers.items():
        if k.lower() not in HOP_BY_HOP_HEADERS and k.lower() != 'host':
            out[k] = v
    return out


def filter_response_headers(in_headers):
    out = {}
    for k, v in in_headers.items():
        if k.lower() not in HOP_BY_HOP_HEADERS:
            out[k] = v
    return out

# -------------------- Flask Routes --------------------

@app.before_request
def inject_request_id():
    rid_header = CONFIG['gateway'].get('request_id_header', 'X-Request-ID')
    rid = request.headers.get(rid_header) or gen_request_id()
    request.environ['request_id'] = rid

@app.after_request
def add_response_id(resp):
    resp.headers[CONFIG['gateway'].get('request_id_header', 'X-Request-ID')] = request.environ.get('request_id')
    return resp

@app.route('/__gateway/health', methods=['GET'])
def gw_health():
    return jsonify({
        'status': 'ok',
        'routes': [
            {
                'name': r['name'],
                'route': r['route'],
                'upstreams': r['upstreams']
            } for r in CONFIG['routes']
        ]
    })

@app.route('/__gateway/routes', methods=['GET'])
def gw_routes():
    return jsonify(CONFIG['routes'])

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
def handle_all(path):
    incoming_path = '/' + path if not path.startswith('/') else path

    route_cfg = longest_prefix_match(incoming_path, CONFIG['routes'])
    if not route_cfg:
        return jsonify({'error': 'not_found', 'message': 'No route matched', 'path': incoming_path}), 404

    if request.method == 'OPTIONS':
        # Simple CORS preflight support
        resp = Response(status=204)
        resp.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        resp.headers['Access-Control-Allow-Methods'] = ','.join(route_cfg.get('methods', []))
        resp.headers['Access-Control-Allow-Headers'] = request.headers.get('Access-Control-Request-Headers', '*')
        return resp

    if route_cfg.get('methods') and request.method not in route_cfg['methods']:
        return jsonify({'error': 'method_not_allowed', 'message': 'Method not allowed'}), 405

    # Compute upstream path
    matched_prefix = route_cfg['route'].rstrip('/')
    if matched_prefix == '':
        matched_prefix = '/'
    remainder = incoming_path[len(matched_prefix):]
    if not remainder:
        remainder = '/'
    # Strip if configured
    if route_cfg.get('strip_path', True):
        upstream_path = remainder
    else:
        upstream_path = incoming_path

    # Choose upstream
    upstream = choose_upstream(route_cfg)
    if not upstream:
        return jsonify({'error': 'service_unavailable', 'message': 'No healthy upstream available'}), 503

    base = upstream['url']
    # Ensure single slash join
    if not base.endswith('/') and not upstream_path.startswith('/'):
        target_url = base + '/' + upstream_path
    elif base.endswith('/') and upstream_path.startswith('/'):
        target_url = base[:-1] + upstream_path
    else:
        target_url = base + upstream_path

    # Query string
    if request.query_string:
        target_url = target_url + ('&' if '?' in target_url else '?') + request.query_string.decode('utf-8')

    # Prepare headers and body
    out_headers = filter_request_headers(request.headers)
    out_headers[CONFIG['gateway']['request_id_header']] = request.environ.get('request_id')
    if CONFIG['gateway'].get('trust_x_forwarded', True):
        out_headers['X-Forwarded-For'] = request.headers.get('X-Forwarded-For', request.remote_addr or '')
        out_headers['X-Forwarded-Proto'] = request.headers.get('X-Forwarded-Proto', request.scheme)
    body = request.get_data()
    content_type = request.headers.get('Content-Type', '')

    # Apply request transformations
    out_headers, body = apply_request_transform(route_cfg, request.method, out_headers, body, content_type)

    timeout = CONFIG['gateway'].get('timeout_sec', 5)
    retries = CONFIG['gateway'].get('retries', 0)

    method = request.method.lower()
    func = getattr(requests, method)

    attempt = 0
    last_exc = None
    while attempt <= retries:
        try:
            resp = func(target_url, headers=out_headers, data=body, timeout=timeout, allow_redirects=False)
            # Forward response with transformation
            return apply_response_transform(route_cfg, request.method, resp)
        except requests.RequestException as e:
            logger.warning(f"Upstream request failed (attempt {attempt+1}/{retries+1}) to {target_url}: {e}")
            last_exc = e
            # Try next healthy upstream on retry
            attempt += 1
            if attempt <= retries:
                candidate = choose_upstream(route_cfg)
                if candidate and candidate is not upstream:
                    upstream = candidate
                    base = upstream['url']
                    if not base.endswith('/') and not upstream_path.startswith('/'):
                        target_url = base + '/' + upstream_path
                    elif base.endswith('/') and upstream_path.startswith('/'):
                        target_url = base[:-1] + upstream_path
                    else:
                        target_url = base + upstream_path
                    if request.query_string:
                        target_url = target_url + ('&' if '?' in target_url else '?') + request.query_string.decode('utf-8')
                continue
    # If we reached here, all retries failed
    return jsonify({'error': 'bad_gateway', 'message': 'Upstream request failed', 'details': str(last_exc)}), 502


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

