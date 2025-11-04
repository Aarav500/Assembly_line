import secrets
import string
from typing import Optional


def generate_secret(length: int = 32, alphabet: Optional[str] = None) -> str:
    if length <= 0:
        length = 1
    if alphabet is None:
        # URL-safe without ambiguous characters
        alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))

