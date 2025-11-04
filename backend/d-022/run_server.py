import argparse
import os
from app import create_app


def main():
    parser = argparse.ArgumentParser(description="Run Flask app server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 5000)))
    parser.add_argument("--sandbox", action="store_true", help="Enable sandbox mode for safe testing")
    args = parser.parse_args()

    if args.sandbox:
        os.environ["SANDBOX_MODE"] = "1"

    app = create_app()
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

