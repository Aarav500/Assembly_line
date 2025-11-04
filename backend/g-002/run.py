import os
from threading import Event
from time import sleep

from app import app
import db
from orchestrator import Orchestrator


if __name__ == "__main__":
    db.init_db()
    orch = Orchestrator()
    orch.start()
    try:
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False, use_reloader=False)
    finally:
        orch.stop()
        orch.join()

