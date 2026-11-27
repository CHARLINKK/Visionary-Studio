import os
import logging
from logging.handlers import RotatingFileHandler
from src.config import get_app_data_dir

_loggers = {}

def get_logger(name: str) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]

    log_dir = os.path.join(get_app_data_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Determine filename based on name (e.g. 'pipeline' -> 'debug_pipeline.log')
    # Use crash.log for general dev/error logs
    if name == "pipeline":
        filename = "debug_pipeline.log"
    elif name == "teleport":
        filename = "teleport_debug.log"
    else:
        filename = "crash.log"

    log_path = os.path.join(log_dir, filename)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Evita que logs se repitam se houver mÃºltiplos handlers
    if not logger.handlers:
        # Rotation: max 5MB per file, keep 3 backups
        handler = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _loggers[name] = logger
    return logger
