from devtools import dev_command
from app import create_app


@dev_command(help="Run the Flask development server.")
def runserver(host: str = "127.0.0.1", port: int = 5000, reload: bool = True, debug: bool = True):
    app = create_app()
    # Werkzeug dev server with reloader control
    app.run(host=host, port=port, debug=debug, use_reloader=reload)

