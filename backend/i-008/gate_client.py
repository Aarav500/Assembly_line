import argparse
import json
import sys
import urllib.request
import urllib.error


def load_responses(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Accept either a pure mapping or wrapper with 'responses'
    if isinstance(data, dict) and 'responses' in data and isinstance(data['responses'], dict):
        return data['responses']
    if isinstance(data, dict):
        return data
    raise ValueError('Invalid responses file format')


def post_json(url: str, payload: dict, api_key: str = None):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    if api_key:
        req.add_header('X-API-Key', api_key)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8')
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'error': 'HTTPError', 'message': str(e)}
    except urllib.error.URLError as e:
        return 0, {'error': 'URLError', 'message': str(e)}


def main():
    parser = argparse.ArgumentParser(description='Regulatory Checklist Gate Client')
    parser.add_argument('--url', required=True, help='Base URL of the API (e.g., http://localhost:5000)')
    parser.add_argument('--framework', required=True, help='Framework key (gdpr, hipaa, ccpa)')
    parser.add_argument('--region', required=True, help='Region key (e.g., eu, uk, us, us-ca)')
    parser.add_argument('--responses', required=True, help='Path to JSON file with task responses (id: boolean)')
    parser.add_argument('--api-key', default=None, help='API key if server requires it (X-API-Key)')
    parser.add_argument('--min-required-percent', type=float, default=100.0, help='Minimum percent of required tasks to pass')
    parser.add_argument('--allow-optional-incomplete', action='store_true', help='Allow optional tasks incomplete')
    args = parser.parse_args()

    responses = load_responses(args.responses)

    payload = {
        'framework': args.framework,
        'region': args.region,
        'responses': responses,
        'min_required_percent': args.min_required_percent,
        'allow_optional_incomplete': bool(args.allow_optional_incomplete)
    }

    status, body = post_json(args.url.rstrip('/') + '/api/gate', payload, api_key=args.api_key)

    print(json.dumps(body, indent=2))

    if status == 200 and body.get('status') == 'pass':
        sys.exit(0)
    else:
        # Non-pass considered failure for CI
        sys.exit(2)


if __name__ == '__main__':
    main()

