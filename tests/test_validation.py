import pytest

from models.record import SOURCE_BOOKS, SOURCE_QUOTES, Record
from processing.validation import validate_record, validate_records


BOOK_URL = (
    "https://books.toscrape.com/"
    "catalogue/x_1/index.html"
)
QUOTE_URL = "https://quotes.toscrape.com/"


def book(**overrides) -> Record:
    values = {
        "source": SOURCE_BOOKS,
        "source_url": BOOK_URL,
        "name_or_title": "A Book",
        "price": 10.0,
        "rating": 3,
    }
    values.update(overrides)

    return Record(**values)


def quote(**overrides) -> Record:
    values = {
        "source": SOURCE_QUOTES,
        "source_url": QUOTE_URL,
        "name_or_title": "Quote",
        "author": "Someone",
    }
    values.update(overrides)

    return Record(**values)


def test_valid_book_and_quote_pass():
    assert validate_record(book()) == []
    assert validate_record(quote()) == []


@pytest.mark.parametrize(
    "price",
    [-1.0, "12.5", float("inf")],
)
def test_invalid_price_rejected(price):
    assert "invalid_price" in validate_record(
        book(price=price)
    )


@pytest.mark.parametrize(
    "rating",
    [0, 6, 8.5, "Three"],
)
def test_invalid_rating_rejected(rating):
    assert "invalid_rating" in validate_record(
        book(rating=rating)
    )


def test_missing_url_rejected():
    assert "missing_url" in validate_record(
        book(source_url=None)
    )


def test_malformed_url_rejected():
    assert "invalid_url" in validate_record(
        book(source_url="not-a-url")
    )


def test_unknown_source_rejected():
    assert "unknown_source" in validate_record(
        book(source="other_site")
    )


def test_missing_name_rejected():
    assert "missing_name" in validate_record(
        book(name_or_title=None)
    )


def test_book_requires_price_and_rating():
    reasons = validate_record(
        book(price=None, rating=None)
    )

    assert {
        "missing_price",
        "missing_rating",
    } <= set(reasons)


def test_quote_requires_author_but_not_price():
    assert validate_record(
        quote(author=None)
    ) == ["missing_author"]


def test_validate_records_tracks_rejections_and_reason_counts():
    result = validate_records(
        [
            book(),
            book(price=-5),
            quote(author=None),
            book(source_url=None, price=-1),
        ]
    )

    assert len(result.valid) == 1
    assert len(result.rejected) == 3
    assert result.reason_counts == {
        "invalid_price": 2,
        "missing_author": 1,
        "missing_url": 1,
    }