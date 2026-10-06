"""Consolidate cleaned, validated, and deduplicated records."""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from models.record import COLUMNS, TAG_SEPARATOR, Record, ScrapeStats
from processing.cleaning import clean_record
from processing.deduplication import deduplicate
from processing.validation import RejectedRecord, validate_records

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationResult:
    records: list[Record]
    rejected: list[RejectedRecord]
    duplicates: list[Record]
    collected: dict[str, int]
    after_cleaning: dict[str, int]
    rejection_reasons: dict[str, int]
    sources: list[str] = field(default_factory=list)

    @property
    def final_per_source(self) -> dict[str, int]:
        return dict(
            Counter(record.source for record in self.records)
        )


def consolidate(
    raw_by_source: dict[str, list[Record]],
) -> ConsolidationResult:
    """Run cleaning, validation, and deduplication."""
    collected = {
        source: len(records)
        for source, records in raw_by_source.items()
    }

    raw_records = [
        record
        for records in raw_by_source.values()
        for record in records
    ]

    cleaned = [
        cleaned_record
        for record in raw_records
        if (
            cleaned_record := clean_record(record)
        ) is not None
    ]

    logger.info(
        "Cleaning finished: %d of %d records kept",
        len(cleaned),
        len(raw_records),
    )

    after_cleaning = dict(
        Counter(record.source for record in cleaned)
    )

    validation = validate_records(cleaned)
    deduplication = deduplicate(validation.valid)

    return ConsolidationResult(
        records=deduplication.unique,
        rejected=validation.rejected,
        duplicates=deduplication.duplicates,
        collected=collected,
        after_cleaning=after_cleaning,
        rejection_reasons=validation.reason_counts,
        sources=list(raw_by_source),
    )


def write_dataset(
    records: list[Record],
    path: Path,
) -> None:
    """Write the final records to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)

    frame = pd.DataFrame(
        [record.to_row() for record in records],
        columns=COLUMNS,
    )

    frame.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )

    logger.info(
        "Final dataset written to %s (%d rows)",
        path,
        len(frame),
    )


def write_rejected(
    rejected: list[RejectedRecord],
    path: Path,
) -> None:
    """Write rejected records and their validation reasons."""
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = [
        {
            **item.record.to_row(),
            "rejection_reasons": TAG_SEPARATOR.join(
                item.reasons
            ),
        }
        for item in rejected
    ]

    columns = [
        *COLUMNS,
        "rejection_reasons",
    ]

    pd.DataFrame(
        rows,
        columns=columns,
    ).to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )

    logger.info(
        "Rejected records written to %s (%d rows)",
        path,
        len(rejected),
    )


def build_summary(
    result: ConsolidationResult,
    scrape_stats: dict[str, ScrapeStats],
    execution_time_seconds: float,
) -> dict[str, Any]:
    """Build the JSON summary report."""
    removed_in_cleaning = {
        source: (
            result.collected.get(source, 0)
            - result.after_cleaning.get(source, 0)
        )
        for source in result.sources
    }

    rejected_by_source = Counter(
        item.record.source
        for item in result.rejected
    )

    duplicates_by_source = Counter(
        record.source
        for record in result.duplicates
    )

    final = result.final_per_source

    return {
        "generated_at": (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
        ),
        "execution_time_seconds": round(
            execution_time_seconds,
            2,
        ),
        "records_collected_per_source": result.collected,
        "total_records_collected": sum(
            result.collected.values()
        ),
        "records_removed_during_cleaning": sum(
            removed_in_cleaning.values()
        ),
        "total_records_after_cleaning": sum(
            result.after_cleaning.values()
        ),
        "records_rejected_during_validation": len(
            result.rejected
        ),
        "rejection_reasons": result.rejection_reasons,
        "duplicates_detected": len(
            result.duplicates
        ),
        "duplicates_removed": len(
            result.duplicates
        ),
        "duplicates_flagged_and_retained": 0,
        "final_record_count": len(result.records),
        "final_records_per_source": {
            source: final.get(source, 0)
            for source in result.sources
        },
        "per_source": {
            source: {
                "collected": result.collected.get(
                    source,
                    0,
                ),
                "removed_during_cleaning": (
                    removed_in_cleaning[source]
                ),
                "rejected_during_validation": (
                    rejected_by_source.get(source, 0)
                ),
                "duplicates_removed": (
                    duplicates_by_source.get(source, 0)
                ),
                "final": final.get(source, 0),
            }
            for source in result.sources
        },
        "scraping": {
            source: stats.to_dict()
            for source, stats in scrape_stats.items()
        },
    }


def write_summary(
    summary: dict[str, Any],
    path: Path,
) -> None:
    """Write the summary report as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    logger.info(
        "Summary report written to %s",
        path,
    )