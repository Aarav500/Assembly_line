import io
import os
import re
import zipfile
from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')

def jinja_env():
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(enabled_extensions=('j2',), default_for_string=False)
    )
    # filters
    env.filters['k8s_name'] = sanitize_name
    return env


def render_to_file(template_path: str, out_path: str, context: dict):
    env = jinja_env()
    template = env.get_template(template_path)
    content = template.render(**context)
    ensure_dir(os.path.dirname(out_path))
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)


def ensure_dir(path: str):
    if not path:
        return
    os.makedirs(path, exist_ok=True)


def sanitize_name(name: str) -> str:
    if not name:
        return ''
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9-]+', '-', s)
    s = re.sub(r'-{2,}', '-', s)
    s = s.strip('-')
    return s[:63]


def create_zip_from_dir(source_dir: str, fileobj: io.BytesIO):
    with zipfile.ZipFile(fileobj, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, start=source_dir)
                zipf.write(full_path, arcname)


def to_env_list(env_dict: dict):
    if not env_dict:
        return []
    return [{"name": k, "value": str(v)} for k, v in env_dict.items()]


def default(val, fallback):
    return val if val is not None else fallback

