from flask import Flask, request, redirect, url_for, make_response, render_template, current_app
from flask_babel import Babel, gettext as _

babel = Babel()


def create_app():
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY='dev',
        BABEL_DEFAULT_LOCALE='en',
        BABEL_DEFAULT_TIMEZONE='UTC',
        # Supported languages for this app
        LANGUAGES=['en', 'es', 'fr']
    )

    babel.init_app(app, locale_selector=_select_locale, timezone_selector=_select_timezone)

    @app.context_processor
    def inject_globals():
        # Expose supported languages and current locale to templates
        return {
            'LANGUAGES': app.config.get('LANGUAGES', ['en']),
            'current_locale': str(_select_locale())
        }

    @app.route('/')
    def index():
        # Example title uses gettext for extraction
        return render_template('index.html', title=_('Home Page'))

    @app.route('/set-lang/<lang_code>')
    def set_language(lang_code):
        if lang_code not in current_app.config.get('LANGUAGES', []):
            # Fallback silently to index if unsupported
            return redirect(url_for('index'))
        resp = make_response(redirect(url_for('index')))
        # Persist language preference for 1 year
        resp.set_cookie('lang', lang_code, max_age=60 * 60 * 24 * 365, httponly=False, samesite='Lax')
        return resp

    return app


def _select_locale():
    # Priority: ?lang -> cookie -> Accept-Language -> default
    lang = request.args.get('lang')
    if lang and lang in current_app.config.get('LANGUAGES', []):
        return lang
    lang = request.cookies.get('lang')
    if lang and lang in current_app.config.get('LANGUAGES', []):
        return lang
    return request.accept_languages.best_match(current_app.config.get('LANGUAGES', ['en'])) or current_app.config.get('BABEL_DEFAULT_LOCALE', 'en')


def _select_timezone():
    # Could be extended to read from user profile
    return current_app.config.get('BABEL_DEFAULT_TIMEZONE', 'UTC')

