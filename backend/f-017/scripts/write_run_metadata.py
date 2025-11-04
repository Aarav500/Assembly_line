import argparse
import json
import os
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tool', required=True, help='Tool name (k6/locust/etc)')
    parser.add_argument('--output', required=True, help='Output JSON path')
    args = parser.parse_args()

    meta = {
        'tool': args.tool,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'github': {
            'workflow': os.getenv('GITHUB_WORKFLOW'),
            'run_id': os.getenv('GITHUB_RUN_ID'),
            'run_number': os.getenv('GITHUB_RUN_NUMBER'),
            'job': os.getenv('GITHUB_JOB'),
            'sha': os.getenv('GITHUB_SHA'),
            'ref': os.getenv('GITHUB_REF'),
            'actor': os.getenv('GITHUB_ACTOR'),
            'repository': os.getenv('GITHUB_REPOSITORY'),
        }
    }

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"Wrote metadata to {args.output}")


if __name__ == '__main__':
    main()

