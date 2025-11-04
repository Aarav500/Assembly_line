import os
from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    # When eventlet is installed, SocketIO will use it automatically.
    socketio.run(app, host="0.0.0.0", port=port)

