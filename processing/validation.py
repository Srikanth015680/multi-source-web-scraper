"""Validate cleaned records and keep rejection reasons."""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field

from models.record import (
    KNOWN_SOURCES,
    SOURCE_BOOKS,
    SOURCE_QUOTES,
    Record,
)
from processing.cleaning import normalize_url

logger = logging.getLogger(__name__)

MIN_RATING = 1
MAX_RATING = 5


@dataclass
class RejectedRecord:
    record: Record
    reasons: list[str]


@dataclass
class ValidationResult:
    valid: list[Record] = field(default_factory=list)
    rejected: list[RejectedRecord] = field(default_factory=list)

    @property
    def reason_counts(self) -> dict[str, int]:
        counts = Counter(
            reason
            for item in self.rejected
            for reason in item.reasons
        )

        return dict(sorted(counts.items()))


def _is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_record(record: Record) -> list[str]:
    """Return validation errors for a single record."""
    reasons: list[str] = []

    if record.source not in KNOWN_SOURCES:
        reasons.append("unknown_source")

    if not record.name_or_title:
        reasons.append("missing_name")

    if not record.source_url:
        reasons.append("missing_url")
    elif normalize_url(record.source_url) is None:
        reasons.append("invalid_url")

    if (
        record.price is not None
        and (
            not _is_number(record.price)
            or record.price < 0
        )
    ):
        reasons.append("invalid_price")

    if (
        record.rating is not None
        and (
            not _is_number(record.rating)
            or not MIN_RATING
            <= record.rating
            <= MAX_RATING
        )
    ):
        reasons.append("invalid_rating")

    if record.source == SOURCE_BOOKS:
        if record.price is None:
            reasons.append("missing_price")

        if record.rating is None:
            reasons.append("missing_rating")

    elif (
        record.source == SOURCE_QUOTES
        and not record.author
    ):
        reasons.append("missing_author")

    return reasons


def validate_records(
    records: list[Record],
) -> ValidationResult:
    """Validate all records and separate valid and rejected records."""
    result = ValidationResult()

    for record in records:
        reasons = validate_record(record)

        if reasons:
            logger.warning(
                "Validation rejected %r (%s): %s",
                record.name_or_title,
                record.source,
                ", ".join(reasons),
            )

            result.rejected.append(
                RejectedRecord(
                    record=record,
                    reasons=reasons,
                )
            )
        else:
            result.valid.append(record)

    logger.info(
        "Validation finished: %d valid, %d rejected",
        len(result.valid),
        len(result.rejected),
    )

    return result