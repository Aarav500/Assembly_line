from .py_to_js import transpile as py_to_js
from .js_to_py import transpile as js_to_py


_LANG_ALIASES = {
    'python': 'python', 'py': 'python',
    'javascript': 'javascript', 'js': 'javascript', 'node': 'javascript'
}


def normalize_lang(name: str) -> str:
    key = (name or '').strip().lower()
    if key in _LANG_ALIASES:
        return _LANG_ALIASES[key]
    raise ValueError(f'Unsupported language: {name}')


def supported_languages():
    return ['python', 'javascript']


def transpile(source_lang: str, target_lang: str, code: str):
    s = normalize_lang(source_lang)
    t = normalize_lang(target_lang)
    if s == t:
        return code, []

    if s == 'python' and t == 'javascript':
        return py_to_js(code)
    if s == 'javascript' and t == 'python':
        return js_to_py(code)

    raise ValueError(f'Transpilation from {s} to {t} is not supported yet.')

