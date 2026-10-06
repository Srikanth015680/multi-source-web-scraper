from models.record import SOURCE_QUOTES
from scrapers.quotes_scraper import (
    QuotesScraper,
    parse_author,
    parse_quotes_page,
)
from tests.conftest import FakeClient, load_fixture


ROOT = "https://quotes.toscrape.com/"
PAGE2 = "https://quotes.toscrape.com/page/2/"
EINSTEIN = "https://quotes.toscrape.com/author/Albert-Einstein"
ROWLING = "https://quotes.toscrape.com/author/J-K-Rowling"


def site() -> dict[str, str | None]:
    return {
        ROOT: load_fixture("quotes_page1.html"),
        PAGE2: load_fixture("quotes_page2.html"),
        EINSTEIN: load_fixture("author_einstein.html"),
        ROWLING: None,
    }


def test_parse_quotes_page_extracts_fields():
    quotes, next_url = parse_quotes_page(
        load_fixture("quotes_page1.html"),
        ROOT,
    )

    assert len(quotes) == 2

    first = quotes[0]

    assert first.text.startswith(
        "“The world as we have created it"
    )
    assert first.author == "Albert Einstein"
    assert first.author_url == EINSTEIN
    assert first.tags == ["change", "thinking"]
    assert next_url == PAGE2


def test_parse_quotes_page_last_page_and_missing_tags():
    quotes, next_url = parse_quotes_page(
        load_fixture("quotes_page2.html"),
        PAGE2,
    )

    assert len(quotes) == 1
    assert quotes[0].tags == []
    assert next_url is None


def test_parse_quotes_page_handles_missing_fields():
    html = (
        '<div class="quote">'
        '<span class="text">Orphan quote</span>'
        "</div>"
    )

    quotes, _ = parse_quotes_page(html, ROOT)

    assert quotes[0].text == "Orphan quote"
    assert quotes[0].author is None
    assert quotes[0].author_url is None


def test_parse_author_builds_bio_with_born_info():
    info = parse_author(
        load_fixture("author_einstein.html")
    )

    assert info.startswith(
        "Born: March 14, 1879 in Ulm, Germany."
    )
    assert "Nobel Prize" in info


def test_parse_author_on_empty_page_returns_none():
    assert parse_author("<html></html>") is None


def test_scrape_follows_pagination_and_maps_fields():
    scraper = QuotesScraper(FakeClient(site()))
    records = scraper.scrape()

    assert len(records) == 3

    first = records[0]

    assert first.source == SOURCE_QUOTES
    assert first.source_url == ROOT
    assert first.author == "Albert Einstein"
    assert first.price is None
    assert first.rating is None
    assert first.category is None
    assert first.description.startswith(
        "Born: March 14, 1879"
    )
    assert records[2].source_url == PAGE2
    assert scraper.stats.pages_requested == 2


def test_author_page_is_requested_once_per_author():
    client = FakeClient(site())

    QuotesScraper(client).scrape()

    assert client.requested.count(EINSTEIN) == 1


def test_failed_author_page_keeps_quote_without_description():
    scraper = QuotesScraper(FakeClient(site()))
    records = scraper.scrape()

    assert records[1].author == "J.K. Rowling"
    assert records[1].description is None
    assert scraper.stats.failed_detail_pages == [ROWLING]


def test_failed_page_keeps_earlier_records():
    pages = site()
    pages[PAGE2] = None

    scraper = QuotesScraper(FakeClient(pages))

    assert len(scraper.scrape()) == 2
    assert scraper.stats.failed_pages == [PAGE2]


def test_invalid_response_yields_no_records():
    scraper = QuotesScraper(
        FakeClient({ROOT: "<html>nothing</html>"})
    )

    assert scraper.scrape() == []