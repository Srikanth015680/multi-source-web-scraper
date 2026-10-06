import json

import pandas as pd

from main import main
from models.record import (
    COLUMNS,
    SOURCE_BOOKS,
    SOURCE_QUOTES,
    Record,
    ScrapeStats,
)
from processing.consolidation import (
    build_summary,
    consolidate,
    write_dataset,
    write_rejected,
    write_summary,
)


def raw_records() -> dict[str, list[Record]]:
    books = [
        Record(
            SOURCE_BOOKS,
            "https://books.toscrape.com/a_1/index.html",
            " A Light in the Attic ",
            "Poetry",
            "£51.77",
            "Three",
        ),
        Record(
            SOURCE_BOOKS,
            "https://books.toscrape.com/a_1/index.html",
            "A LIGHT IN THE ATTIC",
            "Poetry",
            "£51.77",
            "Three",
        ),
        Record(
            SOURCE_BOOKS,
            "https://books.toscrape.com/b_2/index.html",
            "Bad Price Book",
            "Poetry",
            "£-3.00",
            "Two",
        ),
        Record(
            SOURCE_BOOKS,
            "https://books.toscrape.com/c_3/index.html",
            "   ",
            "Poetry",
            "£5.00",
            "Two",
        ),
    ]

    quotes = [
        Record(
            SOURCE_QUOTES,
            "https://quotes.toscrape.com/",
            "“Be yourself.”",
            author="Oscar Wilde",
            tags=["life"],
        ),
        Record(
            SOURCE_QUOTES,
            "https://quotes.toscrape.com/page/2/",
            "“Be  yourself.”",
            author="oscar wilde",
        ),
    ]

    return {
        SOURCE_BOOKS: books,
        SOURCE_QUOTES: quotes,
    }


def test_consolidate_counts_each_stage():
    result = consolidate(raw_records())

    assert result.collected == {
        SOURCE_BOOKS: 4,
        SOURCE_QUOTES: 2,
    }
    assert sum(result.after_cleaning.values()) == 5
    assert len(result.rejected) == 1
    assert result.rejection_reasons == {"invalid_price": 1}
    assert len(result.duplicates) == 2
    assert len(result.records) == 2
    assert result.final_per_source == {
        SOURCE_BOOKS: 1,
        SOURCE_QUOTES: 1,
    }


def test_outputs_are_written_with_consistent_schema(tmp_path):
    result = consolidate(raw_records())

    stats = {
        SOURCE_BOOKS: ScrapeStats(pages_requested=1),
        SOURCE_QUOTES: ScrapeStats(),
    }

    summary = build_summary(
        result,
        stats,
        1.234,
    )

    write_dataset(
        result.records,
        tmp_path / "final_dataset.csv",
    )
    write_rejected(
        result.rejected,
        tmp_path / "rejected_records.csv",
    )
    write_summary(
        summary,
        tmp_path / "summary_report.json",
    )

    frame = pd.read_csv(
        tmp_path / "final_dataset.csv",
        encoding="utf-8-sig",
    )

    assert list(frame.columns) == COLUMNS
    assert set(frame["source"]) == {
        SOURCE_BOOKS,
        SOURCE_QUOTES,
    }

    assert "3.0" not in (
        tmp_path / "final_dataset.csv"
    ).read_text(encoding="utf-8-sig")

    assert (
        frame.loc[
            frame["source"] == SOURCE_BOOKS,
            "rating",
        ].tolist()
        == [3]
    )

    loaded = json.loads(
        (tmp_path / "summary_report.json").read_text(
            encoding="utf-8"
        )
    )

    assert loaded["total_records_collected"] == 6
    assert loaded["records_removed_during_cleaning"] == 1
    assert loaded["total_records_after_cleaning"] == 5
    assert loaded["records_rejected_during_validation"] == 1
    assert loaded["duplicates_detected"] == 2
    assert loaded["duplicates_removed"] == 2
    assert loaded["final_record_count"] == 2
    assert loaded["execution_time_seconds"] == 1.23
    assert loaded["per_source"][SOURCE_BOOKS]["final"] == 1


def test_main_survives_total_network_failure(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "utils.http_client.HttpClient.get",
        lambda self, url: None,
    )

    code = main(
        [
            "--output-dir",
            str(tmp_path / "out"),
            "--log-dir",
            str(tmp_path / "logs"),
        ]
    )

    assert code == 1

    summary = json.loads(
        (tmp_path / "out" / "summary_report.json").read_text(
            encoding="utf-8"
        )
    )

    assert summary["final_record_count"] == 0
    assert summary["scraping"][SOURCE_BOOKS]["failed_pages"]

    assert list(
        (tmp_path / "logs").glob("*.log")
    )