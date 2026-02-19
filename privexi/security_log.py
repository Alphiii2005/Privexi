"""
modules/security_log.py
Logs security events without logging any secrets.
"""

import logging
import time
from pathlib import Path

LOG_PATH = Path.home() / ".secure_vault" / "security.log"


def setup_logger() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("SecureVault")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


_logger = setup_logger()


def log_event(event: str, details: str = ""):
    """Log a security event. Never include passwords or keys."""
    _logger.info(f"{event}" + (f" | {details}" if details else ""))


def log_warning(event: str, details: str = ""):
    _logger.warning(f"{event}" + (f" | {details}" if details else ""))


def log_failure(event: str, details: str = ""):
    _logger.error(f"{event}" + (f" | {details}" if details else ""))
