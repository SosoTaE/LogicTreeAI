"""
Central logging configuration.

Logs go to stderr and to a rotating file at logs/app.log.
Set LOG_LEVEL=DEBUG in the environment for verbose output.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'app.log')

_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
_DATEFMT = '%Y-%m-%d %H:%M:%S'

_configured = False


def setup_logging(level=None):
    """Configure root logging. Idempotent."""
    global _configured
    if _configured:
        return

    level_name = level or os.environ.get('LOG_LEVEL', 'INFO')
    level_value = getattr(logging, level_name.upper(), logging.INFO)

    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_048_576,   # 1 MiB
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level_value)
    # Remove any pre-existing handlers (e.g. from Flask reloader) to avoid dupes
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Quiet overly chatty third-party loggers
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    _configured = True
    logging.getLogger(__name__).info(
        "Logging initialized (level=%s, file=%s)", level_name.upper(), LOG_FILE
    )
