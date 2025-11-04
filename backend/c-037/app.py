import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/multitenant')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'poolclass': NullPool}

db = SQLAlchemy(app)

TENANT_SCHEMAS = {
    'tenant1': 'tenant1_schema',
    'tenant2': 'tenant2_schema',
    'tenant3': 'tenant3_schema'
}

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)

@app.before_request
def set_tenant_schema():
    tenant_id = request.headers.get('X-Tenant-ID')
    if tenant_id and tenant_id in TENANT_SCHEMAS:
        g.tenant_schema = TENANT_SCHEMAS[tenant_id]
    else:
        g.tenant_schema = None

def get_tenant_engine():
    if not hasattr(g, 'tenant_schema') or g.tenant_schema is None:
        return None
    return db.engine

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/tenants', methods=['GET'])
def list_tenants():
    return jsonify({'tenants': list(TENANT_SCHEMAS.keys())}), 200

@app.route('/init-schema', methods=['POST'])
def init_schema():
    tenant_id = request.headers.get('X-Tenant-ID')
    if not tenant_id or tenant_id not in TENANT_SCHEMAS:
        return jsonify({'error': 'Invalid tenant'}), 400
    
    schema_name = TENANT_SCHEMAS[tenant_id]
    try:
        with db.engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {schema_name}'))
            conn.execute(text(f'CREATE TABLE IF NOT EXISTS {schema_name}.users (id SERIAL PRIMARY KEY, name VARCHAR(100), email VARCHAR(100))'))
            conn.commit()
        return jsonify({'message': f'Schema {schema_name} initialized'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/users', methods=['GET'])
def get_users():
    if not g.tenant_schema:
        return jsonify({'error': 'Tenant not specified'}), 400
    
    try:
        with db.engine.connect() as conn:
            result = conn.execute(text(f'SELECT id, name, email FROM {g.tenant_schema}.users'))
            users = [{'id': row[0], 'name': row[1], 'email': row[2]} for row in result]
        return jsonify({'users': users}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/users', methods=['POST'])
def create_user():
    if not g.tenant_schema:
        return jsonify({'error': 'Tenant not specified'}), 400
    
    data = request.get_json()
    if not data or 'name' not in data or 'email' not in data:
        return jsonify({'error': 'Name and email required'}), 400
    
    try:
        with db.engine.connect() as conn:
            result = conn.execute(
                text(f'INSERT INTO {g.tenant_schema}.users (name, email) VALUES (:name, :email) RETURNING id'),
                {'name': data['name'], 'email': data['email']}
            )
            user_id = result.fetchone()[0]
            conn.commit()
        return jsonify({'id': user_id, 'name': data['name'], 'email': data['email']}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def create_app():
    return app
