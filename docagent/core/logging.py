"""Structured logging configuration for DocAgent."""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "docagent",
    level: str = "INFO",
    log_format: Optional[str] = None
) -> logging.Logger:
    """Configures a standardized structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Prevent duplicate handlers if already attached
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        fmt = log_format or (
            "[%(asctime)s] [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d] - %(message)s"
        )
        formatter = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()
