import argparse
import json
from typing import Any

from .tasks import add, fetch_url, important_task


def enqueue_add(a: int, b: int) -> None:
    res = add.delay(a, b)
    print(json.dumps({"task": "add", "id": res.id}))


def enqueue_fetch(url: str) -> None:
    res = fetch_url.delay(url)
    print(json.dumps({"task": "fetch_url", "id": res.id}))


def enqueue_important(payload_json: str) -> None:
    payload: Any = json.loads(payload_json)
    res = important_task.delay(payload)
    print(json.dumps({"task": "important_task", "id": res.id}))


def main():
    parser = argparse.ArgumentParser(description="Celery background jobs enqueuer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("a", type=int)
    p_add.add_argument("b", type=int)

    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("url", type=str)

    p_imp = sub.add_parser("important")
    p_imp.add_argument("payload", type=str, help='JSON payload, e.g. "{\\"should_fail\\": false}"')

    args = parser.parse_args()

    if args.cmd == "add":
        enqueue_add(args.a, args.b)
    elif args.cmd == "fetch":
        enqueue_fetch(args.url)
    elif args.cmd == "important":
        enqueue_important(args.payload)


if __name__ == "__main__":
    main()

