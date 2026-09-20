"""Central file logging and bounded retry helpers."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TypeVar

ResultT = TypeVar("ResultT")


def configure_logging(log_path: str | Path = "logs/app.log") -> None:
    """Configure one rotating UTF-8 application log on the root logger."""

    path = Path(log_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == path
        for handler in root.handlers
    ):
        return
    handler = RotatingFileHandler(
        path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def retry_call(
    operation: Callable[[], ResultT],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 1.0,
    operation_name: str = "operation",
    sleep: Callable[[float], None] = time.sleep,
) -> ResultT:
    """Retry a transient operation with bounded exponential backoff."""

    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    logger = logging.getLogger(__name__)
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception:
            if attempt == attempts:
                logger.exception("%s failed after %d attempt(s)", operation_name, attempt)
                raise
            delay = base_delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "%s attempt %d/%d failed; retrying in %.2f seconds",
                operation_name,
                attempt,
                attempts,
                delay,
                exc_info=True,
            )
            sleep(delay)
    raise RuntimeError("unreachable")
