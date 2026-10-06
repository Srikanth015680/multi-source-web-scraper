import requests

from utils.http_client import HttpClient


class FakeResponse:
    def __init__(self, status_code: int, body: str = "") -> None:
        self.status_code = status_code
        self.content = body.encode("utf-8")

    @property
    def ok(self) -> bool:
        return self.status_code < 400


class FakeSession:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.headers: dict[str, str] = {}
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        outcome = self.outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


def make_client(outcomes, **kwargs):
    sleeps: list[float] = []
    session = FakeSession(outcomes)

    client = HttpClient(
        session=session,
        sleep=sleeps.append,
        min_delay=0,
        backoff_factor=1.0,
        **kwargs,
    )

    return client, session, sleeps


def test_success_returns_text_and_sets_user_agent():
    client, session, _ = make_client(
        [FakeResponse(200, "£ok")]
    )

    assert client.get("https://x.test/") == "£ok"
    assert "User-Agent" in session.headers


def test_retries_on_server_error_with_exponential_backoff():
    client, session, sleeps = make_client(
        [
            FakeResponse(503),
            FakeResponse(503),
            FakeResponse(200, "fine"),
        ]
    )

    assert client.get("https://x.test/") == "fine"
    assert session.calls == 3
    assert sleeps == [1.0, 2.0]


def test_retries_on_timeout_then_gives_up():
    client, session, _ = make_client(
        [requests.Timeout()] * 3
    )

    assert client.get("https://x.test/") is None
    assert session.calls == 3


def test_connection_error_recovers_on_retry():
    client, _, _ = make_client(
        [
            requests.ConnectionError(),
            FakeResponse(200, "back"),
        ]
    )

    assert client.get("https://x.test/") == "back"


def test_client_error_is_not_retried():
    client, session, _ = make_client(
        [FakeResponse(404)]
    )

    assert client.get("https://x.test/") is None
    assert session.calls == 1


def test_unrecoverable_request_exception_returns_none():
    client, session, _ = make_client(
        [requests.exceptions.InvalidURL("bad")]
    )

    assert client.get("nonsense") is None
    assert session.calls == 1


def test_requests_are_rate_limited():
    sleeps: list[float] = []
    now = [0.0]

    session = FakeSession(
        [
            FakeResponse(200),
            FakeResponse(200),
        ]
    )

    client = HttpClient(
        session=session,
        sleep=sleeps.append,
        clock=lambda: now[0],
        min_delay=0.5,
    )

    client.get("https://x.test/1")
    client.get("https://x.test/2")

    assert sleeps == [0.5]