"""Application-scoped logging with idempotent handler configuration."""

import logging
from threading import RLock

_SETUP_LOCK = RLock()


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the FinHealth logger without duplicate handlers."""
    normalized_level = level.strip().upper()
    numeric_level = getattr(logging, normalized_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid logging level: {level!r}")

    logger = logging.getLogger("finhealth")
    with _SETUP_LOCK:
        handler = next(
            (item for item in logger.handlers if item.get_name() == "finhealth.console"),
            None,
        )
        if handler is None:
            handler = logging.StreamHandler()
            handler.set_name("finhealth.console")
            logger.addHandler(handler)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(name)s | %(module)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        handler.setLevel(numeric_level)
        logger.setLevel(numeric_level)
        logger.propagate = False
    return logger
