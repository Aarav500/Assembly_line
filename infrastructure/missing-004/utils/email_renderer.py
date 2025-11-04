from jinja2 import Environment, FileSystemLoader, select_autoescape
from config import settings

loader = FileSystemLoader(settings.TEMPLATE_FOLDER)
env = Environment(loader=loader, autoescape=select_autoescape(["html", "xml"]))


def render_templates(template_name: str, context: dict):
    # Expecting template_name.[html|txt].j2
    html_template_name = f"{template_name}.html.j2"
    txt_template_name = f"{template_name}.txt.j2"

    template_html = env.get_template(html_template_name)
    template_txt = env.get_template(txt_template_name)

    html_body = template_html.render(**context)
    text_body = template_txt.render(**context)

    return html_body, text_body

