from flask import jsonify


def register_routes(app):
    @app.route("/health")
    def health():
        return jsonify(status="ok", region=app.config.get("REGION")), 200

    @app.route("/region")
    def region():
        return (
            jsonify(
                region=app.config.get("REGION"),
                greeting=app.config.get("GREETING"),
                cdn_url=app.config.get("CDN_URL"),
                app=app.config.get("APP_NAME"),
            ),
            200,
        )

    @app.route("/")
    def index():
        return jsonify(
            message=f"{app.config.get('GREETING')} from {app.config.get('REGION')}"
        )

