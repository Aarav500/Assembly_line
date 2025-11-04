import code

from devtools import dev_command
from app import create_app


@dev_command(help="Open an interactive shell with Flask app context")
def shell():
    app = create_app()
    banner = "Flask shell. Available: app, ctx"
    with app.app_context():
        ctx = app.app_context()
        local_vars = {"app": app, "ctx": ctx}
        code.interact(banner=banner, local=local_vars)

