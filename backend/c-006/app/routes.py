from flask import jsonify, request, Blueprint
from .extensions import db
from .models import User, Post


def register_routes(app):
    api = Blueprint("api", __name__)

    @api.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @api.get("/users")
    def list_users():
        users = User.query.order_by(User.id.asc()).all()
        return jsonify(
            [
                {
                    "id": u.id,
                    "email": u.email,
                    "name": u.name,
                    "created_at": u.created_at.isoformat(),
                    "posts_count": len(u.posts),
                }
                for u in users
            ]
        )

    @api.post("/users")
    def create_user():
        data = request.get_json(force=True) or {}
        email = data.get("email")
        name = data.get("name")
        if not email or not name:
            return jsonify({"error": "email and name are required"}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "email already exists"}), 409
        user = User(email=email, name=name)
        db.session.add(user)
        db.session.commit()
        return jsonify({"id": user.id, "email": user.email, "name": user.name}), 201

    @api.post("/posts")
    def create_post():
        data = request.get_json(force=True) or {}
        user_id = data.get("user_id")
        title = data.get("title")
        body = data.get("body")
        if not user_id or not title or not body:
            return jsonify({"error": "user_id, title, and body are required"}), 400
        if not User.query.get(user_id):
            return jsonify({"error": "user not found"}), 404
        post = Post(user_id=user_id, title=title, body=body)
        db.session.add(post)
        db.session.commit()
        return jsonify({"id": post.id, "user_id": post.user_id, "title": post.title}), 201

    app.register_blueprint(api, url_prefix="/api")

