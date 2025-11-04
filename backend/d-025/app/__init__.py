import os
import requests
from flask import Flask, jsonify


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.setdefault("GITHUB_API_BASE", "https://api.github.com")

    @app.route("/github/<username>")
    def github_user(username):
        try:
            data = fetch_github_user(username, api_base=app.config["GITHUB_API_BASE"])
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                return jsonify({"error": "User not found"}), 404
            return jsonify({"error": "Upstream error", "status_code": status}), 502
        except requests.RequestException:
            return jsonify({"error": "Network error"}), 502

        result = {
            "login": data.get("login"),
            "id": data.get("id"),
            "name": data.get("name"),
            "public_repos": data.get("public_repos"),
            "followers": data.get("followers"),
        }
        return jsonify(result)

    return app


def fetch_github_user(username: str, api_base: str = "https://api.github.com"):
    url = f"{api_base}/users/{username}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "integration-tests-demo/1.0",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

