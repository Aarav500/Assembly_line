import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import sqlite3
import base64
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'ideas.db')
UPLOAD_ROOT = os.path.join(BASE_DIR, 'uploads')
AUDIO_DIR = os.path.join(UPLOAD_ROOT, 'audio')
IMAGE_DIR = os.path.join(UPLOAD_ROOT, 'images')

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

ALLOWED_AUDIO_EXTENSIONS = {"wav", "mp3", "m4a", "webm", "ogg"}
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

MIMETYPE_EXT_MAP = {
    'audio/wav': 'wav',
    'audio/x-wav': 'wav',
    'audio/mpeg': 'mp3',
    'audio/mp3': 'mp3',
    'audio/webm': 'webm',
    'audio/ogg': 'ogg',
    'audio/aac': 'm4a',
    'image/png': 'png',
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/gif': 'gif',
    'image/webp': 'webp'
}


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            text TEXT,
            audio_path TEXT,
            image_path TEXT,
            created_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()


init_db()


def allowed_file(filename, allowed_exts):
    if not filename:
        return False
    return "." in filename and filename.rsplit('.', 1)[1].lower() in allowed_exts


def guess_extension_from_mimetype(mimetype, fallback=None):
    return MIMETYPE_EXT_MAP.get(mimetype, fallback)


def save_uploaded_file(file_storage, target_dir, allowed_exts):
    if not file_storage:
        return None
    filename = secure_filename(file_storage.filename or '')
    ext = None
    if filename and "." in filename:
        ext = filename.rsplit('.', 1)[1].lower()
    if not ext:
        ext = guess_extension_from_mimetype(file_storage.mimetype)
    if not ext:
        return None
    if ext not in allowed_exts:
        return None
    new_name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(target_dir, new_name)
    file_storage.save(path)
    return new_name


def save_data_url_image(data_url, target_dir):
    if not data_url:
        return None
    if not data_url.startswith('data:'):
        return None
    try:
        header, b64data = data_url.split(',', 1)
        mimetype = header.split(';')[0].split(':')[1]
        ext = guess_extension_from_mimetype(mimetype, 'png')
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return None
        binary = base64.b64decode(b64data)
        new_name = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(target_dir, new_name)
        with open(path, 'wb') as f:
            f.write(binary)
        return new_name
    except Exception:
        return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/ideas', methods=['GET'])
def list_ideas():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM ideas ORDER BY datetime(created_at) DESC").fetchall()
    conn.close()
    items = []
    for r in rows:
        audio_url = url_for('serve_audio', filename=os.path.basename(r['audio_path'])) if r['audio_path'] else None
        image_url = url_for('serve_image', filename=os.path.basename(r['image_path'])) if r['image_path'] else None
        items.append({
            'id': r['id'],
            'title': r['title'] or '',
            'text': r['text'] or '',
            'audio_url': audio_url,
            'image_url': image_url,
            'created_at': r['created_at']
        })
    return jsonify({'items': items})


@app.route('/api/ideas', methods=['POST'])
def create_idea():
    title = (request.form.get('title') or '').strip()
    text = (request.form.get('text') or '').strip()

    audio_file = request.files.get('audio')
    image_file = request.files.get('image')
    image_data_url = request.form.get('imageData')

    saved_audio = None
    saved_image = None

    if audio_file and audio_file.filename:
        saved_audio_name = save_uploaded_file(audio_file, AUDIO_DIR, ALLOWED_AUDIO_EXTENSIONS)
        if saved_audio_name:
            saved_audio = os.path.join('audio', saved_audio_name)

    # prioritize uploaded image file over data URL
    if image_file and image_file.filename:
        saved_image_name = save_uploaded_file(image_file, IMAGE_DIR, ALLOWED_IMAGE_EXTENSIONS)
        if saved_image_name:
            saved_image = os.path.join('images', saved_image_name)
    elif image_data_url:
        saved_image_name = save_data_url_image(image_data_url, IMAGE_DIR)
        if saved_image_name:
            saved_image = os.path.join('images', saved_image_name)

    if not any([title, text, saved_audio, saved_image]):
        return jsonify({'error': 'Provide at least one of: title, text, audio, or image/sketch.'}), 400

    created_at = datetime.utcnow().isoformat() + 'Z'

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO ideas (title, text, audio_path, image_path, created_at) VALUES (?, ?, ?, ?, ?)',
        (title, text, saved_audio, saved_image, created_at)
    )
    conn.commit()
    idea_id = cur.lastrowid
    conn.close()

    audio_url = url_for('serve_audio', filename=os.path.basename(saved_audio)) if saved_audio else None
    image_url = url_for('serve_image', filename=os.path.basename(saved_image)) if saved_image else None

    return jsonify({
        'id': idea_id,
        'title': title,
        'text': text,
        'audio_url': audio_url,
        'image_url': image_url,
        'created_at': created_at
    }), 201


@app.route('/uploads/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename, as_attachment=False)


@app.route('/uploads/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGE_DIR, filename, as_attachment=False)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app
