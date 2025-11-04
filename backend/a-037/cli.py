import os
import sys
import json
import argparse
from utils.generator import generate_docs, slugify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    parser = argparse.ArgumentParser(description='Generate onboarding and dev guide from project JSON')
    parser.add_argument('-i', '--input', required=True, help='Path to project JSON file')
    parser.add_argument('-o', '--output', default=os.path.join(BASE_DIR, 'output'), help='Output directory (default: ./output)')
    parser.add_argument('--slug', default=None, help='Override slug for output directory')
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        project = json.load(f)

    slug = args.slug or slugify(project.get('slug') or project.get('name') or 'project')
    out_dir = os.path.join(args.output, 'projects', slug)
    os.makedirs(out_dir, exist_ok=True)

    docs = generate_docs(project)

    onboarding_path = os.path.join(out_dir, 'onboarding_checklist.md')
    dev_guide_path = os.path.join(out_dir, 'dev_environment_guide.md')

    with open(onboarding_path, 'w', encoding='utf-8') as f:
        f.write(docs['onboarding'])

    with open(dev_guide_path, 'w', encoding='utf-8') as f:
        f.write(docs['dev_guide'])

    print('Generated:')
    print('  ', onboarding_path)
    print('  ', dev_guide_path)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)

