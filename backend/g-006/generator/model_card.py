import os
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_env():
    here = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(os.path.dirname(here), "templates")
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(enabled_extensions=(".j2",))
    )
    return env


def generate_model_card(model_record: dict, compliance: dict) -> str:
    env = _template_env()
    try:
        template = env.get_template("model_card.md.j2")
    except Exception:
        # Fallback minimal template
        return f"""
# Model Card: {model_record.get('name')} ({model_record.get('version')})

Description: {model_record.get('description')}

Intended Use: {model_record.get('intended_use')}

Model Details: {model_record.get('model_details')}

Training Data: {model_record.get('training_data')}

Evaluation: {model_record.get('evaluation')}

Risk Management: {model_record.get('risk_management')}

Deployment: {model_record.get('deployment')}

Compliance (summary): {compliance.get('risk_assessment', {})}
"""
    content = template.render(model=model_record, compliance=compliance)
    return content

