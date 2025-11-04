#!/usr/bin/env python3
import argparse
from app import create_app
from docgen.generator import DocGenerator


def main():
    parser = argparse.ArgumentParser(description="Generate API documentation and code samples from Flask app.")
    parser.add_argument("--base-url", default="http://localhost:5000", help="Base URL for examples")
    parser.add_argument("--out", default="docs", help="Output directory")
    args = parser.parse_args()

    app = create_app()
    gen = DocGenerator(app, base_url=args.base_url)
    gen.write_all(args.out)
    print(f"Documentation generated in {args.out}")


if __name__ == "__main__":
    main()

