import os
from flask import Flask, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .config import Config
from .models import Base, Artifact, ArtifactTag, Module
from .storage import Storage
from .utils import (
    compute_stream_sha256_to_tempfile,
    validate_name,
    validate_tag,
    is_valid_sha256,
    parse_semver,
)
from .auth import require_token
from datetime import datetime


def create_app(config: Config | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping({})

    cfg = config or Config.from_env()
    app.config["REGISTRY_TOKEN"] = cfg.REGISTRY_TOKEN

    # Database setup
    engine = create_engine(cfg.DATABASE_URL, future=True)
    Base.metadata.create_all(engine)
    Session = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))

    # Storage setup
    storage = Storage(cfg.DATA_DIR)

    @app.teardown_appcontext
    def remove_session(exception=None):
        Session.remove()

    def _artifact_response(artifact: Artifact):
        return {
            "id": artifact.id,
            "name": artifact.name,
            "hash": artifact.hash,
            "size": artifact.size,
            "content_type": artifact.content_type,
            "filename": artifact.filename,
            "created_at": artifact.created_at.isoformat(),
            "download_url": f"/artifacts/{artifact.name}/{artifact.hash}",
        }

    def _tag_response(tag: ArtifactTag):
        return {
            "id": tag.id,
            "artifact_name": tag.artifact_name,
            "tag": tag.tag,
            "hash": tag.artifact.hash if tag.artifact else None,
            "artifact_id": tag.artifact_id,
            "created_at": tag.created_at.isoformat(),
            "download_url": f"/artifacts/{tag.artifact_name}/tags/{tag.tag}",
        }

    def _module_response(module: Module):
        return {
            "id": module.id,
            "name": module.name,
            "version": module.version,
            "size": module.size,
            "content_type": module.content_type,
            "filename": module.filename,
            "created_at": module.created_at.isoformat(),
            "metadata": module.metadata or {},
            "download_url": f"/modules/{module.name}/{module.version}",
        }

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request", "message": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "unauthorized", "message": str(e)}), 401

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": "resource not found"}), 404

    @app.errorhandler(409)
    def conflict(e):
        return jsonify({"error": "conflict", "message": str(e)}), 409

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})

    # Artifacts
    @app.post("/artifacts")
    @require_token
    def upload_artifact():
        sess = Session()
        name = request.form.get("name", "").strip()
        tag = request.form.get("tag", "").strip() or None
        file = request.files.get("file")
        if not name or not file:
            abort(400, description="name and file are required")
        if not validate_name(name):
            abort(400, description="invalid artifact name")
        if tag and not validate_tag(tag):
            abort(400, description="invalid tag")

        filename = secure_filename(file.filename or "artifact.bin")
        content_type = file.mimetype or "application/octet-stream"

        # Write to temp file and compute hash
        tmp_path, size, sha256_hex = compute_stream_sha256_to_tempfile(file.stream)
        try:
            # Ensure directory and final path
            final_path = storage.artifact_blob_path(name, sha256_hex)
            if not os.path.exists(final_path):
                storage.install_tempfile(tmp_path, final_path)
            else:
                # Already exists; remove temp file
                os.remove(tmp_path)
        except Exception:
            # cleanup temp
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise

        # Upsert artifact row if not exists (name+hash unique)
        existing = (
            sess.query(Artifact)
            .filter(Artifact.name == name, Artifact.hash == sha256_hex)
            .one_or_none()
        )
        if existing is None:
            artifact = Artifact(
                name=name,
                hash=sha256_hex,
                size=size,
                content_type=content_type,
                filename=filename,
                path=final_path,
            )
            sess.add(artifact)
            sess.commit()
        else:
            artifact = existing

        tag_obj = None
        if tag:
            # tag immutability: if tag exists must point to same artifact
            existing_tag = (
                sess.query(ArtifactTag)
                .filter(ArtifactTag.artifact_name == name, ArtifactTag.tag == tag)
                .one_or_none()
            )
            if existing_tag is None:
                tag_obj = ArtifactTag(artifact_id=artifact.id, artifact_name=name, tag=tag)
                sess.add(tag_obj)
                sess.commit()
            else:
                if existing_tag.artifact_id != artifact.id:
                    abort(409, description="tag already exists and points to a different artifact")
                tag_obj = existing_tag

        resp = _artifact_response(artifact)
        if tag_obj is not None:
            resp["tag"] = tag_obj.tag
        return jsonify(resp), 201

    @app.get("/artifacts/<string:name>")
    def list_artifacts(name: str):
        if not validate_name(name):
            abort(400, description="invalid artifact name")
        sess = Session()
        rows = (
            sess.query(Artifact)
            .filter(Artifact.name == name)
            .order_by(Artifact.created_at.desc())
            .all()
        )
        return jsonify([_artifact_response(a) for a in rows])

    @app.get("/artifacts/<string:name>/<string:hash_hex>")
    def download_artifact(name: str, hash_hex: str):
        if not validate_name(name) or not is_valid_sha256(hash_hex):
            abort(400, description="invalid parameters")
        sess = Session()
        artifact = (
            sess.query(Artifact)
            .filter(Artifact.name == name, Artifact.hash == hash_hex)
            .one_or_none()
        )
        if artifact is None:
            abort(404)
        if not os.path.exists(artifact.path):
            abort(404)
        return send_file(
            artifact.path,
            mimetype=artifact.content_type or "application/octet-stream",
            as_attachment=True,
            download_name=artifact.filename or f"{artifact.hash}",
            conditional=True,
        )

    @app.post("/artifacts/<string:name>/tags")
    @require_token
    def create_tag(name: str):
        if not validate_name(name):
            abort(400, description="invalid artifact name")
        data = request.get_json(silent=True) or {}
        tag = (data.get("tag") or "").strip()
        hash_hex = (data.get("hash") or "").strip()
        if not validate_tag(tag) or not is_valid_sha256(hash_hex):
            abort(400, description="invalid tag or hash")
        sess = Session()
        artifact = (
            sess.query(Artifact)
            .filter(Artifact.name == name, Artifact.hash == hash_hex)
            .one_or_none()
        )
        if artifact is None:
            abort(404)
        existing = (
            sess.query(ArtifactTag)
            .filter(ArtifactTag.artifact_name == name, ArtifactTag.tag == tag)
            .one_or_none()
        )
        if existing is None:
            tag_obj = ArtifactTag(artifact_id=artifact.id, artifact_name=name, tag=tag)
            sess.add(tag_obj)
            sess.commit()
        else:
            if existing.artifact_id != artifact.id:
                abort(409, description="tag already exists and points to a different artifact")
            tag_obj = existing
        return jsonify(_tag_response(tag_obj)), 201

    @app.get("/artifacts/<string:name>/tags")
    def list_tags(name: str):
        if not validate_name(name):
            abort(400, description="invalid artifact name")
        sess = Session()
        rows = (
            sess.query(ArtifactTag)
            .filter(ArtifactTag.artifact_name == name)
            .order_by(ArtifactTag.created_at.desc())
            .all()
        )
        return jsonify([_tag_response(t) for t in rows])

    @app.get("/artifacts/<string:name>/tags/<string:tag>")
    def download_by_tag(name: str, tag: str):
        if not validate_name(name) or not validate_tag(tag):
            abort(400, description="invalid parameters")
        sess = Session()
        tag_obj = (
            sess.query(ArtifactTag)
            .filter(ArtifactTag.artifact_name == name, ArtifactTag.tag == tag)
            .one_or_none()
        )
        if tag_obj is None or tag_obj.artifact is None:
            abort(404)
        artifact = tag_obj.artifact
        if not os.path.exists(artifact.path):
            abort(404)
        return send_file(
            artifact.path,
            mimetype=artifact.content_type or "application/octet-stream",
            as_attachment=True,
            download_name=artifact.filename or f"{artifact.hash}",
            conditional=True,
        )

    # Modules
    @app.post("/modules/<string:name>/<string:version>")
    @require_token
    def upload_module(name: str, version: str):
        if not validate_name(name):
            abort(400, description="invalid module name")
        semver_info = parse_semver(version)
        if semver_info is None:
            abort(400, description="invalid semantic version")
        file = request.files.get("file")
        if not file:
            abort(400, description="file is required")
        filename = secure_filename(file.filename or f"{name}-{version}.bin")
        content_type = file.mimetype or "application/octet-stream"

        sess = Session()
        existing = (
            sess.query(Module)
            .filter(Module.name == name, Module.version == version)
            .one_or_none()
        )
        if existing is not None:
            abort(409, description="module version already exists (immutable)")

        tmp_path, size, sha256_hex = compute_stream_sha256_to_tempfile(file.stream)
        try:
            final_path = storage.module_blob_path(name, version, filename)
            if os.path.exists(final_path):
                # This should not happen as DB would also exist, but guard
                abort(409, description="module artifact already exists on disk")
            storage.install_tempfile(tmp_path, final_path)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise

        module = Module(
            name=name,
            version=version,
            size=size,
            content_type=content_type,
            filename=filename,
            path=final_path,
            sha256=sha256_hex,
            semver_major=semver_info["major"],
            semver_minor=semver_info["minor"],
            semver_patch=semver_info["patch"],
            semver_prerelease=semver_info.get("prerelease"),
            semver_build=semver_info.get("build"),
            metadata=(request.form.get("metadata") if request.form.get("metadata") else None),
        )
        sess.add(module)
        sess.commit()
        return jsonify(_module_response(module)), 201

    @app.get("/modules")
    def list_modules():
        sess = Session()
        rows = sess.query(Module.name).distinct().order_by(Module.name.asc()).all()
        names = [r[0] for r in rows]
        return jsonify(names)

    @app.get("/modules/<string:name>")
    def list_module_versions(name: str):
        if not validate_name(name):
            abort(400, description="invalid module name")
        sess = Session()
        rows = (
            sess.query(Module)
            .filter(Module.name == name)
            .order_by(
                Module.semver_major.desc(),
                Module.semver_minor.desc(),
                Module.semver_patch.desc(),
                Module.semver_prerelease.is_(None).desc(),
                Module.semver_prerelease.desc(),
            )
            .all()
        )
        return jsonify([_module_response(m) for m in rows])

    @app.get("/modules/<string:name>/<string:version>")
    def download_module(name: str, version: str):
        if not validate_name(name):
            abort(400, description="invalid module name")
        if parse_semver(version) is None:
            abort(400, description="invalid semantic version")
        sess = Session()
        module = (
            sess.query(Module)
            .filter(Module.name == name, Module.version == version)
            .one_or_none()
        )
        if module is None:
            abort(404)
        if not os.path.exists(module.path):
            abort(404)
        headers = {"X-Content-SHA256": module.sha256}
        return send_file(
            module.path,
            mimetype=module.content_type or "application/octet-stream",
            as_attachment=True,
            download_name=module.filename or f"{name}-{version}",
            conditional=True,
            headers=headers,
        )

    return app

