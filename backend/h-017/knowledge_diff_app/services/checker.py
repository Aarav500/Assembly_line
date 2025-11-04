from datetime import datetime
from flask import current_app
from ..models import db, Source, Version
from .fetcher import fetch_content
from .diffing import sha256_hex, diff_text
from .notifier import notify_change


def ensure_initial_version(source: Source, content_text: str, content_hash: str):
    v = Version(
        source_id=source.id,
        content_text=content_text,
        content_hash=content_hash,
        diff_to_prev=None,
        html_diff_to_prev=None,
        added_lines=0,
        removed_lines=0,
    )
    db.session.add(v)
    db.session.commit()
    return v


def check_source(source: Source):
    app_base = current_app.config.get('APP_BASE_URL', 'http://localhost:5000')
    try:
        text = fetch_content(source.url, selector=source.selector)
        content_hash = sha256_hex(text)

        last = Version.last_for_source(source.id)
        if not last:
            v = ensure_initial_version(source, text, content_hash)
            current_app.logger.info(f"Initialized source '{source.name}' with first version {v.id}")
        else:
            if last.content_hash != content_hash:
                unified, html_diff, added, removed = diff_text(last.content_text, text)
                v = Version(
                    source_id=source.id,
                    content_text=text,
                    content_hash=content_hash,
                    diff_to_prev=unified,
                    html_diff_to_prev=html_diff,
                    added_lines=added,
                    removed_lines=removed,
                )
                db.session.add(v)
                db.session.commit()
                diff_url = f"{app_base}/versions/{v.id}/diff/{last.id}"
                notify_change(source, v, diff_url)
                current_app.logger.info(f"Change detected for '{source.name}': +{added} -{removed}")
            else:
                current_app.logger.info(f"No changes for '{source.name}'")
        source.last_checked = datetime.utcnow()
        db.session.commit()
        return True
    except Exception as e:
        current_app.logger.exception(f"Error checking source '{source.name}': {e}")
        # Still update last_checked to avoid hot-looping on failures
        source.last_checked = datetime.utcnow()
        db.session.commit()
        return False

