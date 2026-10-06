from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any

SOURCE_BOOKS = "books_toscrape"
SOURCE_QUOTES = "quotes_toscrape"
KNOWN_SOURCES = frozenset({SOURCE_BOOKS, SOURCE_QUOTES})
TAG_SEPARATOR = "|"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Record:
    """Common data model for scraped records."""

    source: str | None
    source_url: str | None
    name_or_title: str | None
    category: str | None = None
    price: str | int | float | None = None
    rating: str | int | float | None = None
    author: str | None = None
    tags: list[str] = field(default_factory=list)
    description: str | None = None
    scraped_at: str = field(default_factory=utc_now_iso)
    availability: str | None = None
    author_url: str | None = None

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["tags"] = TAG_SEPARATOR.join(self.tags) if self.tags else None
        return row


COLUMNS = [field.name for field in fields(Record)]


@dataclass
class ScrapeStats:
    """Scraping statistics used in the summary report."""

    pages_requested: int = 0
    pages_succeeded: int = 0
    failed_pages: list[str] = field(default_factory=list)
    detail_pages_requested: int = 0
    failed_detail_pages: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)