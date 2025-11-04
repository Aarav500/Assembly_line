import json
import logging
import sys
from typing import Optional


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "level": record.levelname,
            "message": record.getMessage() if isinstance(record.msg, str) else record.msg,
            "logger": record.name,
        }
        if isinstance(record.msg, dict):
            data.update(record.msg)
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


def get_logger(name: str, level: str = "INFO", json_output: bool = True, file_path: Optional[str] = None):
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers = []

    handler = logging.FileHandler(file_path) if file_path else logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger

