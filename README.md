
# Multi-Source Web Scraping & Data Consolidation

A Python pipeline that scrapes two public sandbox sites, **Books to Scrape** and **Quotes to Scrape**, and combines them into one cleaned, validated and deduplicated dataset with a summary report.

## Project Overview

The two sites have different structures. Books contain prices, ratings and categories, while quotes contain authors and tags. The pipeline collects data from both sources, maps everything into one common schema, cleans and validates the records, removes duplicates, and produces a single CSV dataset along with a JSON summary report.

Rejections, duplicates and scraping failures are counted and reported instead of being silently dropped.

## Architecture

```text
Books to Scrape ─┐
                 ├─> Scraping -> Cleaning -> Validation -> Deduplication -> Consolidation -> Output
Quotes to Scrape ┘
```

| Stage         | Module                                                        | Responsibility                                                |
| ------------- | ------------------------------------------------------------- | ------------------------------------------------------------- |
| HTTP          | `utils/http_client.py`                                      | timeout, User-Agent, retries, exponential backoff, rate limit |
| Scraping      | `scrapers/books_scraper.py`, `scrapers/quotes_scraper.py` | fetch pages, follow pagination, extract raw fields            |
| Cleaning      | `processing/cleaning.py`                                    | whitespace, price, rating, missing values, URLs               |
| Validation    | `processing/validation.py`                                  | rules + rejection reasons                                     |
| Deduplication | `processing/deduplication.py`                               | normalised-key duplicate detection                            |
| Consolidation | `processing/consolidation.py`                               | runs the stages, writes CSV/JSON                              |
| Entry point   | `main.py`                                                   | wires everything together and isolates source failures        |

```text
scraping_assignment/
├── scrapers/  processing/  models/  utils/
├── tests/ (+ tests/fixtures/ HTML samples)
├── output/    logs/
├── main.py  requirements.txt  README.md  AI_USAGE.md  pytest.ini  .gitignore
```

## Sources

- https://books.toscrape.com/ : 1000 books over 50 listing pages; category and description are available only on each book's detail page.
- https://quotes.toscrape.com/ : 100 quotes over 10 pages; author biography is available only on each author page.

Both sites are sandboxes built for scraping. The client uses a descriptive User-Agent, a delay between requests, and no authentication or CAPTCHA bypassing.

## Python Version

Python 3.11+ (developed on 3.12).

Dependencies: `requests`, `beautifulsoup4`, `pandas`, `pytest` (see `requirements.txt`).

## Installation

```bash
python -m venv .venv
```

Activate it:

- Windows (PowerShell): `.venv\Scripts\Activate.ps1`  (cmd: `.venv\Scripts\activate.bat`)
- Linux / macOS: `source .venv/bin/activate`

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

Optional arguments:

`--delay 0.3` (seconds between requests), `--timeout 10`, `--max-pages N` (limit listing pages per source, useful for a quick trial), `--output-dir`, `--log-dir`.

A full run makes about 1,060 requests (50 listing pages + 1000 book detail pages + 10 quote pages + about 50 author pages), so at the default delay it takes roughly 6–10 minutes.

For a quick trial:

```bash
python main.py --max-pages 2
```

Exit code is `0` if at least one record was produced, and `1` otherwise.

## Pagination

Pagination is dynamic.

After each page is parsed, the scraper looks for the next-page link (`li.next a` on both sites), resolves its `href` against the current page URL using `urllib.parse.urljoin`, requests that URL, and continues until there is no next link.

There is no hard-coded page count.

Safeguards include:

- A `visited` set prevents pagination loops.
- A next link without `href` is logged and treated as the end.
- `--max-pages` is only a manual limit for testing.

## Data Model

Every record contains the required fields.

Fields that do not apply to a particular source remain empty (`None` in Python and blank in the CSV). No data is invented.

| Field             | Books to Scrape                                                   | Quotes to Scrape                                                             |
| ----------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `source`        | `books_toscrape`                                                | `quotes_toscrape`                                                          |
| `source_url`    | product detail page URL                                           | URL of the page where the quote was found (quotes have no page of their own) |
| `name_or_title` | book title (full`title` attribute, not the truncated link text) | quote text (decorative quotation marks removed in cleaning)                  |
| `category`      | category from the detail-page breadcrumb                          | empty                                                                        |
| `price`         | numeric price in GBP                                              | empty                                                                        |
| `rating`        | integer 1-5 (from`One`...`Five`)                              | empty                                                                        |
| `author`        | empty                                                             | author name                                                                  |
| `tags`          | empty                                                             | tags joined with`\|` in the CSV                                             |
| `description`   | product description (empty if the book has none)                  | author biography:`Born: <date> <place>.` + biography text                  |
| `scraped_at`    | UTC ISO-8601 timestamp                                            | same                                                                         |

**Two documented extensions** beyond the required fields, because the assignment asks for them to be captured:

- `availability` (books, e.g. `In stock (22 available)`)
- `author_url` (quotes)

Remove them from `models/record.py` if you want the schema strictly limited to the ten required fields.

## Cleaning

Cleaning is handled in `processing/cleaning.py` and is kept separate from scraping.

- Text: Unicode NFC, non-breaking spaces and repeated whitespace are collapsed, and leading/trailing whitespace is removed.
- Missing values: empty strings and placeholders (`N/A`, `null`, `none`, `-`, ...) become `None`.
- Price: `"£51.77"`, `"Â£51.77"` (mis-decoded), and `"£1,051.50"` become floats; unparsable values become `None`.
- Rating: `"Three"`, `"3"`, and `3.0` become integer `3`. Out-of-range numbers are kept so validation can reject and report them.
- URLs: made absolute, fragments removed, scheme/host lower-cased, only `http(s)` accepted; otherwise `None`.
- Tags: trimmed, empty and repeated tags removed.
- Quotes: the wrapping `“ ”` is removed.
- Records with no name/title after cleaning are removed and counted as "removed during cleaning".

## Validation

Records failing any rule go to `output/rejected_records.csv` with their reasons and are counted in the summary.

| Reason                                 | Rule                                         |
| -------------------------------------- | -------------------------------------------- |
| `unknown_source`                     | source must be a known source                |
| `missing_name`                       | name/title required                          |
| `missing_url` / `invalid_url`      | URL required and must be a valid http(s) URL |
| `invalid_price`                      | when present, must be a finite number >= 0   |
| `invalid_rating`                     | when present, must be 1-5                    |
| `missing_price` / `missing_rating` | required for books                           |
| `missing_author`                     | required for quotes                          |

Category and description are never required. Some books have no description, and a failed detail page should not discard a valid book.

## Deduplication

Two records are duplicates when they share the same:

**source + normalised name + normalised author + price**

Normalization lower-cases, strips accents and punctuation, and collapses whitespace.

For example:

```text
"Example Book Title"
" Example   Book Title "
"EXAMPLE BOOK TITLE"
```

are treated as the same value.

The same normalization also makes `It's` and `It’s` match.

The same title with a different price is treated as a different item, possibly representing a different edition. The same quote text by a different author is kept, and identical text from different sources is never merged.

URLs are not used because every quote on a page shares one URL.

The first occurrence is kept and later duplicates are removed and logged. Every removal is counted using `duplicates_detected` and `duplicates_removed`. None are "flagged and retained" in this version.

## Error Handling

- Timeouts, connection errors and HTTP `429/500/502/503/504` are retried (3 attempts, exponential backoff 1s, 2s). Other 4xx errors, such as 404 and 403, are not retried.
- After the final failure the client returns `None`; the scraper records the URL in the summary and continues.
- A failed **detail/author page** keeps the record and leaves the detail fields empty. Each detail/author page is requested at most once through caching.
- A failed **listing page** stops pagination for that source because the next link is unknown, but records already collected are kept, and the other source still runs.
- Missing HTML elements give `None` plus a warning instead of raising an exception.
- `main.py` isolates each source with a logged `try/except`; unexpected errors in one source do not stop the other.

## Logging

Each run writes:

```text
logs/scrape_<timestamp>.log
```

The same information is also echoed to the console.

The logs record:

- Source start/end
- Every request and retry
- Page completion with record counts
- Pagination continuation
- HTTP/parsing problems
- Validation rejections
- Duplicates
- Output files

Only URLs and counts are logged.

## Outputs

- `output/final_dataset.csv` : final records, one consistent schema (UTF-8 with BOM so Excel shows `£` correctly).
- `output/summary_report.json` : records collected per source, removed during cleaning, after cleaning, rejected during validation (with reason counts), duplicates detected/removed/flagged, final count (total and per source), execution time, and per-source scraping stats (pages requested/succeeded, failed pages, failed detail pages).
- `output/rejected_records.csv` : rejected records with `rejection_reasons`.

## Testing

```bash
pytest
```

95 tests run without internet.

HTML fixtures in `tests/fixtures/` and a fake HTTP client feed the scrapers. The tests cover:

- Parsing
- Missing fields
- Pagination, including failures, loops and relative links
- Cleaning
- Validation
- Deduplication
- Exact, whitespace and capitalization cases
- Must-not-merge cases
- Retry and backoff logic
- End-to-end consolidation

## Assumptions

- Both sites keep their current HTML structure and use `li.next a` for pagination.
- "Price" is the listed GBP price; currency is not stored separately.
- Quotes have no individual URL, so the page URL is used as `source_url`.
- Author biography is stored in `description` for quote records.
- Pages are UTF-8.

## Known Limitations

- **The live run was not verified by the author of this code in the build environment** (network access to the target sites was blocked there). Selectors follow the sites' public structure; run `python main.py --max-pages 2` once on your machine to confirm.
- Test fixtures are small hand-written samples of that structure, not saved copies of the real pages.
- A failed listing page ends pagination for that source.
- Scraping is sequential and takes several minutes for the full run.
- No checkpoint/resume; the dedup key cannot recognise paraphrased or near-duplicate titles.

## AI Usage

AI assistance was used during development for planning, implementation, testing, debugging, code review and documentation.

Claude was used during the initial development to help design and generate the project structure, scrapers, processing logic, tests and documentation.

ChatGPT was used for reviewing the implementation against the assignment requirements, identifying issues, simplifying code, and refining the final implementation.
