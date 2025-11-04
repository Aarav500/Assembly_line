from flask import Flask
from .users.api import bp as users_bp
from .orders.api import bp as orders_bp

app = Flask(__name__)
app.register_blueprint(users_bp)
app.register_blueprint(orders_bp)

@app.route('/')
def index():
    return 'ok'

