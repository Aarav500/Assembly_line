import logging
import logging.config
import sys

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        },
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'default',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': 'app.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
    },
    'loggers': {
        '': {
            'level': 'INFO',
            'handlers': ['console', 'file'],
        },
    },
}

def setup_logging():
    try:
        logging.config.dictConfig(LOGGING_CONFIG)
    except (ValueError, TypeError, AttributeError, ImportError) as e:
        # Fallback to basic configuration if dictConfig fails
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        logging.error(f"Failed to configure logging from dict: {e}")
    except Exception as e:
        # Catch any other unexpected errors
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Unexpected error during logging setup: {e}")