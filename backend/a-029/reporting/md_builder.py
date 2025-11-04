from pathlib import Path
from typing import Dict, Any
import jinja2
from .utils import format_currency, percent


def _env() -> jinja2.Environment:
    templates_dir = Path(__file__).resolve().parent.parent / "templates"
    env = jinja2.Environment(  # nosec - trusted templates included in package
        loader=jinja2.FileSystemLoader(str(templates_dir)), autoescape=False, trim_blocks=True, lstrip_blocks=True
    )
    env.filters["currency"] = format_currency
    env.filters["percent"] = percent
    return env


def build_markdown_report(data: Dict[str, Any]) -> str:
    env = _env()
    tmpl = env.get_template("report.md.j2")
    content = tmpl.render(data=data)
    return content

