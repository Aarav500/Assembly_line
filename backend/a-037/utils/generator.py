import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates', 'docs')

def slugify(text):
    if not text:
        return 'project'
    text = text.strip().lower()
    allowed = 'abcdefghijklmnopqrstuvwxyz0123456789-'
    result = []
    prev_dash = False
    for ch in text:
        if ch.isalnum():
            result.append(ch)
            prev_dash = False
        else:
            if not prev_dash:
                result.append('-')
                prev_dash = True
    s = ''.join(result).strip('-')
    return s or 'project'


def _env():
    env = Environment(
        loader=FileSystemLoader(DOC_TEMPLATES_DIR),
        autoescape=select_autoescape(['html', 'xml'])
    )
    env.filters['datefmt'] = lambda d, fmt='%Y-%m-%d': d.strftime(fmt)
    env.filters['code'] = lambda s: f'`{s}`' if s else ''
    env.globals['now'] = datetime.utcnow
    return env


def _ensure_defaults(project):
    p = dict(project)
    p.setdefault('name', 'Unnamed Project')
    p.setdefault('description', '')
    p.setdefault('repositories', [])
    p.setdefault('programming_languages', [])
    p.setdefault('frameworks', [])
    p.setdefault('package_managers', [])
    p.setdefault('runtimes', [])
    p.setdefault('tooling', {})
    p['tooling'].setdefault('ide', [])
    p['tooling'].setdefault('plugins', [])
    p['tooling'].setdefault('cli_tools', [])
    p.setdefault('services', [])
    p.setdefault('databases', [])
    p.setdefault('environment_variables', [])
    p.setdefault('secrets', [])
    p.setdefault('access', [])
    p.setdefault('ci_cd', {})
    p['ci_cd'].setdefault('provider', '')
    p['ci_cd'].setdefault('pipelines', [])
    p.setdefault('code_style', {})
    p['code_style'].setdefault('formatter', '')
    p['code_style'].setdefault('linter', '')
    p['code_style'].setdefault('style_guide', '')
    p['code_style'].setdefault('pre_commit', False)
    p.setdefault('testing', {})
    p['testing'].setdefault('frameworks', [])
    p['testing'].setdefault('commands', [])
    p.setdefault('commands', {})
    p['commands'].setdefault('setup', [])
    p['commands'].setdefault('bootstrap', [])
    p['commands'].setdefault('start', [])
    p['commands'].setdefault('test', [])
    p['commands'].setdefault('lint', [])
    p['commands'].setdefault('migrate', [])
    p['commands'].setdefault('seed', [])
    p.setdefault('os_instructions', [])
    p.setdefault('practices', {})
    p['practices'].setdefault('branching_model', '')
    p['practices'].setdefault('commit_conventions', '')
    p['practices'].setdefault('code_review', '')
    p.setdefault('contacts', [])
    p.setdefault('day_one_tasks', [])
    p.setdefault('first_week_tasks', [])
    p.setdefault('security_training', [])
    p.setdefault('additional_notes', '')

    # Derive some helpful fields
    languages_lower = [x.lower() for x in p.get('programming_languages', [])]
    p['is_python'] = 'python' in languages_lower
    frameworks_lower = [x.lower() for x in p.get('frameworks', [])]
    p['is_flask'] = 'flask' in frameworks_lower

    # Precompute a baseline setup checklist
    p.setdefault('derived', {})
    setup_steps = []
    if p['is_python']:
        setup_steps.extend([
            'Install Python 3.11+ and ensure python3/pip are on PATH',
            'Create and activate a virtual environment',
            'Install dependencies: pip install -r requirements.txt'
        ])
        if p['code_style'].get('pre_commit'):
            setup_steps.append('Install pre-commit hooks: pre-commit install')
    if p['repositories']:
        setup_steps.insert(0, 'Clone repositories and configure remotes')
    p['derived']['baseline_setup_steps'] = setup_steps

    verification_steps = []
    if p['commands'].get('test'):
        verification_steps.append('Run test suite to confirm environment is healthy')
    if p['commands'].get('start'):
        verification_steps.append('Start the application and hit health endpoint')
    p['derived']['verification_steps'] = verification_steps

    return p


def generate_docs(project):
    p = _ensure_defaults(project)
    env = _env()
    onboarding_tpl = env.get_template('onboarding_checklist.md.j2')
    dev_tpl = env.get_template('dev_environment_guide.md.j2')
    context = {
        'project': p,
        'generated_at': datetime.utcnow()
    }
    onboarding = onboarding_tpl.render(**context)
    dev_guide = dev_tpl.render(**context)
    return {
        'onboarding': onboarding,
        'dev_guide': dev_guide
    }


def default_project_template():
    return {
        "name": "Sample Project",
        "slug": "sample-project",
        "description": "A web service that demonstrates onboarding automation.",
        "repositories": [
            {"name": "app", "url": "https://github.com/org/sample-project"}
        ],
        "programming_languages": ["Python"],
        "frameworks": ["Flask"],
        "package_managers": ["pip"],
        "runtimes": ["Python 3.11"],
        "tooling": {
            "ide": ["VS Code"],
            "plugins": ["Python", "EditorConfig"],
            "cli_tools": ["git", "make", "pre-commit"]
        },
        "services": [
            {"name": "Auth0", "type": "Auth", "url": "https://auth0.com", "notes": "Staging tenant"}
        ],
        "databases": [
            {"name": "Main DB", "type": "PostgreSQL", "version": "14", "host": "localhost", "port": 5432}
        ],
        "environment_variables": [
            {"key": "FLASK_ENV", "value": "development", "description": "Flask environment", "required": True},
            {"key": "DATABASE_URL", "value": "postgresql://user:pass@localhost:5432/app", "description": "Postgres connection string", "required": True}
        ],
        "secrets": [
            {"name": "Auth0 Client Secret", "where": "1Password vault: Team/App", "how_to_request": "Ask Platform team in #platform"}
        ],
        "access": [
            {"system": "GitHub", "role": "Member", "how_to_request": "Open IT ticket"},
            {"system": "CI/CD", "role": "Developer", "how_to_request": "Request via #devops"}
        ],
        "ci_cd": {"provider": "GitHub Actions", "pipelines": ["lint", "test", "deploy-staging"]},
        "code_style": {"formatter": "black", "linter": "ruff", "style_guide": "PEP8", "pre_commit": True},
        "testing": {"frameworks": ["pytest"], "commands": ["pytest -q"]},
        "commands": {
            "setup": ["python -m venv .venv", ". .venv/bin/activate", "pip install -U pip", "pip install -r requirements.txt"],
            "start": ["flask --app app.py run"],
            "test": ["pytest -q"],
            "lint": ["ruff check .", "black --check ."],
            "migrate": ["alembic upgrade head"]
        },
        "os_instructions": [
            {"os": "macOS", "steps": ["brew install python@3.11", "brew install postgresql@14"]},
            {"os": "Ubuntu", "steps": ["sudo apt update", "sudo apt install python3.11 python3.11-venv postgresql"]},
            {"os": "Windows", "steps": ["Install Python 3.11 from python.org", "Install WSL2 (optional)"]}
        ],
        "practices": {"branching_model": "Trunk-based with short-lived feature branches", "commit_conventions": "Conventional Commits", "code_review": "At least 1 approval"},
        "contacts": [
            {"name": "Alice", "role": "Tech Lead", "contact": "@alice"},
            {"name": "Bob", "role": "Product Manager", "contact": "@bob"}
        ],
        "day_one_tasks": [
            "Meet the team and your onboarding buddy",
            "Set up development environment",
            "Run the app locally"
        ],
        "first_week_tasks": [
            "Ship your first PR",
            "Read architecture docs",
            "Join on-call shadow (if applicable)"
        ],
        "security_training": ["Complete security awareness module"],
        "additional_notes": "Welcome! Reach out in #project-sample for help."
    }

