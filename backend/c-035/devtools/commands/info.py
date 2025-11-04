import platform

import flask

from devtools import dev_command
from app import create_app


@dev_command(help="Show project and environment info")
def info():
    app = create_app()
    print("Project Info:")
    print(f" - Project Name: {app.config.get('PROJECT_NAME')}")
    print(f" - Flask: {flask.__version__}")
    print(f" - Python: {platform.python_version()} ({platform.python_implementation()})")
    print(f" - Working Dir: {os.getcwd()}")

