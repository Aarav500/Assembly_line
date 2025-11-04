import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import inspect, MetaData
import difflib

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)


@app.route('/')
def index():
    return jsonify({'message': 'Migration & Upgrade Assist API'})


@app.route('/db/schema', methods=['GET'])
def get_schema():
    """Get current database schema"""
    inspector = inspect(db.engine)
    schema = {}
    
    for table_name in inspector.get_table_names():
        columns = []
        for column in inspector.get_columns(table_name):
            columns.append({
                'name': column['name'],
                'type': str(column['type']),
                'nullable': column['nullable']
            })
        schema[table_name] = columns
    
    return jsonify({'schema': schema})


@app.route('/db/suggest-migration', methods=['POST'])
def suggest_migration():
    """Suggest database migration based on proposed changes"""
    proposed_changes = request.json
    
    inspector = inspect(db.engine)
    current_tables = inspector.get_table_names()
    
    suggestions = []
    safety_checks = []
    
    # Check for new tables
    if 'new_tables' in proposed_changes:
        for table in proposed_changes['new_tables']:
            suggestions.append(f"CREATE TABLE {table}")
            safety_checks.append({'type': 'info', 'message': f'New table {table} will be created'})
    
    # Check for table modifications
    if 'modify_tables' in proposed_changes:
        for table, modifications in proposed_changes['modify_tables'].items():
            if table not in current_tables:
                safety_checks.append({'type': 'error', 'message': f'Table {table} does not exist'})
                continue
            
            if 'add_columns' in modifications:
                for column in modifications['add_columns']:
                    suggestions.append(f"ALTER TABLE {table} ADD COLUMN {column}")
                    safety_checks.append({'type': 'info', 'message': f'Column {column} will be added to {table}'})
            
            if 'drop_columns' in modifications:
                for column in modifications['drop_columns']:
                    suggestions.append(f"ALTER TABLE {table} DROP COLUMN {column}")
                    safety_checks.append({'type': 'warning', 'message': f'Dropping column {column} from {table} will cause data loss'})
    
    # Check for table drops
    if 'drop_tables' in proposed_changes:
        for table in proposed_changes['drop_tables']:
            suggestions.append(f"DROP TABLE {table}")
            safety_checks.append({'type': 'critical', 'message': f'Dropping table {table} will cause permanent data loss'})
    
    return jsonify({
        'suggestions': suggestions,
        'safety_checks': safety_checks,
        'safe_to_apply': all(check['type'] != 'critical' for check in safety_checks)
    })


@app.route('/db/compare-models', methods=['GET'])
def compare_models():
    """Compare current DB schema with SQLAlchemy models"""
    inspector = inspect(db.engine)
    db_tables = set(inspector.get_table_names())
    
    # Get model tables
    model_tables = set()
    for table in db.Model.metadata.tables.values():
        model_tables.add(table.name)
    
    differences = {
        'missing_in_db': list(model_tables - db_tables),
        'missing_in_models': list(db_tables - model_tables - {'alembic_version'}),
        'requires_migration': len(model_tables - db_tables) > 0
    }
    
    return jsonify(differences)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


def create_app():
    return app
