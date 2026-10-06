"""Cleaning helpers for scraped records."""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from dataclasses import replace
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

from models.record import SOURCE_QUOTES, Record

logger = logging.getLogger(__name__)

MISSING_TOKENS = frozenset(
    {"", "n/a", "na", "none", "null", "nan", "-", "--"}
)

RATING_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}

NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
OPENING_QUOTES = '“"'
CLOSING_QUOTES = '”"'


def clean_text(value: Any) -> str | None:
    """Normalize whitespace and convert missing values to None."""
    if value is None:
        return None

    text = unicodedata.normalize(
        "NFC",
        str(value),
    ).replace("\xa0", " ")

    text = " ".join(text.split())

    if text.casefold() in MISSING_TOKENS:
        return None

    return text


def clean_price(value: Any) -> float | None:
    """Convert a price value to a finite float."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return (
            float(value)
            if math.isfinite(value)
            else None
        )

    text = str(value).replace(",", "")
    match = NUMBER_PATTERN.search(text)

    if match is None:
        return None

    number = float(match.group())

    return (
        round(number, 2)
        if math.isfinite(number)
        else None
    )


def clean_rating(value: Any) -> int | float | None:
    """Convert rating words or numeric values to a number."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().casefold()

        if text in RATING_WORDS:
            return RATING_WORDS[text]

        match = NUMBER_PATTERN.search(text)

        if match is None:
            return None

        number = float(match.group())

    if not math.isfinite(number):
        return None

    return (
        int(number)
        if number.is_integer()
        else number
    )


def normalize_url(
    url: Any,
    base: str | None = None,
) -> str | None:
    """Return an absolute HTTP(S) URL without a fragment."""
    text = clean_text(url)

    if text is None:
        return None

    if base:
        text = urljoin(base, text)

    text, _ = urldefrag(text)
    parts = urlsplit(text)

    if (
        parts.scheme.lower() not in {"http", "https"}
        or not parts.netloc
    ):
        return None

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path,
            parts.query,
            "",
        )
    )


def clean_tags(value: Any) -> list[str]:
    """Normalize tags, remove empty values, and remove duplicates."""
    if value is None:
        return []

    items = (
        value.split("|")
        if isinstance(value, str)
        else list(value)
    )

    seen: set[str] = set()
    tags: list[str] = []

    for item in items:
        tag = clean_text(item)

        if tag is None:
            continue

        key = tag.casefold()

        if key in seen:
            continue

        seen.add(key)
        tags.append(tag)

    return tags


def strip_wrapping_quotes(text: str) -> str:
    """Remove decorative quotes surrounding a quote."""
    if (
        len(text) > 1
        and text[0] in OPENING_QUOTES
        and text[-1] in CLOSING_QUOTES
    ):
        return text[1:-1].strip()

    return text


def clean_record(record: Record) -> Record | None:
    """Return a cleaned record or None when the title is missing."""
    source = clean_text(record.source)
    name = clean_text(record.name_or_title)

    if (
        name is not None
        and source
        and source.casefold() == SOURCE_QUOTES
    ):
        name = strip_wrapping_quotes(name)

    if not name:
        logger.warning(
            "Dropping record without a name/title (url=%s)",
            record.source_url,
        )
        return None

    return replace(
        record,
        source=source.casefold() if source else None,
        source_url=normalize_url(record.source_url),
        name_or_title=name,
        category=clean_text(record.category),
        price=clean_price(record.price),
        rating=clean_rating(record.rating),
        author=clean_text(record.author),
        tags=clean_tags(record.tags),
        description=clean_text(record.description),
        availability=clean_text(record.availability),
        author_url=normalize_url(record.author_url),
    )