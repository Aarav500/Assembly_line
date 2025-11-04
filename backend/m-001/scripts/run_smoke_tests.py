#!/usr/bin/env python3
import os
import subprocess
import sys


def main() -> int:
    base_url = os.getenv('SMOKE_BASE_URL') or os.getenv('BASE_URL') or 'http://localhost:5000'
    print(f"Using base URL: {base_url}")

    gen = subprocess.run([sys.executable, 'scripts/generate_smoke_tests.py'], check=False)
    if gen.returncode != 0:
        return gen.returncode

    cmd = [sys.executable, '-m', 'pytest', '-q', 'tests/smoke']
    return subprocess.run(cmd, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())

