"""Duplicate detection using normalized record keys."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from models.record import Record

logger = logging.getLogger(__name__)

NON_ALNUM = re.compile(r"[^0-9a-z]+")


def normalize_key_text(value: str | None) -> str:
    """Normalize text for duplicate comparison."""
    if not value:
        return ""

    decomposed = unicodedata.normalize(
        "NFKD",
        value,
    )

    without_accents = "".join(
        char
        for char in decomposed
        if not unicodedata.combining(char)
    )

    return NON_ALNUM.sub(
        " ",
        without_accents.casefold(),
    ).strip()


def duplicate_key(
    record: Record,
) -> tuple[str, str, str, float | None]:
    """Build the normalized key used for duplicate detection."""
    price = (
        round(record.price, 2)
        if isinstance(record.price, (int, float))
        else None
    )

    return (
        record.source or "",
        normalize_key_text(record.name_or_title),
        normalize_key_text(record.author),
        price,
    )


@dataclass
class DeduplicationResult:
    unique: list[Record] = field(default_factory=list)
    duplicates: list[Record] = field(default_factory=list)

    @property
    def detected(self) -> int:
        return len(self.duplicates)


def deduplicate(
    records: list[Record],
) -> DeduplicationResult:
    """Keep the first occurrence and report later duplicates."""
    result = DeduplicationResult()
    seen: set[tuple[str, str, str, float | None]] = set()

    for record in records:
        key = duplicate_key(record)

        if key in seen:
            logger.info(
                "Duplicate detected: %r (%s)",
                record.name_or_title,
                record.source,
            )
            result.duplicates.append(record)
            continue

        seen.add(key)
        result.unique.append(record)

    logger.info(
        "Deduplication finished: %d unique, %d duplicates removed",
        len(result.unique),
        len(result.duplicates),
    )

    return result