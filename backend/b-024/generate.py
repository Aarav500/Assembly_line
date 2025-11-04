#!/usr/bin/env python3
import json
from pathlib import Path
from generator.utils import parse_entities_spec
from generator.erd import generate_mermaid_erd, generate_dot_erd
from generator.openapi import generate_openapi


def main():
    root = Path(__file__).parent
    spec_path = root / "sample" / "entities.json"
    out_dir = root / "build"
    out_dir.mkdir(parents=True, exist_ok=True)

    with spec_path.open() as f:
        spec = json.load(f)

    entities = parse_entities_spec(spec)

    mermaid = generate_mermaid_erd(entities)
    dot = generate_dot_erd(entities)
    openapi = generate_openapi(entities, title=spec.get("title", "Idea Entities API"), version=spec.get("version", "1.0.0"), base_path=spec.get("basePath", "/api"))

    (out_dir / "erd.mmd").write_text(mermaid)
    (out_dir / "erd.dot").write_text(dot)
    (out_dir / "openapi.json").write_text(json.dumps(openapi, indent=2))

    print("Generated:")
    print(f" - {out_dir / 'erd.mmd'}")
    print(f" - {out_dir / 'erd.dot'}")
    print(f" - {out_dir / 'openapi.json'}")


if __name__ == "__main__":
    main()

