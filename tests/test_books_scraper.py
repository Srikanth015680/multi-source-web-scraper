from models.record import SOURCE_BOOKS
from scrapers.books_scraper import BooksScraper, parse_detail, parse_listing
from tests.conftest import FakeClient, load_fixture

ROOT = "https://books.toscrape.com/"
PAGE2 = "https://books.toscrape.com/catalogue/page-2.html"
ATTIC = (
    "https://books.toscrape.com/"
    "catalogue/a-light-in-the-attic_1000/index.html"
)
VELVET = (
    "https://books.toscrape.com/"
    "catalogue/tipping-the-velvet_999/index.html"
)
SHARP = (
    "https://books.toscrape.com/"
    "catalogue/sharp-objects_997/index.html"
)


def listing_html(
    *cards: str,
    next_href: str | None = None,
) -> str:
    pager = (
        f'<li class="next"><a href="{next_href}">next</a></li>'
        if next_href
        else ""
    )

    return (
        f"<html><body><ol>{''.join(cards)}</ol>"
        f"<ul>{pager}</ul></body></html>"
    )


def card(
    title: str,
    href: str,
    price: str = "£10.00",
    rating: str = "Two",
) -> str:
    return (
        f'<article class="product_pod">'
        f'<p class="star-rating {rating}"></p>'
        f'<h3><a href="{href}" title="{title}">{title}</a></h3>'
        f'<p class="price_color">{price}</p>'
        f'<p class="availability">In stock</p>'
        f"</article>"
    )


def full_site() -> dict[str, str | None]:
    return {
        ROOT: load_fixture("books_page1.html"),
        PAGE2: load_fixture("books_page2.html"),
        ATTIC: load_fixture("book_detail_attic.html"),
        VELVET: load_fixture("book_detail_no_description.html"),
        SHARP: load_fixture("book_detail_attic.html"),
    }


def test_parse_listing_extracts_fields_and_resolves_urls():
    listings, next_url = parse_listing(
        load_fixture("books_page1.html"),
        ROOT,
    )

    assert len(listings) == 2

    first = listings[0]

    assert first.title == "A Light in the Attic"
    assert first.price == "£51.77"
    assert first.rating == "Three"
    assert first.availability == "In stock"
    assert first.url == ATTIC
    assert next_url == PAGE2


def test_parse_listing_resolves_relative_next_link():
    _, next_url = parse_listing(
        listing_html(
            card("A", "a/index.html"),
            next_href="page-3.html",
        ),
        PAGE2,
    )

    assert (
        next_url
        == "https://books.toscrape.com/catalogue/page-3.html"
    )


def test_parse_listing_last_page_has_no_next_link():
    listings, next_url = parse_listing(
        load_fixture("books_page2.html"),
        PAGE2,
    )

    assert len(listings) == 1
    assert next_url is None


def test_parse_listing_handles_missing_elements():
    html = listing_html(
        '<article class="product_pod">'
        "<h3>No link here</h3>"
        "</article>"
    )

    listings, next_url = parse_listing(html, ROOT)

    assert len(listings) == 1
    assert listings[0].url is None
    assert listings[0].price is None
    assert listings[0].rating is None
    assert next_url is None


def test_parse_listing_on_unexpected_page_returns_nothing():
    html = "<html><body>Maintenance</body></html>"

    assert parse_listing(html, ROOT) == ([], None)


def test_parse_detail_extracts_category_description_availability():
    detail = parse_detail(
        load_fixture("book_detail_attic.html")
    )

    assert detail.category == "Poetry"
    assert detail.description.startswith("It's hard to imagine")
    assert detail.availability == "In stock (22 available)"


def test_parse_detail_without_description():
    detail = parse_detail(
        load_fixture("book_detail_no_description.html")
    )

    assert detail.category == "Historical Fiction"
    assert detail.description is None


def test_scrape_follows_pagination_until_no_next_link():
    client = FakeClient(full_site())
    scraper = BooksScraper(client)

    records = scraper.scrape()

    assert [record.name_or_title for record in records] == [
        "A Light in the Attic",
        "Tipping the Velvet",
        "Sharp Objects",
    ]

    assert all(record.source == SOURCE_BOOKS for record in records)
    assert records[0].category == "Poetry"
    assert records[0].source_url == ATTIC
    assert records[0].price == "£51.77"

    assert scraper.stats.pages_requested == 2
    assert scraper.stats.pages_succeeded == 2
    assert scraper.stats.failed_pages == []


def test_each_detail_page_is_requested_once():
    detail_url = (
        "https://books.toscrape.com/dup_1/index.html"
    )

    pages = {
        ROOT: listing_html(
            card("Dup", "dup_1/index.html"),
            card("Dup", "dup_1/index.html"),
        ),
        detail_url: load_fixture("book_detail_attic.html"),
    }

    client = FakeClient(pages)
    records = BooksScraper(client).scrape()

    assert len(records) == 2
    assert client.requested.count(detail_url) == 1


def test_failed_listing_page_keeps_earlier_records():
    pages = full_site()
    pages[PAGE2] = None

    scraper = BooksScraper(FakeClient(pages))
    records = scraper.scrape()

    assert len(records) == 2
    assert scraper.stats.failed_pages == [PAGE2]


def test_failed_detail_page_keeps_record_without_detail_fields():
    pages = full_site()
    pages[SHARP] = None

    scraper = BooksScraper(FakeClient(pages))
    records = scraper.scrape()

    sharp = records[-1]

    assert sharp.name_or_title == "Sharp Objects"
    assert sharp.category is None
    assert sharp.description is None
    assert scraper.stats.failed_detail_pages == [SHARP]


def test_invalid_response_yields_no_records_and_no_crash():
    html = "<html>not a catalogue</html>"

    scraper = BooksScraper(FakeClient({ROOT: html}))

    assert scraper.scrape() == []
    assert scraper.stats.pages_succeeded == 1


def test_pagination_loop_is_detected():
    pages = {
        ROOT: listing_html(next_href="/"),
    }

    client = FakeClient(pages)
    BooksScraper(client).scrape()

    assert client.requested == [ROOT]


def test_max_pages_limits_pagination():
    client = FakeClient(full_site())
    scraper = BooksScraper(client, max_pages=1)

    records = scraper.scrape()

    assert len(records) == 2
    assert PAGE2 not in client.requested