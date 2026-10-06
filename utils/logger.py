from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | "
    "%(name)s | %(message)s"
)


def setup_logging(
    log_dir: Path,
    level: int = logging.INFO,
) -> Path:
    """Configure console and file logging."""
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = (
        log_dir
        / f"scrape_{datetime.now():%Y%m%d_%H%M%S}.log"
    )

    logger = logging.getLogger()
    logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT)

    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return log_file