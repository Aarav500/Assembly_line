import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, render_template_string
from flask_babel import Babel, gettext

app = Flask(__name__)
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
app.config['SECRET_KEY'] = 'dev-secret-key'

babel = Babel(app)

@babel.localeselector
def get_locale():
    return request.args.get('lang') or request.accept_languages.best_match(['en', 'es', 'fr'])

@app.route('/')
def index():
    welcome = gettext('Welcome')
    message = gettext('Hello, World!')
    template = '<h1>{{ welcome }}</h1><p>{{ message }}</p>'
    return render_template_string(template, welcome=welcome, message=message)

@app.route('/greeting/<name>')
def greeting(name):
    message = gettext('Hello, %(name)s!', name=name)
    return {'message': message}

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app


@app.route('/?lang=es', methods=['GET'])
def _auto_stub_lang_es():
    return 'Auto-generated stub for /?lang=es', 200


@app.route('/greeting/John', methods=['GET'])
def _auto_stub_greeting_John():
    return 'Auto-generated stub for /greeting/John', 200
