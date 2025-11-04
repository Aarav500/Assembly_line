from flask import jsonify

class APIError(Exception):
    def __init__(self, message, status_code=400, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details

    def to_response(self):
        payload = {"error": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return jsonify(payload), self.status_code


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return err.to_response()

    @app.errorhandler(404)
    def handle_404(err):
        return jsonify({"error": "Not Found"}), 404

    @app.errorhandler(405)
    def handle_405(err):
        return jsonify({"error": "Method Not Allowed"}), 405

    @app.errorhandler(500)
    def handle_500(err):
        return jsonify({"error": "Internal Server Error"}), 500

