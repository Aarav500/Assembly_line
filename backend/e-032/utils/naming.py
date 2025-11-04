import re

def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9-]", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")

