"""Awesome App package.

Includes a small utility function and is configured for:
- Ruff linting
- Black formatting
- Mypy type checking
- Fast unit tests via pytest
"""

from .utils import add

__all__ = ["add"]
__version__ = "0.1.0"

