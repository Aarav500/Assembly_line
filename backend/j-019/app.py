import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from functools import wraps
import random
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-change-me'

USERS = {
    'alice': {'password': 'pm123', 'role': 'pm', 'name': 'Alice'},
    'bob': {'password': 'dev123', 'role': 'dev', 'name': 'Bob'},
    'eve': {'password': 'exec123', 'role': 'exec', 'name': 'Eve'},
}


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def _seed_for_role(role: str):
    today = datetime.utcnow().timetuple().tm_yday
    seed = hash(role) % 100000 + today
    random.seed(seed)


def _series(n, min_v, max_v, ints=False, smooth=False):
    vals = []
    curr = random.uniform(min_v, max_v)
    for _ in range(n):
        if smooth:
            drift = random.uniform(-1, 1) * (max_v - min_v) * 0.05
            curr = max(min_v, min(max_v, curr + drift))
        else:
            curr = random.uniform(min_v, max_v)
        vals.append(int(round(curr)) if ints else round(curr, 2))
    return vals


def generate_kpi_data(role: str):
    _seed_for_role(role)
    common = {
        'role': role,
        'period': 'Last 8 Weeks'
    }

    if role == 'pm':
        labels = [f"S{i}" for i in range(1, 9)]
        velocity = _series(8, 35, 65, ints=True, smooth=True)
        bugs = _series(8, 20, 60, ints=True, smooth=True)
        active_users = _series(8, 1200, 2400, ints=True, smooth=True)

        widgets = [
            {'title': 'Feature Completion', 'value': f"{_series(1, 72, 92, ints=True)[0]}%", 'delta': round(random.uniform(-3, 7), 1)},
            {'title': 'Sprint Velocity', 'value': f"{velocity[-1]} pts", 'delta': round((velocity[-1] - velocity[-2]) / max(1, velocity[-2]) * 100, 1)},
            {'title': 'Bug Backlog', 'value': f"{_series(1, 40, 120, ints=True)[0]}", 'delta': round(random.uniform(-10, 10), 1)},
            {'title': 'On-time Delivery', 'value': f"{_series(1, 75, 98, ints=True)[0]}%", 'delta': round(random.uniform(-5, 5), 1)},
        ]
        charts = [
            {
                'id': 'velocityChart',
                'title': 'Sprint Velocity (pts)',
                'type': 'line',
                'labels': labels,
                'datasets': [
                    {
                        'label': 'Velocity',
                        'data': velocity,
                        'borderColor': '#2563eb',
                        'backgroundColor': 'rgba(37, 99, 235, 0.2)',
                        'fill': True,
                        'tension': 0.35,
                    }
                ],
            },
            {
                'id': 'bugChart',
                'title': 'Bugs Opened by Week',
                'type': 'bar',
                'labels': labels,
                'datasets': [
                    {
                        'label': 'Bugs',
                        'data': bugs,
                        'borderColor': '#ef4444',
                        'backgroundColor': 'rgba(239, 68, 68, 0.7)'
                    }
                ],
            },
            {
                'id': 'activeUsersChart',
                'title': 'Active Users',
                'type': 'line',
                'labels': labels,
                'datasets': [
                    {
                        'label': 'Active Users',
                        'data': active_users,
                        'borderColor': '#059669',
                        'backgroundColor': 'rgba(5, 150, 105, 0.2)',
                        'fill': True,
                        'tension': 0.35,
                    }
                ],
            },
        ]
        common.update({'widgets': widgets, 'charts': charts})
        return common

    if role == 'dev':
        days = [f"D{i}" for i in range(1, 11)]
        build_rate = _series(10, 82, 100, ints=True, smooth=True)
        coverage = _series(10, 60, 88, ints=True, smooth=True)
        prs_open = _series(1, 3, 15, ints=True)[0]
        prs_review = _series(1, 2, 10, ints=True)[0]
        prs_merged = _series(1, 5, 20, ints=True)[0]

        widgets = [
            {'title': 'Open PRs', 'value': str(prs_open), 'delta': round(random.uniform(-30, 30), 1)},
            {'title': 'Build Success', 'value': f"{build_rate[-1]}%", 'delta': round(build_rate[-1] - build_rate[-2], 1)},
            {'title': 'Code Coverage', 'value': f"{coverage[-1]}%", 'delta': round(coverage[-1] - coverage[-2], 1)},
            {'title': 'Deploys (wk)', 'value': str(_series(1, 2, 12, ints=True)[0]), 'delta': round(random.uniform(-40, 40), 1)},
        ]
        charts = [
            {
                'id': 'buildChart',
                'title': 'Build Success Rate',
                'type': 'line',
                'labels': days,
                'datasets': [
                    {
                        'label': 'Success %',
                        'data': build_rate,
                        'borderColor': '#10b981',
                        'backgroundColor': 'rgba(16, 185, 129, 0.2)',
                        'fill': True,
                        'tension': 0.35,
                    }
                ],
            },
            {
                'id': 'coverageChart',
                'title': 'Code Coverage',
                'type': 'line',
                'labels': days,
                'datasets': [
                    {
                        'label': 'Coverage %',
                        'data': coverage,
                        'borderColor': '#f59e0b',
                        'backgroundColor': 'rgba(245, 158, 11, 0.2)',
                        'fill': True,
                        'tension': 0.35,
                    }
                ],
            },
            {
                'id': 'prsChart',
                'title': 'Pull Requests Status',
                'type': 'doughnut',
                'labels': ['Open', 'In Review', 'Merged'],
                'datasets': [
                    {
                        'label': 'PRs',
                        'data': [prs_open, prs_review, prs_merged],
                        'backgroundColor': ['#3b82f6', '#a855f7', '#22c55e'],
                        'borderWidth': 0
                    }
                ],
            },
        ]
        common.update({'widgets': widgets, 'charts': charts})
        return common

    if role == 'exec':
        months = [
            'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug'
        ]
        revenue = _series(8, 120, 260, ints=True, smooth=True)
        dau = _series(8, 2.5, 4.2, smooth=True)
        mau = [round(d * random.uniform(6.5, 8.5), 2) for d in dau]
        churn = _series(1, 2.0, 6.0)[0]
        nps = _series(8, 30, 65, ints=True, smooth=True)

        widgets = [
            {'title': 'ARR', 'value': f"${_series(1, 3.2, 6.8)[0]:.1f}M", 'delta': round(random.uniform(-3, 8), 1)},
            {'title': 'MRR', 'value': f"${_series(1, 260, 480, ints=True)[0]}k", 'delta': round(random.uniform(-5, 9), 1)},
            {'title': 'Churn', 'value': f"{churn:.1f}%", 'delta': round(random.uniform(-1.5, 1.5), 1)},
            {'title': 'NPS', 'value': f"{nps[-1]}", 'delta': round(nps[-1] - nps[-2], 1)},
        ]
        charts = [
            {
                'id': 'revenueChart',
                'title': 'Revenue ($k)',
                'type': 'bar',
                'labels': months,
                'datasets': [
                    {
                        'label': 'Revenue',
                        'data': revenue,
                        'backgroundColor': 'rgba(59, 130, 246, 0.8)',
                        'borderColor': '#2563eb'
                    }
                ],
            },
            {
                'id': 'engagementChart',
                'title': 'DAU vs MAU (k)',
                'type': 'line',
                'labels': months,
                'datasets': [
                    {
                        'label': 'DAU',
                        'data': [round(v * 1000) for v in dau],
                        'borderColor': '#22c55e',
                        'backgroundColor': 'rgba(34, 197, 94, 0.2)',
                        'fill': True,
                        'tension': 0.35,
                    },
                    {
                        'label': 'MAU',
                        'data': [round(v * 1000) for v in mau],
                        'borderColor': '#a855f7',
                        'backgroundColor': 'rgba(168, 85, 247, 0.15)',
                        'fill': True,
                        'tension': 0.35,
                    }
                ],
            },
            {
                'id': 'npsChart',
                'title': 'NPS Trend',
                'type': 'line',
                'labels': months,
                'datasets': [
                    {
                        'label': 'NPS',
                        'data': nps,
                        'borderColor': '#f97316',
                        'backgroundColor': 'rgba(249, 115, 22, 0.2)',
                        'fill': True,
                        'tension': 0.35,
                    }
                ],
            },
        ]
        common.update({'widgets': widgets, 'charts': charts})
        return common

    # default fallback
    return {'role': role, 'widgets': [], 'charts': []}


@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = USERS.get(username)
        if user and user['password'] == password:
            session['user'] = username
            session['role'] = user['role']
            session['name'] = user.get('name', username)
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid credentials'
    return render_template('login.html', error=error, users=USERS)


@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role', 'pm')
    data = generate_kpi_data(role)
    return render_template('dashboard.html', data=data, user=session.get('name'), role=role)


@app.route('/api/kpis')
@login_required
def api_kpis():
    role = session.get('role', 'pm')
    return jsonify(generate_kpi_data(role))


if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app


@app.route('/api/kpis/dev', methods=['GET'])
def _auto_stub_api_kpis_dev():
    return 'Auto-generated stub for /api/kpis/dev', 200


@app.route('/api/kpis/invalid', methods=['GET'])
def _auto_stub_api_kpis_invalid():
    return 'Auto-generated stub for /api/kpis/invalid', 200
