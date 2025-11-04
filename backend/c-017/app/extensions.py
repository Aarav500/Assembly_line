from authlib.integrations.flask_client import OAuth
from flask_sqlalchemy import SQLAlchemy
from flask import current_app


db = SQLAlchemy()
oauth = OAuth()


def register_oauth_clients(app):
    # Google (OIDC)
    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    # GitHub (OAuth2)
    if app.config.get("GITHUB_CLIENT_ID") and app.config.get("GITHUB_CLIENT_SECRET"):
        oauth.register(
            name="github",
            client_id=app.config["GITHUB_CLIENT_ID"],
            client_secret=app.config["GITHUB_CLIENT_SECRET"],
            api_base_url="https://api.github.com/",
            access_token_url="https://github.com/login/oauth/access_token",
            authorize_url="https://github.com/login/oauth/authorize",
            client_kwargs={"scope": "read:user user:email"},
        )

    # Generic OIDC (e.g., Okta, Azure AD)
    if app.config.get("OIDC_CLIENT_ID") and app.config.get("OIDC_CLIENT_SECRET") and app.config.get("OIDC_SERVER_METADATA_URL"):
        oauth.register(
            name="oidc",
            client_id=app.config["OIDC_CLIENT_ID"],
            client_secret=app.config["OIDC_CLIENT_SECRET"],
            server_metadata_url=app.config["OIDC_SERVER_METADATA_URL"],
            client_kwargs={"scope": "openid email profile"},
        )

