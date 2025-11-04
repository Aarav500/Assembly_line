import os
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, abort, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import safe_join
from models import db, Template, TemplateVersion, Purchase

marketplace_bp = Blueprint('marketplace', __name__)

ALLOWED_EXTENSIONS = {'.zip', '.json', '.yaml', '.yml', '.txt'}

def allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


def ensure_upload_dir(template_id: int) -> str:
    base = current_app.config['UPLOAD_FOLDER']
    path = os.path.join(base, 'templates', str(template_id))
    os.makedirs(path, exist_ok=True)
    return path


@marketplace_bp.route('/')
def index():
    q = request.args.get('q', '').strip()
    query = Template.query.filter_by(is_published=True)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Template.title.ilike(like), Template.description.ilike(like)))
    templates = query.order_by(Template.created_at.desc()).all()
    return render_template('index.html', templates=templates, q=q)


@marketplace_bp.route('/dashboard')
@login_required
def dashboard():
    my_templates = Template.query.filter_by(owner_id=current_user.id).all()
    # revenue aggregate
    revenue_cents = 0
    sales_count = 0
    for t in my_templates:
        for p in t.purchases:
            if p.status == 'paid':
                revenue_cents += p.amount_cents
                sales_count += 1
    return render_template('dashboard.html', templates=my_templates, revenue_cents=revenue_cents, sales_count=sales_count)


@marketplace_bp.route('/purchases')
@login_required
def purchases():
    purchases = Purchase.query.filter_by(user_id=current_user.id).order_by(Purchase.created_at.desc()).all()
    return render_template('purchases.html', purchases=purchases)


@marketplace_bp.route('/template/new', methods=['GET', 'POST'])
@login_required
def create_template():
    if not current_user.is_seller:
        flash('Seller account required to create templates.', 'error')
        return redirect(url_for('marketplace.index'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price')
        currency = request.form.get('currency', 'usd').strip().lower() or 'usd'
        try:
            price_cents = int(float(price) * 100)
        except Exception:
            price_cents = 0
        if not title:
            flash('Title is required.', 'error')
            return render_template('create_template.html')
        tmpl = Template(title=title, description=description, price_cents=price_cents, currency=currency, owner_id=current_user.id)
        db.session.add(tmpl)
        db.session.commit()
        flash('Template created. You can now add a version.', 'success')
        return redirect(url_for('marketplace.template_detail', template_id=tmpl.id))
    return render_template('create_template.html')


@marketplace_bp.route('/template/<int:template_id>')
def template_detail(template_id):
    tmpl = Template.query.get_or_404(template_id)
    purchased = False
    if current_user.is_authenticated:
        purchase = Purchase.query.filter_by(user_id=current_user.id, template_id=tmpl.id).first()
        purchased = bool(purchase and purchase.is_paid())
    latest = tmpl.latest_version()
    return render_template('template_detail.html', template=tmpl, purchased=purchased, latest=latest)


@marketplace_bp.route('/template/<int:template_id>/version/new', methods=['GET', 'POST'])
@login_required
def new_version(template_id):
    tmpl = Template.query.get_or_404(template_id)
    if tmpl.owner_id != current_user.id:
        abort(403)
    if request.method == 'POST':
        version = request.form.get('version', '').strip()
        changelog = request.form.get('changelog', '').strip()
        file = request.files.get('file')
        if not version:
            flash('Version is required (e.g., 1.0.0).', 'error')
            return render_template('new_version.html', template=tmpl)
        if not file or file.filename == '':
            flash('File is required.', 'error')
            return render_template('new_version.html', template=tmpl)
        filename = secure_filename(file.filename)
        if not allowed_file(filename):
            flash('Invalid file type.', 'error')
            return render_template('new_version.html', template=tmpl)
        dirpath = ensure_upload_dir(tmpl.id)
        # Temporarily add a record to get version id for filename prefix
        tv = TemplateVersion(template_id=tmpl.id, version=version, changelog=changelog, file_path='', filename=filename)
        db.session.add(tv)
        db.session.flush()
        stored_name = f"{tv.id}__{filename}"
        filepath = os.path.join(dirpath, stored_name)
        file.save(filepath)
        # Store relative path from uploads root for safer joining later
        rel_path = os.path.join('templates', str(tmpl.id), stored_name)
        tv.file_path = rel_path
        db.session.commit()
        flash('New version uploaded.', 'success')
        return redirect(url_for('marketplace.template_detail', template_id=tmpl.id))
    return render_template('new_version.html', template=tmpl)


@marketplace_bp.route('/download/<int:version_id>')
@login_required
def download(version_id):
    version = TemplateVersion.query.get_or_404(version_id)
    tmpl = version.template
    if not (tmpl.owner_id == current_user.id or Purchase.query.filter_by(user_id=current_user.id, template_id=tmpl.id, status='paid').first()):
        abort(403)
    uploads_root = current_app.config['UPLOAD_FOLDER']
    abs_path = os.path.join(uploads_root, version.file_path)
    directory = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)
    # Ensure path is within uploads root
    safe_path = safe_join(uploads_root, version.file_path)
    if not safe_path or not os.path.exists(safe_path):
        abort(404)
    return send_from_directory(directory, filename, as_attachment=True, download_name=version.filename)


