import argparse
import os
import sys
from scaffolder.manifest_loader import load_manifest_file
from scaffolder.helm_generator import HelmGenerator
from scaffolder.k8s_generator import K8sGenerator
from scaffolder.terraform_generator import TerraformGenerator
from scaffolder.utils import ensure_dir

def main():
    parser = argparse.ArgumentParser(description='Cloud infra scaffolding generator (Terraform, Helm, K8s) from manifest')
    parser.add_argument('manifest', help='Path to manifest YAML/JSON')
    parser.add_argument('-o', '--output', default='./output', help='Output directory')
    args = parser.parse_args()

    manifest_path = args.manifest
    if not os.path.exists(manifest_path):
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    manifest = load_manifest_file(manifest_path)

    ensure_dir(args.output)
    HelmGenerator().generate(args.output, manifest)
    K8sGenerator().generate(args.output, manifest)
    TerraformGenerator().generate(args.output, manifest)

    print(f"Scaffold generated at: {args.output}")

if __name__ == '__main__':
    main()

