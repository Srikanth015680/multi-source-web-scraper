import pytest

from models.record import SOURCE_BOOKS, SOURCE_QUOTES, Record
from processing.cleaning import (
    clean_price,
    clean_rating,
    clean_record,
    clean_tags,
    clean_text,
    normalize_url,
    strip_wrapping_quotes,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("  Example Book Title  ", "Example Book Title"),
        ("Too   many\n spaces\xa0here", "Too many spaces here"),
        ("", None),
        ("   ", None),
        ("N/A", None),
        ("null", None),
        (None, None),
    ],
)
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("£51.77", 51.77),
        ("Â£51.77", 51.77),
        ("£1,051.50", 1051.5),
        (12, 12.0),
        ("free", None),
        (None, None),
        (True, None),
        (float("nan"), None),
    ],
)
def test_clean_price(raw, expected):
    assert clean_price(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Three", 3),
        ("five", 5),
        ("4", 4),
        (2.0, 2),
        ("3 out of 5", 3),
        ("lots", None),
        (None, None),
    ],
)
def test_clean_rating(raw, expected):
    assert clean_rating(raw) == expected


def test_clean_rating_keeps_out_of_range_values_for_validation():
    assert clean_rating("9") == 9


def test_normalize_url_resolves_relative_and_strips_fragment():
    assert (
        normalize_url(
            "../a/index.html#top",
            base="https://books.toscrape.com/catalogue/x/",
        )
        == "https://books.toscrape.com/catalogue/a/index.html"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "",
        None,
        "not a url",
        "ftp://example.com/x",
        "http://",
        "javascript:alert(1)",
    ],
)
def test_normalize_url_rejects_invalid(bad):
    assert normalize_url(bad) is None


def test_clean_tags_strips_and_removes_repeats():
    assert clean_tags([" love ", "Love", "", "life"]) == ["love", "life"]
    assert clean_tags("a|b| a ") == ["a", "b"]
    assert clean_tags(None) == []


def test_strip_wrapping_quotes():
    assert strip_wrapping_quotes("“Hello there”") == "Hello there"
    assert strip_wrapping_quotes("No quotes") == "No quotes"
    assert strip_wrapping_quotes("“Unbalanced") == "“Unbalanced"


def test_clean_record_books():
    raw = Record(
        source=" Books_ToScrape ",
        source_url="https://books.toscrape.com/catalogue/x_1/index.html#a",
        name_or_title="  Example   Book ",
        price="£12.50",
        rating="Four",
        description="  text \n here ",
        category=" Poetry ",
    )

    cleaned = clean_record(raw)

    assert cleaned.source == SOURCE_BOOKS
    assert cleaned.name_or_title == "Example Book"
    assert cleaned.price == 12.5
    assert cleaned.rating == 4
    assert cleaned.description == "text here"
    assert cleaned.category == "Poetry"
    assert (
        cleaned.source_url
        == "https://books.toscrape.com/catalogue/x_1/index.html"
    )


def test_clean_record_quote_strips_decorative_quotes():
    raw = Record(
        SOURCE_QUOTES,
        "https://quotes.toscrape.com/",
        "“Be yourself.”",
        author=" Oscar Wilde ",
        tags=["a", " a "],
    )

    cleaned = clean_record(raw)

    assert cleaned.name_or_title == "Be yourself."
    assert cleaned.author == "Oscar Wilde"
    assert cleaned.tags == ["a"]
    assert cleaned.price is None


def test_clean_record_drops_record_without_name():
    record = Record(
        SOURCE_BOOKS,
        "https://x.com/",
        "   ",
    )

    assert clean_record(record) is None


def test_clean_record_keeps_invalid_url_as_none_for_validation():
    record = Record(
        SOURCE_BOOKS,
        "garbage",
        "Title",
        price="£1",
        rating="One",
    )

    cleaned = clean_record(record)

    assert cleaned is not None
    assert cleaned.source_url is None