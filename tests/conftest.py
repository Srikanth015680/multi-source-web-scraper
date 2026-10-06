from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeClient:
    """Simple HTTP client replacement for tests."""

    def __init__(self, pages: dict[str, str | None]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def get(self, url: str) -> str | None:
        self.requested.append(url)
        return self.pages.get(url)


@pytest.fixture
def fixture_loader():
    return load_fixture