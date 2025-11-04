import inspect
from typing import Any, Callable, Dict


def _normalize_command_name(name: str) -> str:
    return name.replace("_", "-").lower()


def dev_command(name: str | None = None, help: str | None = None):
    """
    Decorator to mark a function as a dev command.
    - name: optional CLI name (defaults to function name with dashes)
    - help: optional help string (defaults to function docstring)
    Function parameters are converted into CLI parameters automatically:
      - Required parameters -> positional arguments
      - Optional parameters -> --option options
      - bool parameters -> --flag/--no-flag
      - Types inferred from annotations: int, float, str. Otherwise str.
    """
    def _decorator(func: Callable[..., Any]):
        meta = {
            "name": _normalize_command_name(name or func.__name__),
            "help": (help or (func.__doc__ or "")).strip(),
            "signature": inspect.signature(func),
        }
        setattr(func, "_dev_meta", meta)
        return func

    return _decorator

