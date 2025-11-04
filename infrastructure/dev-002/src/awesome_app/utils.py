from __future__ import annotations

from typing import Any


def add(a: int, b: int) -> int:
    """Add two integers and return the sum.

    Args:
        a: First integer.
        b: Second integer.

    Returns:
        The sum of a and b.
    """
    return a + b


def stringify(value: Any) -> str:
    """Return a string representation of value.

    Primarily here to demonstrate type checking on broader types.
    """
    return str(value)

