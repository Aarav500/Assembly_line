import os
import re
import subprocess
import datetime
from typing import List, Dict, Any

try:
    # Flask depends on Jinja2 so jinja2 will be present
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except Exception:  # pragma: no cover
    Environment = None


def _short_sha(sha: str) -> str:
    return sha[:7] if sha else ''


def parse_commits_from_git(from_ref: str = None, to_ref: str = 'HEAD') -> List[Dict[str, str]]:
    range_spec = []
    if from_ref and to_ref:
        range_spec = [f"{from_ref}..{to_ref}"]
    elif from_ref and not to_ref:
        range_spec = [from_ref]

    cmd = [
        'git', 'log', '--no-merges', '--pretty=format:%H%n%s%n%b%n==END=='
    ] + range_spec

    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.output.decode('utf-8', errors='ignore'))

    text = out.decode('utf-8', errors='ignore')
    chunks = [c.strip('\n') for c in text.split('==END==') if c.strip()]

    commits: List[Dict[str, str]] = []
    for chunk in chunks:
        lines = chunk.splitlines()
        if not lines:
            continue
        sha = lines[0].strip()
        subject = lines[1].strip() if len(lines) > 1 else ''
        body = '\n'.join(lines[2:]).strip() if len(lines) > 2 else ''
        commits.append({'hash': sha, 'subject': subject, 'body': body})

    return commits


_CONVENTIONAL_RE = re.compile(r'^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?:\s+(?P<desc>.+)$')


def _is_breaking(subject: str, body: str) -> bool:
    if not subject:
        return False
    if '!' in subject.split(':', 1)[0]:
        return True
    if 'BREAKING CHANGE' in body or 'BREAKING CHANGES' in body:
        return True
    return False


def _is_deprecated(subject: str, body: str) -> bool:
    s = (subject or '') + '\n' + (body or '')
    return bool(re.search(r'\bdeprecat', s, re.IGNORECASE))


def _extract_migration_steps(body: str) -> List[str]:
    steps: List[str] = []
    if not body:
        return steps
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().upper().startswith('MIGRATION:'):
            content = lines[i][lines[i].upper().find('MIGRATION:') + len('MIGRATION:'):].strip()
            if content:
                steps.append(content)
            i += 1
            while i < len(lines) and (lines[i].startswith('  ') or lines[i].startswith('\t') or lines[i].strip().startswith('-') or lines[i].strip().startswith('*')):
                steps.append(lines[i].strip(' \t-'))
                i += 1
            continue
        i += 1
    return [s for s in steps if s]


def _detect_dependency_change(subject: str, body: str) -> List[str]:
    candidates = []
    text = subject + '\n' + body
    for m in re.finditer(r'\bbump\s+([\w\-_./]+)\s+from\s+([\w\-_.]+)\s+to\s+([\w\-_.]+)', text, re.IGNORECASE):
        pkg, frm, to = m.group(1), m.group(2), m.group(3)
        candidates.append(f"Bump {pkg} from {frm} to {to}")
    for m in re.finditer(r'\b(update|upgrade)\s+([\w\-_./]+)\s+to\s+([\w\-_.]+)', text, re.IGNORECASE):
        pkg, to = m.group(2), m.group(3)
        candidates.append(f"Update {pkg} to {to}")
    if re.search(r'\bdeps?\b', text, re.IGNORECASE):
        candidates.append(subject.strip())
    return candidates


def _linkify(repo_url: str, sha: str) -> str:
    if not repo_url or not sha:
        return _short_sha(sha)
    base = repo_url.rstrip('/')
    return f"[{_short_sha(sha)}]({base}/commit/{sha})"


def _categorize_commits(commits: List[Dict[str, str]]) -> Dict[str, Any]:
    cats: Dict[str, Any] = {
        'breaking': [],
        'deprecations': [],
        'migrations': [],
        'dependencies': [],
        'api_changes': [],
        'features': [],
        'fixes': [],
        'perf': [],
        'refactor': [],
        'build': [],
        'ci': [],
        'docs': [],
        'tests': [],
        'style': [],
        'chore': [],
        'others': [],
    }

    for c in commits:
        subject = c.get('subject', '')
        body = c.get('body', '')
        sha = c.get('hash', '')

        m = _CONVENTIONAL_RE.match(subject)
        ctype = None
        scope = None
        desc = subject
        breaking = _is_breaking(subject, body)

        if m:
            ctype = m.group('type')
            scope = m.group('scope')
            desc = m.group('desc')

        entry = {
            'hash': sha,
            'subject': subject.strip(),
            'description': desc.strip(),
            'body': body.strip(),
            'type': ctype or 'other',
            'scope': scope,
            'breaking': breaking,
        }

        if breaking:
            cats['breaking'].append(entry)
            if scope and scope.lower() == 'api' or re.search(r'\bapi\b', subject, re.IGNORECASE):
                cats['api_changes'].append(entry)

        if _is_deprecated(subject, body):
            cats['deprecations'].append(entry)

        steps = _extract_migration_steps(body)
        if steps:
            cats['migrations'].append({'commit': entry, 'steps': steps})

        deps = _detect_dependency_change(subject, body)
        if deps:
            cats['dependencies'].extend([{'commit': entry, 'note': d} for d in deps])

        # Detailed categories
        mapping = {
            'feat': 'features',
            'fix': 'fixes',
            'perf': 'perf',
            'refactor': 'refactor',
            'build': 'build',
            'ci': 'ci',
            'docs': 'docs',
            'test': 'tests',
            'style': 'style',
            'chore': 'chore',
        }
        if ctype in mapping:
            cats[mapping[ctype]].append(entry)
        else:
            cats['others'].append(entry)

    return cats


def _counts(cats: Dict[str, Any]) -> Dict[str, int]:
    return {
        'breaking': len(cats['breaking']),
        'deprecations': len(cats['deprecations']),
        'migrations': len(cats['migrations']),
        'dependencies': len(cats['dependencies']),
        'features': len(cats['features']),
        'fixes': len(cats['fixes']),
        'perf': len(cats['perf']),
        'refactor': len(cats['refactor']),
        'build': len(cats['build']),
        'ci': len(cats['ci']),
        'docs': len(cats['docs']),
        'tests': len(cats['tests']),
        'style': len(cats['style']),
        'chore': len(cats['chore']),
        'others': len(cats['others']),
    }


def _render_markdown(payload: Dict[str, Any]) -> str:
    templates_path = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(
        loader=FileSystemLoader(templates_path),
        autoescape=select_autoescape(disabled_extensions=("md",), default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template('upgrade_notes.md.j2')
    return template.render(**payload)


def generate_upgrade_notes(commits: List[Dict[str, str]], previous_version: str = None, new_version: str = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
    context = context or {}
    cats = _categorize_commits(commits)
    counts = _counts(cats)

    payload = {
        'context': {
            'project_name': context.get('project_name', 'YourProject'),
            'repo_url': context.get('repo_url'),
            'date': context.get('date') or datetime.date.today().isoformat(),
            'previous_version': previous_version,
            'new_version': new_version,
        },
        'counts': counts,
        'categories': cats,
    }

    # Build enhanced entries with links
    repo_url = context.get('repo_url')
    for key in ['breaking', 'deprecations', 'features', 'fixes', 'perf', 'refactor', 'build', 'ci', 'docs', 'tests', 'style', 'chore', 'others']:
        for e in payload['categories'][key]:
            e['link'] = _linkify(repo_url, e.get('hash'))

    for e in payload['categories']['dependencies']:
        e['commit']['link'] = _linkify(repo_url, e['commit'].get('hash'))

    for e in payload['categories']['migrations']:
        e['commit']['link'] = _linkify(repo_url, e['commit'].get('hash'))

    for e in payload['categories']['api_changes']:
        e['link'] = _linkify(repo_url, e.get('hash'))

    markdown = _render_markdown(payload)

    return {
        'markdown': markdown,
        'counts': counts,
        'context': payload['context'],
        'categories': cats,
    }

