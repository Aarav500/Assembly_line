import argparse
import sys
import time
from urllib import request, error


def wait_for(url: str, timeout: float, interval: float) -> bool:
    start = time.time()
    while True:
        try:
            with request.urlopen(url, timeout=5) as resp:
                if 200 <= resp.status < 300:
                    return True
        except error.URLError:
            pass
        if time.time() - start > timeout:
            return False
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Wait for URL to become healthy (2xx)")
    parser.add_argument("url")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()

    ok = wait_for(args.url, args.timeout, args.interval)
    if not ok:
        print(f"Timeout waiting for {args.url}", file=sys.stderr)
        sys.exit(1)
    print(f"{args.url} is healthy")


if __name__ == "__main__":
    main()

