import re


def slugify(value: str, allow_unicode: bool = False) -> str:
    value = str(value)
    if allow_unicode:
        value = re.sub(r"\s+", "-", value)
        value = re.sub(r"[^\w\-]", "", value)
    else:
        value = value.encode("ascii", "ignore").decode("ascii")
        value = re.sub(r"[^\w\s-]", "", value).strip().lower()
        value = re.sub(r"[-\s]+", "-", value)
    return value

