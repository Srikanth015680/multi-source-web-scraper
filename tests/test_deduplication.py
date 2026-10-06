from models.record import SOURCE_BOOKS, SOURCE_QUOTES, Record
from processing.deduplication import deduplicate, normalize_key_text


def book(
    title: str,
    price: float = 10.0,
    url: str = "https://books.toscrape.com/a",
) -> Record:
    return Record(
        SOURCE_BOOKS,
        url,
        title,
        price=price,
        rating=3,
    )


def quote(text: str, author: str) -> Record:
    return Record(
        SOURCE_QUOTES,
        "https://quotes.toscrape.com/",
        text,
        author=author,
    )


def test_exact_duplicate_removed():
    result = deduplicate(
        [
            book("Example Book Title"),
            book("Example Book Title"),
        ]
    )

    assert len(result.unique) == 1
    assert result.detected == 1


def test_whitespace_duplicate_removed():
    result = deduplicate(
        [
            book("Example Book Title"),
            book("  Example   Book Title "),
        ]
    )

    assert len(result.unique) == 1


def test_capitalization_duplicate_removed():
    result = deduplicate(
        [
            book("Example Book Title"),
            book("EXAMPLE BOOK TITLE"),
        ]
    )

    assert len(result.unique) == 1


def test_punctuation_and_accent_differences_are_ignored():
    result = deduplicate(
        [
            quote("It's better.", "André Gide"),
            quote("It’s  better", "andre gide"),
        ]
    )

    assert len(result.unique) == 1


def test_different_books_are_not_merged():
    result = deduplicate(
        [
            book("Book One"),
            book("Book Two"),
        ]
    )

    assert len(result.unique) == 2
    assert result.detected == 0


def test_same_title_different_price_is_not_merged():
    result = deduplicate(
        [
            book("Same Title", price=10.0),
            book("Same Title", price=25.0),
        ]
    )

    assert len(result.unique) == 2


def test_same_quote_by_different_authors_is_not_merged():
    result = deduplicate(
        [
            quote("Be yourself.", "Oscar Wilde"),
            quote("Be yourself.", "Someone Else"),
        ]
    )

    assert len(result.unique) == 2


def test_same_text_in_different_sources_is_not_merged():
    shared = "Poetry"

    result = deduplicate(
        [
            book(shared),
            Record(
                SOURCE_QUOTES,
                "https://quotes.toscrape.com/",
                shared,
                author="X",
            ),
        ]
    )

    assert len(result.unique) == 2


def test_first_occurrence_is_kept():
    first = book(
        "Dup",
        url="https://books.toscrape.com/first",
    )
    second = book(
        "dup",
        url="https://books.toscrape.com/second",
    )

    result = deduplicate([first, second])

    assert result.unique == [first]
    assert result.duplicates == [second]


def test_normalize_key_text():
    assert normalize_key_text("  Hello,   WORLD! ") == "hello world"
    assert normalize_key_text(None) == ""