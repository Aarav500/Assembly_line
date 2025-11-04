import re
import unicodedata

def slugify(value: str, separator: str = "-") -> str:
    if not value:
        return "project"
    value = str(value)
    value = unicodedata.normalize('NFKD', value)
    value = value.encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r"[^a-zA-Z0-9\-\_\s]+", "", value)
    value = value.strip().lower()
    value = re.sub(r"[\s\-\_]+", separator, value)
    value = value.strip(separator)
    return value or "project"

