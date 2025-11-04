import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import re
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB
app.config['UPLOAD_EXTENSIONS'] = ['.py', '.js', '.ts', '.md', '.txt', '.json', '.yml', '.yaml']
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key')


def summarize_text(text, max_len=160):
    s = re.sub(r"\s+", " ", text or "").strip()
    return (s[: max_len - 1] + "…") if len(s) > max_len else s


def extract_title_from_idea(idea: str) -> str:
    idea = (idea or '').strip()
    if not idea:
        return 'New Product Idea'
    # Try first header-like line
    for line in idea.splitlines():
        t = line.strip()
        if not t:
            continue
        if t.lower().startswith(('title:', '#', '##', '###')):
            t = re.sub(r'^(title:|#+)\s*', '', t, flags=re.I).strip()
            if t:
                return t[:80]
        # If line is short enough and likely a title
        if 4 <= len(t) <= 80 and t.endswith('.') is False:
            return t
    # Fallback: first sentence
    m = re.split(r'[\.!?]', idea)
    if m and m[0].strip():
        return m[0].strip()[:80]
    return summarize_text(idea, 80)


def infer_target_users(idea: str):
    users = []
    # Look for phrases like "for X", "helping X"
    for m in re.finditer(r"\bfor\s+([A-Za-z0-9\-\s]+?)(?:\.|,|;|$)", idea, flags=re.I):
        candidate = m.group(1).strip()
        if 2 <= len(candidate) <= 60:
            users.append(candidate)
    for m in re.finditer(r"\bhelp(?:s|ing)?\s+([A-Za-z0-9\-\s]+?)\s+(?:to|with)\b", idea, flags=re.I):
        candidate = m.group(1).strip()
        if 2 <= len(candidate) <= 60:
            users.append(candidate)
    # Clean and unique
    cleaned = []
    seen = set()
    for u in users:
        u = re.sub(r"\s+", " ", u)
        if u.lower() not in seen:
            cleaned.append(u)
            seen.add(u.lower())
    if not cleaned:
        cleaned = ["Early adopters in your target niche", "Internal stakeholders"]
    return cleaned[:3]


def generate_user_stories(title: str, users):
    base = []
    for u in users[:2]:
        base.append(f"As a {u}, I want to quickly experience the core value of {title} so that I can decide if it fits my needs.")
    base += [
        f"As a new user, I want an onboarding flow for {title} so that I can get value in minutes.",
        f"As a power user, I want configurable settings in {title} so that I can tailor it to my workflow.",
    ]
    return base[:5]


def generate_acceptance_criteria(title: str):
    return [
        f"A user can complete the primary task of {title} within 3 clicks or under 60 seconds.",
        "All critical paths have tests with >= 80% coverage.",
        "Core pages load under 2 seconds on a 3G connection.",
        "Upsell/activation event is tracked with analytics.",
    ]


def generate_architecture_suggestion(title: str):
    return [
        "Frontend: SPA or SSR (e.g., React/Vue/Svelte) with design system.",
        "Backend: REST/GraphQL with auth, rate limiting, and logging.",
        "Data: Postgres for transactional data, Redis for caching.",
        "CI/CD: Lint, tests, build, containerize, deploy to cloud.",
        "Observability: structured logs, metrics, tracing, error reporting.",
    ]


def generate_milestones(title: str):
    return [
        "M1: Prototype core value (1-2 weeks)",
        "M2: Usability + onboarding (1-2 weeks)",
        "M3: Analytics + reliability (1 week)",
        "M4: Beta with 5-10 users and feedback (2 weeks)",
    ]


def generate_risks(title: str):
    return [
        "Ambiguous core value proposition leads to low activation.",
        "Scope creep inflates timeline and hides the signal.",
        "Missing instrumentation blocks learning and iteration.",
    ]


def generate_ideation_outcomes(idea_text: str):
    title = extract_title_from_idea(idea_text)
    target_users = infer_target_users(idea_text)

    problem_statement = (
        f"{title} addresses a clear pain by enabling {', '.join(target_users)} "
        "to achieve their desired outcomes faster and more reliably than current alternatives."
    )

    value_prop = (
        f"With {title}, users reduce time-to-value, improve quality, and gain insights via built-in analytics and automation."
    )

    outcomes = {
        'title': title,
        'problem_statement': problem_statement,
        'target_users': target_users,
        'value_proposition': value_prop,
        'user_stories': generate_user_stories(title, target_users),
        'acceptance_criteria': generate_acceptance_criteria(title),
        'suggested_architecture': generate_architecture_suggestion(title),
        'milestones': generate_milestones(title),
        'risks': generate_risks(title),
        'idea_excerpt': summarize_text(idea_text, 240),
    }
    return outcomes


LANG_HINTS = [
    ("python", [r"\bdef\s+", r"\bclass\s+", r"import\s+", r"from\s+.+\s+import\s+"]),
    ("javascript", [r"function\s+", r"=>", r"console\.log", r"import\s+.*from\s+"]) ,
    ("typescript", [r"interface\s+", r"type\s+", r"export\s+class\s+"]),
    ("shell", [r"#!/bin/sh", r"#!/bin/bash", r"echo "]),
    ("markdown", [r"^# ", r"^## ", r"\* ", r"\- "]),
]


def detect_language(code: str):
    code = code or ''
    scores = {}
    for lang, patterns in LANG_HINTS:
        for p in patterns:
            if re.search(p, code, flags=re.M):
                scores[lang] = scores.get(lang, 0) + 1
    if not scores:
        return 'unknown'
    return max(scores, key=scores.get)


def extract_functions_and_classes(code: str):
    funcs = []
    clss = []
    # Python pattern
    for m in re.finditer(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", code, flags=re.M):
        funcs.append(m.group(1))
    for m in re.finditer(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(?", code, flags=re.M):
        clss.append(m.group(1))
    # JS/TS named functions
    for m in re.finditer(r"function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", code, flags=re.M):
        funcs.append(m.group(1))
    for m in re.finditer(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", code, flags=re.M):
        clss.append(m.group(1))
    # Arrow functions (variable names)
    for m in re.finditer(r"const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\([^)]*\)\s*=>", code, flags=re.M):
        funcs.append(m.group(1))
    # Unique preserve order
    seen = set()
    funcs_u = []
    for f in funcs:
        if f not in seen:
            funcs_u.append(f)
            seen.add(f)
    seen = set()
    clss_u = []
    for c in clss:
        if c not in seen:
            clss_u.append(c)
            seen.add(c)
    return funcs_u, clss_u


def extract_imports(code: str):
    imports = []
    # Python imports
    for m in re.finditer(r"^\s*(?:from\s+([\w\.]+)\s+import\s+[\w\*, ]+|import\s+([\w\.]+))", code, flags=re.M):
        mod = m.group(1) or m.group(2)
        if mod:
            imports.append(mod)
    # JS/TS imports
    for m in re.finditer(r"^\s*import\s+.+?from\s+['\"]([^'\"]+)['\"]", code, flags=re.M):
        imports.append(m.group(1))
    # Unique preserve order
    seen = set()
    out = []
    for i in imports:
        if i not in seen:
            out.append(i)
            seen.add(i)
    return out


def estimate_cyclomatic_complexity(code: str):
    # Very rough heuristic
    keywords = [
        r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b", r"\bwhen\b", r"\bcatch\b", r"\bexcept\b",
        r"\band\b", r"\bor\b", r"\?\:", r"\belse\b", r"\belif\b", r"\btry\b"
    ]
    score = 1
    for kw in keywords:
        score += len(re.findall(kw, code))
    return score


def generate_test_suggestions(funcs):
    suggestions = []
    basic = [
        "Happy path with typical inputs",
        "Edge cases and invalid inputs",
        "Error handling and exceptions",
        "Performance on large inputs",
    ]
    if not funcs:
        return ["No functions detected. Consider adding unit tests for core logic."] + basic
    for f in funcs[:5]:
        suggestions.append(f"Test {f}(): {', '.join(basic)}")
    return suggestions


def refactor_suggestions(code: str):
    suggestions = []
    lines = code.splitlines()
    if len(lines) > 300:
        suggestions.append("Split large modules into cohesive components.")
    if any(len(l) > 120 for l in lines):
        suggestions.append("Shorten long lines (>120 chars) for readability.")
    if re.search(r"global\s+", code):
        suggestions.append("Avoid global state; encapsulate in classes/functions.")
    if len(re.findall(r"TODO|FIXME", code)) >= 3:
        suggestions.append("Address accumulated TODO/FIXME comments.")
    if not suggestions:
        suggestions.append("Codebase looks tidy; consider adding docs and automation.")
    return suggestions


def analyze_code(code_text: str):
    code_text = code_text or ''
    loc = len(code_text.splitlines())
    chars = len(code_text)
    language = detect_language(code_text)
    funcs, classes = extract_functions_and_classes(code_text)
    imports = extract_imports(code_text)
    complexity = estimate_cyclomatic_complexity(code_text)
    tests = generate_test_suggestions(funcs)
    refactors = refactor_suggestions(code_text)

    inferred_architecture = []
    if language == 'python':
        if 'flask' in code_text.lower():
            inferred_architecture.append('Python Flask app with routes and templates/static assets')
        inferred_architecture.append('Use virtualenv/poetry, black/ruff, pytest, and pre-commit')
    elif language in ('javascript', 'typescript'):
        inferred_architecture.append('Node-based app; consider ESLint, Prettier, Jest, and CI pipeline')
    else:
        inferred_architecture.append('General project; set up linter, tests, and CI/CD baseline')

    outcomes = {
        'summary': f"Language: {language}, LOC: {loc}, Chars: {chars}, Estimated complexity: {complexity}",
        'language': language,
        'loc': loc,
        'chars': chars,
        'functions': funcs[:20],
        'classes': classes[:20],
        'imports': imports[:20],
        'inferred_architecture': inferred_architecture,
        'test_suggestions': tests,
        'refactor_suggestions': refactors,
        'code_excerpt': summarize_text(code_text, 240),
    }
    return outcomes


@app.route('/')
def home():
    expected_ideater = [
        'Problem statement and value proposition',
        'Target users and key user stories',
        'Acceptance criteria and initial scope',
        'Suggested architecture and milestones',
        'Risks and assumptions to validate'
    ]
    expected_code = [
        'Code summary (language, LOC, complexity)',
        'Detected functions/classes/imports',
        'Inferred architecture and quality checklist',
        'Test plan suggestions',
        'Refactor recommendations'
    ]
    return render_template('home.html', expected_ideater=expected_ideater, expected_code=expected_code)


@app.route('/ideater', methods=['GET', 'POST'])
def ideater():
    if request.method == 'POST':
        idea = request.form.get('idea', '').strip()
        if not idea:
            flash('Please enter a brief description of your idea.')
            return redirect(url_for('ideater'))
        outcomes = generate_ideation_outcomes(idea)
        return render_template('ideater_result.html', outcomes=outcomes)
    expected = [
        'Problem statement',
        'Value proposition',
        'Target users',
        'User stories',
        'Acceptance criteria',
        'Suggested architecture',
        'Milestones',
        'Risks'
    ]
    sample = (
        "Title: Team Retro Assistant\n"
        "A simple assistant for remote teams to run async retros for engineering sprints.\n"
        "It helps teams capture feedback, cluster themes, and generate action items."
    )
    return render_template('ideater.html', expected=expected, sample=sample)


@app.route('/code', methods=['GET', 'POST'])
def code():
    if request.method == 'POST':
        code_text = request.form.get('code_text', '').strip()
        uploaded = request.files.get('code_file')
        if uploaded and uploaded.filename:
            _, ext = os.path.splitext(uploaded.filename)
            if app.config['UPLOAD_EXTENSIONS'] and ext and ext.lower() not in app.config['UPLOAD_EXTENSIONS']:
                flash(f'Unsupported file type: {ext}')
                return redirect(url_for('code'))
            try:
                data = uploaded.read()
                if isinstance(data, bytes):
                    data = data.decode('utf-8', errors='replace')
                code_text = (code_text + "\n" + data).strip() if code_text else data
            except Exception as e:
                flash('Could not read uploaded file.')
                return redirect(url_for('code'))
        if not code_text:
            flash('Please paste code or upload a file to analyze.')
            return redirect(url_for('code'))
        outcomes = analyze_code(code_text)
        return render_template('code_result.html', outcomes=outcomes)
    expected = [
        'Language, LOC, complexity',
        'Functions/classes/imports',
        'Inferred architecture',
        'Test suggestions',
        'Refactor suggestions'
    ]
    sample = (
        "from flask import Flask\n\n"
        "app = Flask(__name__)\n\n"
        "@app.get('/')\n"
        "def index():\n"
        "    return 'Hello'\n"
    )
    return render_template('code.html', expected=expected, sample=sample)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)



def create_app():
    return app
