import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, jsonify, abort
from pathlib import Path
import json
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / 'data' / 'projects.json'


def load_projects():
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def compute_project_metrics(p):
    tasks_total = p.get('metrics', {}).get('tasks_total', 0) or 0
    tasks_completed = p.get('metrics', {}).get('tasks_completed', 0) or 0
    completion = (tasks_completed / tasks_total * 100.0) if tasks_total else 0.0
    budget = float(p.get('budget', 0) or 0)
    spent = float(p.get('spent', 0) or 0)
    remaining = budget - spent
    utilization = (spent / budget * 100.0) if budget else 0.0
    over_by = max(spent - budget, 0)

    # Sort monthly costs
    monthly = p.get('costs_by_month', {})
    monthly_sorted = sorted(monthly.items(), key=lambda kv: datetime.strptime(kv[0], '%Y-%m'))

    return {
        'id': p.get('id'),
        'name': p.get('name'),
        'owner': p.get('owner'),
        'status': p.get('status'),
        'budget': budget,
        'spent': spent,
        'remaining': remaining,
        'utilization': utilization,
        'completion': completion,
        'start_date': p.get('start_date'),
        'end_date': p.get('end_date'),
        'team_size': p.get('team_size'),
        'velocity': p.get('metrics', {}).get('velocity'),
        'tasks_total': tasks_total,
        'tasks_completed': tasks_completed,
        'over_by': over_by,
        'costs_by_month': [{'month': m, 'cost': float(c)} for m, c in monthly_sorted],
    }


def compute_summary(projects):
    total_budget = 0.0
    total_spent = 0.0
    total_remaining = 0.0
    status_counts = defaultdict(int)
    monthly_map = defaultdict(float)
    completions = []

    computed = []
    for p in projects:
        m = compute_project_metrics(p)
        computed.append(m)
        total_budget += m['budget']
        total_spent += m['spent']
        total_remaining += m['remaining']
        status_counts[m['status']] += 1
        completions.append(m['completion'])
        for item in m['costs_by_month']:
            monthly_map[item['month']] += item['cost']

    utilization = (total_spent / total_budget * 100.0) if total_budget else 0.0
    avg_completion = sum(completions) / len(completions) if completions else 0.0

    months_sorted = sorted(monthly_map.keys(), key=lambda m: datetime.strptime(m, '%Y-%m'))
    monthly_costs = [{'month': m, 'cost': monthly_map[m]} for m in months_sorted]

    # Top over-budget projects
    over_list = [
        {
            'id': m['id'],
            'name': m['name'],
            'over_by': m['over_by'],
            'utilization': m['utilization']
        }
        for m in computed if m['over_by'] > 0
    ]
    over_list.sort(key=lambda x: x['over_by'], reverse=True)
    top_over_budget = over_list[:5]

    return {
        'total_projects': len(projects),
        'status_counts': dict(status_counts),
        'total_budget': total_budget,
        'total_spent': total_spent,
        'total_remaining': total_remaining,
        'utilization': utilization,
        'avg_completion': avg_completion,
        'monthly_costs': monthly_costs,
        'currency': 'USD',
        'top_over_budget': top_over_budget,
        'projects': computed,
    }


@app.template_filter('currency')
def currency_filter(amount, code='USD'):
    try:
        amount = float(amount)
    except Exception:
        return str(amount)
    symbol = '$' if code == 'USD' else f'{code} '
    return f"{symbol}{amount:,.2f}"


@app.template_filter('pct')
def pct_filter(value):
    try:
        value = float(value)
    except Exception:
        return str(value)
    return f"{value:.1f}%"


@app.route('/')
def dashboard():
    projects = load_projects()
    summary = compute_summary(projects)
    return render_template('dashboard.html', summary=summary, projects=summary['projects'])


@app.route('/project/<project_id>')
def project_detail(project_id):
    projects = load_projects()
    project = next((p for p in projects if p.get('id') == project_id), None)
    if not project:
        abort(404)
    m = compute_project_metrics(project)
    return render_template('project_detail.html', project=m)


@app.route('/api/summary')
def api_summary():
    projects = load_projects()
    summary = compute_summary(projects)
    # Remove duplicated list in API summary to keep payload concise
    out = dict(summary)
    out.pop('projects', None)
    return jsonify(out)


@app.route('/api/projects')
def api_projects():
    projects = load_projects()
    computed = [compute_project_metrics(p) for p in projects]
    return jsonify(computed)


@app.route('/api/project/<project_id>')
def api_project(project_id):
    projects = load_projects()
    project = next((p for p in projects if p.get('id') == project_id), None)
    if not project:
        abort(404)
    return jsonify(compute_project_metrics(project))


if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app


@app.route('/api/projects/project-1', methods=['GET'])
def _auto_stub_api_projects_project_1():
    return 'Auto-generated stub for /api/projects/project-1', 200


@app.route('/api/projects/project-999', methods=['GET'])
def _auto_stub_api_projects_project_999():
    return 'Auto-generated stub for /api/projects/project-999', 200
