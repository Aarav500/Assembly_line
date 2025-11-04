from datetime import datetime
from flask import request, render_template, redirect, url_for, jsonify, flash
from .models import db, Source, Version
from .services.checker import check_source


def init_routes(app):
    @app.route('/')
    def index():
        sources = Source.query.order_by(Source.created_at.desc()).all()
        return render_template('index.html', sources=sources)

    @app.route('/sources/new', methods=['GET', 'POST'])
    def new_source():
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            url = request.form.get('url', '').strip()
            selector = request.form.get('selector', '').strip() or None
            interval = int(request.form.get('interval_minutes', '60') or 60)
            active = request.form.get('active') == 'on'
            notify_email = request.form.get('notify_email', '').strip() or None
            notify_webhook = request.form.get('notify_webhook', '').strip() or None

            if not name or not url:
                flash('Name and URL are required', 'error')
                return render_template('new_source.html')

            s = Source(
                name=name,
                url=url,
                selector=selector,
                interval_minutes=interval,
                active=active,
                notify_email=notify_email,
                notify_webhook=notify_webhook,
                last_checked=None,
            )
            db.session.add(s)
            db.session.commit()
            flash('Source created', 'success')
            return redirect(url_for('source_detail', source_id=s.id))

        return render_template('new_source.html')

    @app.route('/sources/<int:source_id>')
    def source_detail(source_id):
        s = Source.query.get_or_404(source_id)
        versions = Version.query.filter_by(source_id=s.id).order_by(Version.created_at.desc()).all()
        latest = versions[0] if versions else None
        prev = versions[1] if len(versions) > 1 else None
        return render_template('source_detail.html', source=s, versions=versions, latest=latest, prev=prev)

    @app.route('/sources/<int:source_id>/toggle', methods=['POST'])
    def toggle_source(source_id):
        s = Source.query.get_or_404(source_id)
        s.active = not s.active
        db.session.commit()
        return redirect(url_for('source_detail', source_id=source_id))

    @app.route('/sources/<int:source_id>/check', methods=['POST'])
    def check_source_route(source_id):
        s = Source.query.get_or_404(source_id)
        ok = check_source(s)
        if ok:
            flash('Check complete', 'success')
        else:
            flash('Check failed', 'error')
        return redirect(url_for('source_detail', source_id=source_id))

    @app.route('/tasks/run_check', methods=['POST'])
    def run_check_all():
        sources = Source.query.filter_by(active=True).all()
        for s in sources:
            check_source(s)
        return jsonify({"status": "ok", "checked": len(sources)})

    @app.route('/versions/<int:v_id>/diff/<int:other_id>')
    def version_diff(v_id, other_id):
        v = Version.query.get_or_404(v_id)
        other = Version.query.get_or_404(other_id)
        # Prefer precomputed HTML diff if between adjacent versions
        html_table = v.html_diff_to_prev if v and other and v.source_id == other.source_id and v.created_at > other.created_at else None
        if not html_table:
            # compute on the fly
            from .services.diffing import diff_text
            _, html_table, _, _ = diff_text(other.content_text, v.content_text)
        return render_template('diff.html', source=v.source, html_table=html_table, v=v, other=other)

    # Simple JSON APIs
    @app.route('/api/sources', methods=['GET'])
    def api_list_sources():
        sources = Source.query.all()
        data = []
        for s in sources:
            latest = Version.last_for_source(s.id)
            data.append({
                'id': s.id,
                'name': s.name,
                'url': s.url,
                'selector': s.selector,
                'interval_minutes': s.interval_minutes,
                'active': s.active,
                'last_checked': s.last_checked.isoformat() if s.last_checked else None,
                'version_count': Version.count_for_source(s.id),
                'latest_version_id': latest.id if latest else None,
                'next_due': s.next_due().isoformat() if s.active else None,
            })
        return jsonify(data)

    @app.route('/api/sources', methods=['POST'])
    def api_create_source():
        data = request.get_json(force=True)
        s = Source(
            name=data.get('name'),
            url=data.get('url'),
            selector=data.get('selector'),
            interval_minutes=int(data.get('interval_minutes') or 60),
            active=bool(data.get('active', True)),
            notify_email=data.get('notify_email'),
            notify_webhook=data.get('notify_webhook'),
        )
        db.session.add(s)
        db.session.commit()
        return jsonify({'id': s.id}), 201

    @app.route('/api/sources/<int:source_id>/check', methods=['POST'])
    def api_check_source(source_id):
        s = Source.query.get_or_404(source_id)
        ok = check_source(s)
        return jsonify({'status': 'ok' if ok else 'error'})

