import argparse
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATIONS_DIR = os.path.join(BASE_DIR, 'app', 'translations')
POT_FILE = os.path.join(BASE_DIR, 'messages.pot')
BABEL_CFG = os.path.join(BASE_DIR, 'babel.cfg')


def run(cmd):
    print('> ' + ' '.join(cmd))
    subprocess.run(cmd, check=True)


def ensure_dirs():
    os.makedirs(TRANSLATIONS_DIR, exist_ok=True)


def cmd_extract(args):
    ensure_dirs()
    run([
        sys.executable.replace('pythonw', 'python'), '-m', 'babel.messages.frontend', 'extract',
        '-F', BABEL_CFG,
        '-k', '_',
        '-k', '_l',
        '-o', POT_FILE,
        BASE_DIR
    ])


def cmd_init(args):
    ensure_dirs()
    if not os.path.exists(POT_FILE):
        cmd_extract(args)
    for lang in args.langs:
        run([
            sys.executable.replace('pythonw', 'python'), '-m', 'babel.messages.frontend', 'init',
            '-i', POT_FILE,
            '-d', TRANSLATIONS_DIR,
            '-l', lang
        ])


def cmd_update(args):
    ensure_dirs()
    if not os.path.exists(POT_FILE):
        cmd_extract(args)
    run([sys.executable.replace('pythonw', 'python'), '-m', 'babel.messages.frontend', 'update', '-i', POT_FILE, '-d', TRANSLATIONS_DIR])


def cmd_compile(args):
    ensure_dirs()
    run([sys.executable.replace('pythonw', 'python'), '-m', 'babel.messages.frontend', 'compile', '-d', TRANSLATIONS_DIR])


def main():
    parser = argparse.ArgumentParser(description='i18n helper for Flask-Babel')
    sub = parser.add_subparsers(dest='command', required=True)

    p_extract = sub.add_parser('extract', help='Extract messages to POT file')
    p_extract.set_defaults(func=cmd_extract)

    p_init = sub.add_parser('init', help='Initialize a new language (creates .po)')
    p_init.add_argument('langs', nargs='+', help='Language codes to initialize, e.g. en es fr')
    p_init.set_defaults(func=cmd_init)

    p_update = sub.add_parser('update', help='Update all .po files from POT')
    p_update.set_defaults(func=cmd_update)

    p_compile = sub.add_parser('compile', help='Compile .po to .mo')
    p_compile.set_defaults(func=cmd_compile)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
