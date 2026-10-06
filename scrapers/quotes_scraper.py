"""Scraper for Quotes to Scrape."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from models.record import SOURCE_QUOTES, Record, ScrapeStats

logger = logging.getLogger(__name__)

START_URL = "https://quotes.toscrape.com/"


@dataclass(frozen=True)
class QuoteListing:
    text: str | None
    author: str | None
    author_url: str | None
    tags: list[str] = field(default_factory=list)


def _text(element: Tag | None) -> str | None:
    if element is None:
        return None

    text = element.get_text(" ", strip=True)
    return text or None


def parse_quotes_page(
    html: str,
    page_url: str,
) -> tuple[list[QuoteListing], str | None]:
    """Parse quotes and the next-page URL from a listing page."""
    soup = BeautifulSoup(html, "html.parser")
    quotes: list[QuoteListing] = []

    for card in soup.select("div.quote"):
        author_link = card.select_one(
            "a[href*='/author/']"
        )

        href = (
            author_link.get("href")
            if author_link is not None
            else None
        )

        tags = [
            tag
            for tag in (
                _text(element)
                for element in card.select("div.tags a.tag")
            )
            if tag
        ]

        quote = QuoteListing(
            text=_text(card.select_one("span.text")),
            author=_text(card.select_one("small.author")),
            author_url=(
                urljoin(page_url, str(href))
                if href
                else None
            ),
            tags=tags,
        )

        if quote.text is None or quote.author is None:
            logger.warning(
                "Quote on %s is missing text or author",
                page_url,
            )

        quotes.append(quote)

    next_url = None
    next_link = soup.select_one("li.next a")

    if next_link is not None:
        next_href = next_link.get("href")

        if next_href:
            next_url = urljoin(
                page_url,
                str(next_href),
            )
        else:
            logger.warning(
                "Next-page link without href on %s",
                page_url,
            )

    return quotes, next_url


def parse_author(html: str) -> str | None:
    """Extract the author's birth information and biography."""
    soup = BeautifulSoup(html, "html.parser")

    born_parts = [
        _text(soup.select_one("span.author-born-date")),
        _text(soup.select_one("span.author-born-location")),
    ]

    born = " ".join(
        part for part in born_parts if part
    )

    bio = _text(
        soup.select_one("div.author-description")
    )

    parts = []

    if born:
        parts.append(f"Born: {born}.")

    if bio:
        parts.append(bio)

    return " ".join(parts) or None


class QuotesScraper:
    """Scrape quotes from listing pages and author pages."""

    def __init__(
        self,
        client,
        start_url: str = START_URL,
        max_pages: int | None = None,
        fetch_authors: bool = True,
    ) -> None:
        self.client = client
        self.start_url = start_url
        self.max_pages = max_pages
        self.fetch_authors = fetch_authors
        self.stats = ScrapeStats()
        self._author_cache: dict[str, str | None] = {}

    def scrape(self) -> list[Record]:
        self.stats = ScrapeStats()
        self._author_cache = {}

        records: list[Record] = []
        visited: set[str] = set()
        url: str | None = self.start_url

        logger.info(
            "Quotes scraping started at %s",
            self.start_url,
        )

        while url:
            if url in visited:
                logger.warning(
                    "Quotes: pagination loop detected at %s",
                    url,
                )
                break

            if (
                self.max_pages is not None
                and self.stats.pages_requested >= self.max_pages
            ):
                logger.info(
                    "Quotes: max_pages=%d reached",
                    self.max_pages,
                )
                break

            visited.add(url)

            html = self._fetch_page(url)

            if html is None:
                logger.error(
                    "Quotes: page failed: %s",
                    url,
                )
                break

            quotes, next_url = parse_quotes_page(
                html,
                url,
            )

            logger.info(
                "Quotes: %d quotes extracted from %s",
                len(quotes),
                url,
            )

            for quote in quotes:
                records.append(
                    self._build_record(quote, url)
                )

            url = next_url

        logger.info(
            "Quotes scraping completed: %d records",
            len(records),
        )

        return records

    def _fetch_page(
        self,
        url: str,
    ) -> str | None:
        self.stats.pages_requested += 1

        html = self.client.get(url)

        if html is None:
            self.stats.failed_pages.append(url)
        else:
            self.stats.pages_succeeded += 1

        return html

    def _get_author_info(
        self,
        url: str,
    ) -> str | None:
        if url in self._author_cache:
            return self._author_cache[url]

        self.stats.detail_pages_requested += 1

        html = self.client.get(url)

        if html is None:
            self.stats.failed_detail_pages.append(url)
            info = None
        else:
            info = parse_author(html)

        self._author_cache[url] = info

        return info

    def _build_record(
        self,
        quote: QuoteListing,
        page_url: str,
    ) -> Record:
        description = None

        if self.fetch_authors and quote.author_url:
            description = self._get_author_info(
                quote.author_url
            )

        return Record(
            source=SOURCE_QUOTES,
            source_url=page_url,
            name_or_title=quote.text,
            author=quote.author,
            tags=list(quote.tags),
            description=description,
            author_url=quote.author_url,
        )