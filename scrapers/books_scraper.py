"""Scraper for Books to Scrape."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from models.record import SOURCE_BOOKS, Record, ScrapeStats

logger = logging.getLogger(__name__)

START_URL = "https://books.toscrape.com/"


@dataclass(frozen=True)
class BookListing:
    title: str | None
    price: str | None
    availability: str | None
    rating: str | None
    url: str | None


@dataclass(frozen=True)
class BookDetail:
    category: str | None = None
    description: str | None = None
    availability: str | None = None


def _text(element: Tag | None) -> str | None:
    if element is None:
        return None

    text = element.get_text(" ", strip=True)
    return text or None


def parse_listing(
    html: str,
    page_url: str,
) -> tuple[list[BookListing], str | None]:
    """Parse books and the next-page URL from a listing page."""
    soup = BeautifulSoup(html, "html.parser")
    listings: list[BookListing] = []

    for card in soup.select("article.product_pod"):
        link = card.select_one("h3 a")

        title = None
        url = None

        if link is not None:
            title = (
                str(link.get("title") or "").strip()
                or _text(link)
            )

            href = link.get("href")
            if href:
                url = urljoin(page_url, str(href))

        rating_element = card.select_one("p.star-rating")
        rating = None

        if rating_element is not None:
            classes = rating_element.get("class", [])
            rating_classes = [
                value
                for value in classes
                if value != "star-rating"
            ]
            rating = rating_classes[0] if rating_classes else None

        listing = BookListing(
            title=title,
            price=_text(
                card.select_one("p.price_color")
            ),
            availability=_text(
                card.select_one("p.availability")
            ),
            rating=rating,
            url=url,
        )

        missing = []

        if listing.title is None:
            missing.append("title")
        if listing.price is None:
            missing.append("price")
        if listing.availability is None:
            missing.append("availability")
        if listing.rating is None:
            missing.append("rating")
        if listing.url is None:
            missing.append("url")

        if missing:
            logger.warning(
                "Book card on %s is missing: %s",
                page_url,
                ", ".join(missing),
            )

        listings.append(listing)

    next_url = None
    next_link = soup.select_one("li.next a")

    if next_link is not None:
        href = next_link.get("href")

        if href:
            next_url = urljoin(page_url, str(href))
        else:
            logger.warning(
                "Next-page link without href on %s",
                page_url,
            )

    return listings, next_url


def parse_detail(html: str) -> BookDetail:
    """Parse category, description, and availability."""
    soup = BeautifulSoup(html, "html.parser")

    breadcrumbs = [
        _text(item)
        for item in soup.select("ul.breadcrumb li")
    ]

    category = (
        breadcrumbs[-2]
        if len(breadcrumbs) >= 3
        else None
    )

    description = None
    heading = soup.select_one("#product_description")

    if heading is not None:
        description = _text(
            heading.find_next_sibling("p")
        )

    availability = _text(
        soup.select_one("p.availability")
    )

    return BookDetail(
        category=category,
        description=description,
        availability=availability,
    )


class BooksScraper:
    """Scrape books from listing pages and detail pages."""

    def __init__(
        self,
        client,
        start_url: str = START_URL,
        max_pages: int | None = None,
        fetch_details: bool = True,
    ) -> None:
        self.client = client
        self.start_url = start_url
        self.max_pages = max_pages
        self.fetch_details = fetch_details
        self.stats = ScrapeStats()
        self._detail_cache: dict[str, BookDetail] = {}

    def scrape(self) -> list[Record]:
        self.stats = ScrapeStats()
        self._detail_cache = {}

        records: list[Record] = []
        visited: set[str] = set()
        url: str | None = self.start_url

        logger.info(
            "Books scraping started at %s",
            self.start_url,
        )

        while url:
            if url in visited:
                logger.warning(
                    "Books: pagination loop detected at %s",
                    url,
                )
                break

            if (
                self.max_pages is not None
                and self.stats.pages_requested >= self.max_pages
            ):
                logger.info(
                    "Books: max_pages=%d reached",
                    self.max_pages,
                )
                break

            visited.add(url)

            html = self._fetch_listing(url)

            if html is None:
                logger.error(
                    "Books: listing page failed: %s",
                    url,
                )
                break

            listings, next_url = parse_listing(
                html,
                url,
            )

            logger.info(
                "Books: %d books extracted from %s",
                len(listings),
                url,
            )

            for listing in listings:
                records.append(
                    self._build_record(listing)
                )

            url = next_url

        logger.info(
            "Books scraping completed: %d records",
            len(records),
        )

        return records

    def _fetch_listing(
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

    def _get_detail(
        self,
        url: str,
    ) -> BookDetail:
        if url in self._detail_cache:
            return self._detail_cache[url]

        self.stats.detail_pages_requested += 1

        html = self.client.get(url)

        if html is None:
            self.stats.failed_detail_pages.append(url)
            detail = BookDetail()
        else:
            detail = parse_detail(html)

        self._detail_cache[url] = detail

        return detail

    def _build_record(
        self,
        listing: BookListing,
    ) -> Record:
        detail = BookDetail()

        if self.fetch_details and listing.url:
            detail = self._get_detail(listing.url)

        return Record(
            source=SOURCE_BOOKS,
            source_url=listing.url,
            name_or_title=listing.title,
            category=detail.category,
            price=listing.price,
            rating=listing.rating,
            description=detail.description,
            availability=(
                detail.availability
                or listing.availability
            ),
        )