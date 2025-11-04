import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify, redirect, url_for
from extensions import db
from models import Project, ProjectFeature, Idea
from services.conversion import convert_project_to_idea
import os


def create_app():
    app = Flask(__name__)

    db_uri = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route("/")
    def root():
        return redirect(url_for("list_projects"))

    @app.route("/projects")
    def list_projects():
        projects = Project.query.order_by(Project.created_at.desc()).all()
        return render_template("projects.html", projects=projects)

    @app.route("/projects/<int:project_id>/convert", methods=["POST"]) 
    def convert_project(project_id: int):
        idea, created = convert_project_to_idea(project_id)
        if not idea:
            return jsonify({"ok": False, "error": "Project not found"}), 404
        return jsonify({
            "ok": True,
            "created": created,
            "idea_id": idea.id,
            "redirect_url": url_for("view_idea", idea_id=idea.id)
        })

    @app.route("/ideas/<int:idea_id>")
    def view_idea(idea_id: int):
        idea = Idea.query.get_or_404(idea_id)
        return render_template("idea.html", idea=idea)

    @app.route("/seed")
    def seed():
        # Create some sample data if none exists
        if Project.query.count() == 0:
            from models import Tag
            p1 = Project(name="Alpha CRM", description="A customer relationship management tool.", status="active")
            p1.tags = [Tag.ensure("crm"), Tag.ensure("b2b")]
            p1.features = [
                ProjectFeature(name="Contact Management", description="Store and manage customer contacts", priority="High"),
                ProjectFeature(name="Pipeline", description="Sales pipeline with stages", priority="Medium"),
                ProjectFeature(name="Reports", description="Generate sales performance reports", priority="Low"),
            ]

            p2 = Project(name="Foodie App", description="Food delivery aggregator.", status="paused")
            p2.tags = [Tag.ensure("mobile"), Tag.ensure("consumer")]
            p2.features = [
                ProjectFeature(name="Restaurant Search", description="Search by cuisine and rating", priority="High"),
                ProjectFeature(name="Order Tracking", description="Live tracking of orders", priority="High"),
            ]

            db.session.add_all([p1, p2])
            db.session.commit()
        return redirect(url_for("list_projects"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

