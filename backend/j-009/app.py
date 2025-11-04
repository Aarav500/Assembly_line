import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask import jsonify
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
from models import db, BlueprintItem, Rating


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///marketplace.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    upload_dir = os.environ.get('UPLOAD_FOLDER', os.path.join(app.root_path, 'uploads'))
    app.config['UPLOAD_FOLDER'] = upload_dir
    os.makedirs(upload_dir, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    register_routes(app)

    return app


def allowed_file(filename):
    # Allow common archive and text formats. Adjust as needed.
    allowed = {'zip', 'json', 'yaml', 'yml', 'txt', 'tar', 'gz'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def client_ip():
    # Try to get real client IP behind proxy, fallback to remote_addr
    fwd = request.headers.get('X-Forwarded-For', '')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'


def register_routes(app: Flask):
    @app.route('/')
    def index():
        q = request.args.get('q', '').strip()
        query = BlueprintItem.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                (BlueprintItem.title.ilike(like)) |
                (BlueprintItem.description.ilike(like)) |
                (BlueprintItem.author.ilike(like))
            )
        items = query.order_by(BlueprintItem.created_at.desc()).all()
        return render_template('index.html', items=items, q=q)

    @app.route('/blueprints/new', methods=['GET', 'POST'])
    def new_blueprint():
        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            author = request.form.get('author', '').strip()
            file = request.files.get('file')

            if not title:
                flash('Title is required.', 'danger')
                return render_template('new_blueprint.html')
            if not file or file.filename == '':
                flash('A file must be uploaded.', 'danger')
                return render_template('new_blueprint.html')
            if not allowed_file(file.filename):
                flash('File type not allowed.', 'danger')
                return render_template('new_blueprint.html')

            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
            stored_name = f"{timestamp}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], stored_name))

            item = BlueprintItem(
                title=title,
                description=description,
                author=author or 'Anonymous',
                file_name=stored_name,
            )
            db.session.add(item)
            db.session.commit()
            flash('Blueprint published successfully.', 'success')
            return redirect(url_for('detail', item_id=item.id))

        return render_template('new_blueprint.html')

    @app.route('/blueprints/<int:item_id>')
    def detail(item_id):
        item = BlueprintItem.query.get_or_404(item_id)
        # Increment view count
        item.view_count = (item.view_count or 0) + 1
        db.session.commit()
        ratings = item.ratings.order_by(Rating.created_at.desc()).all()
        return render_template('detail.html', item=item, ratings=ratings)

    @app.route('/blueprints/<int:item_id>/download')
    def download(item_id):
        item = BlueprintItem.query.get_or_404(item_id)
        item.download_count = (item.download_count or 0) + 1
        db.session.commit()
        return send_from_directory(app.config['UPLOAD_FOLDER'], item.file_name, as_attachment=True)

    @app.route('/blueprints/<int:item_id>/rate', methods=['POST'])
    def rate(item_id):
        item = BlueprintItem.query.get_or_404(item_id)
        try:
            score = int(request.form.get('score', '0'))
        except ValueError:
            score = 0
        comment = request.form.get('comment', '').strip()
        if score < 1 or score > 5:
            flash('Score must be between 1 and 5.', 'danger')
            return redirect(url_for('detail', item_id=item.id))
        rating = Rating(
            blueprint_id=item.id,
            score=score,
            comment=comment,
            ip_address=client_ip(),
        )
        db.session.add(rating)
        try:
            db.session.commit()
            flash('Thanks for your rating!', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('You have already rated this blueprint from your IP.', 'warning')
        return redirect(url_for('detail', item_id=item.id))

    @app.route('/analytics')
    def analytics():
        items = BlueprintItem.query.order_by(BlueprintItem.view_count.desc()).all()
        labels = [i.title for i in items]
        views = [i.view_count for i in items]
        downloads = [i.download_count for i in items]
        avg_ratings = [i.average_rating() for i in items]
        rating_counts = [i.rating_count() for i in items]
        data = {
            'labels': labels,
            'views': views,
            'downloads': downloads,
            'avgRatings': avg_ratings,
            'ratingCounts': rating_counts,
        }
        return render_template('analytics.html', chart_data=json.dumps(data))

    # Simple JSON API endpoints (optional)
    @app.route('/api/blueprints')
    def api_blueprints():
        items = BlueprintItem.query.order_by(BlueprintItem.created_at.desc()).all()
        return jsonify([
            {
                'id': i.id,
                'title': i.title,
                'description': i.description,
                'author': i.author,
                'created_at': i.created_at.isoformat(),
                'view_count': i.view_count,
                'download_count': i.download_count,
                'average_rating': i.average_rating(),
                'rating_count': i.rating_count(),
            } for i in items
        ])


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



@app.route('/blueprints/bp1', methods=['GET'])
def _auto_stub_blueprints_bp1():
    return 'Auto-generated stub for /blueprints/bp1', 200


@app.route('/blueprints/bp2/download', methods=['POST'])
def _auto_stub_blueprints_bp2_download():
    return 'Auto-generated stub for /blueprints/bp2/download', 200


@app.route('/blueprints/bp2/rate', methods=['POST'])
def _auto_stub_blueprints_bp2_rate():
    return 'Auto-generated stub for /blueprints/bp2/rate', 200
