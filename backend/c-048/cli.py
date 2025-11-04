#!/usr/bin/env python3
import argparse
import datetime
import json
import sys

from app.upgrade_generator import parse_commits_from_git, generate_upgrade_notes


def main():
    parser = argparse.ArgumentParser(description='Generate upgrade notes and migration guide (Markdown).')
    parser.add_argument('--from', dest='from_ref', help='Git ref/tag/sha to start from (exclusive).')
    parser.add_argument('--to', dest='to_ref', default='HEAD', help='Git ref/tag/sha to end at (inclusive). Default: HEAD')
    parser.add_argument('--previous-version', dest='previous_version', help='Previous version, e.g., v1.2.3')
    parser.add_argument('--new-version', dest='new_version', help='New version, e.g., v2.0.0')
    parser.add_argument('--project', dest='project_name', default='YourProject', help='Project name for the header')
    parser.add_argument('--repo-url', dest='repo_url', help='Repository URL (for commit links)')
    parser.add_argument('--out', dest='out_file', help='Output file path to write Markdown to')
    parser.add_argument('--json', dest='as_json', action='store_true', help='Output JSON instead of Markdown')

    args = parser.parse_args()

    commits = parse_commits_from_git(from_ref=args.from_ref, to_ref=args.to_ref)

    context = {
        'project_name': args.project_name,
        'repo_url': args.repo_url,
        'date': datetime.date.today().isoformat(),
    }

    result = generate_upgrade_notes(
        commits=commits,
        previous_version=args.previous_version,
        new_version=args.new_version,
        context=context,
    )

    if args.as_json:
        output = json.dumps(result, indent=2)
    else:
        output = result['markdown']

    if args.out_file:
        with open(args.out_file, 'w', encoding='utf-8') as f:
            f.write(output)
    else:
        sys.stdout.write(output)


if __name__ == '__main__':
    main()

