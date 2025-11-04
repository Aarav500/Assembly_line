import argparse
from pathlib import Path
from .generator import generate_sdks

def main():
    parser = argparse.ArgumentParser(description="Generate API client SDKs from OpenAPI spec.")
    parser.add_argument("--spec", required=True, help="Path to OpenAPI spec (YAML or JSON)")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--languages", default="python,typescript,go", help="Comma-separated list: python,typescript,go")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    out_dir = Path(args.out)
    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]

    out_dir.mkdir(parents=True, exist_ok=True)

    generate_sdks(spec_path, out_dir, languages)

if __name__ == "__main__":
    main()

