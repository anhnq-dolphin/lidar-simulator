import logging
import sys
from typing import Any

LOGGER_NAME = "lidar_middleware"


def _build_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = _build_logger()


def log_info(message: str, *args: Any, **kwargs: Any) -> None:
    logger.info(message, *args, **kwargs)


def log_error(message: str, *args: Any, **kwargs: Any) -> None:
    logger.error(message, *args, **kwargs)


def log_debug(message: str, *args: Any, **kwargs: Any) -> None:
    logger.debug(message, *args, **kwargs)
