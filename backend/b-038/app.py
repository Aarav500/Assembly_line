import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
from planner import generate_learning_path

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    try:
        idea = request.form.get('idea', '').strip()
        if not idea:
            return render_template('index.html', error="Please provide an idea"), 400
        
        team_size = int(request.form.get('team_size', 3) or 3)
        roles_raw = request.form.get('roles', '').strip()
        level = request.form.get('level', 'Beginner')
        duration_weeks = int(request.form.get('duration_weeks', 6) or 6)
        hours_per_week = int(request.form.get('hours_per_week', 5) or 5)
        prefer_free = request.form.get('prefer_free') == 'on'

        team_profile = {
            'team_size': team_size,
            'roles': [r.strip() for r in roles_raw.split(',') if r.strip()]
        }

        plan = generate_learning_path(
            idea=idea,
            team_profile=team_profile,
            duration_weeks=duration_weeks,
            hours_per_person_per_week=hours_per_week,
            prefer_free=prefer_free,
            level=level
        )
        return render_template('plan.html', plan=plan)
    except ValueError as e:
        return render_template('index.html', error="Invalid numeric input"), 400
    except Exception as e:
        return render_template('index.html', error=f"Error generating plan: {str(e)}"), 500

@app.route('/api/plan', methods=['GET'])
def api_plan():
    try:
        idea = request.args.get('idea', '').strip()
        if not idea:
            return jsonify({"error": "Missing required parameter: idea"}), 400

        team_size = int(request.args.get('team_size', 3) or 3)
        roles_raw = request.args.get('roles', '')
        level = request.args.get('level', 'Beginner')
        duration_weeks = int(request.args.get('duration_weeks', 6) or 6)
        hours_per_week = int(request.args.get('hours_per_week', 5) or 5)
        prefer_free = request.args.get('prefer_free', 'true').lower() in ['1', 'true', 'yes']

        team_profile = {
            'team_size': team_size,
            'roles': [r.strip() for r in roles_raw.split(',') if r.strip()]
        }

        plan = generate_learning_path(
            idea=idea,
            team_profile=team_profile,
            duration_weeks=duration_weeks,
            hours_per_person_per_week=hours_per_week,
            prefer_free=prefer_free,
            level=level
        )
        return jsonify(plan)
    except ValueError as e:
        return jsonify({"error": "Invalid numeric parameter"}), 400
    except Exception as e:
        return jsonify({"error": f"Error generating plan: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


def create_app():
    return app


@app.route('/api/learning-paths', methods=['GET', 'POST'])
def _auto_stub_api_learning_paths():
    return 'Auto-generated stub for /api/learning-paths', 200
