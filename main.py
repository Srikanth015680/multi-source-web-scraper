"""Entry point for the multi-source scraping pipeline."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from models.record import (
    SOURCE_BOOKS,
    SOURCE_QUOTES,
    Record,
    ScrapeStats,
)
from processing.consolidation import (
    build_summary,
    consolidate,
    write_dataset,
    write_rejected,
    write_summary,
)
from scrapers.books_scraper import BooksScraper
from scrapers.quotes_scraper import QuotesScraper
from utils.http_client import HttpClient
from utils.logger import setup_logging

logger = logging.getLogger("main")

ROOT = Path(__file__).resolve().parent


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-source web scraping pipeline"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output",
    )

    parser.add_argument(
        "--log-dir",
        type=Path,
        default=ROOT / "logs",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Minimum seconds between requests",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit listing pages per source",
    )

    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(argv)

    log_file = setup_logging(args.log_dir)
    started = time.perf_counter()

    logger.info(
        "Pipeline started (log file: %s)",
        log_file,
    )

    client = HttpClient(
        timeout=args.timeout,
        min_delay=args.delay,
    )

    scrapers = {
        SOURCE_BOOKS: BooksScraper(
            client,
            max_pages=args.max_pages,
        ),
        SOURCE_QUOTES: QuotesScraper(
            client,
            max_pages=args.max_pages,
        ),
    }

    raw: dict[str, list[Record]] = {}
    stats: dict[str, ScrapeStats] = {}

    for source, scraper in scrapers.items():
        logger.info("Source started: %s", source)

        try:
            raw[source] = scraper.scrape()
        except Exception:
            logger.exception(
                "Source %s failed unexpectedly",
                source,
            )
            raw[source] = []
            scraper.stats.error = (
                "Unexpected error; see log"
            )

        stats[source] = scraper.stats

    result = consolidate(raw)

    execution_time = (
        time.perf_counter() - started
    )

    summary = build_summary(
        result,
        stats,
        execution_time,
    )

    output_dir = args.output_dir

    write_dataset(
        result.records,
        output_dir / "final_dataset.csv",
    )

    write_rejected(
        result.rejected,
        output_dir / "rejected_records.csv",
    )

    write_summary(
        summary,
        output_dir / "summary_report.json",
    )

    print_report(summary)

    logger.info(
        "Pipeline completed in %.2fs",
        summary["execution_time_seconds"],
    )

    return 0 if result.records else 1


def print_report(summary: dict) -> None:
    print("\n=== Summary ===")

    for source, count in summary[
        "records_collected_per_source"
    ].items():
        print(f"collected {source}: {count}")

    print(
        f"after cleaning:        "
        f"{summary['total_records_after_cleaning']}"
    )

    print(
        f"rejected (validation): "
        f"{summary['records_rejected_during_validation']}"
    )

    print(
        f"duplicates removed:    "
        f"{summary['duplicates_removed']}"
    )

    print(
        f"final records:         "
        f"{summary['final_record_count']}"
    )

    print(
        f"execution time:        "
        f"{summary['execution_time_seconds']}s"
    )


if __name__ == "__main__":
    sys.exit(main())