"""Transport-level tests for AppleClient: retries, error mapping, edge cases."""

import httpx
import pytest

from app.exceptions import (
    AppNotFoundError,
    InvalidSourceResponseError,
    ReviewSourceUnavailableError,
)
from app.services.apple_client import AppleClient

LOOKUP_OK = {
    "resultCount": 1,
    "results": [
        {
            "trackName": "Example App",
            "artistName": "Example Ltd",
            "bundleId": "com.example.app",
            "trackViewUrl": "https://apps.apple.com/us/app/id1",
        }
    ],
}


def make_client(handler) -> tuple[AppleClient, httpx.AsyncClient]:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    # retry_delay_seconds=0 keeps the retry paths fast in tests.
    return AppleClient(http_client, max_attempts=3, retry_delay_seconds=0.0), http_client


def responder(*responses: httpx.Response):
    """Return a handler that replays the given responses in order."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[index]

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


async def test_lookup_returns_app_metadata() -> None:
    client, http = make_client(responder(httpx.Response(200, json=LOOKUP_OK)))
    async with http:
        app = await client.lookup_app("1", "us")

    assert app.name == "Example App"
    assert app.developer == "Example Ltd"
    assert app.bundle_id == "com.example.app"
    assert app.country == "us"


async def test_lookup_reports_a_missing_app() -> None:
    empty = httpx.Response(200, json={"resultCount": 0, "results": []})
    client, http = make_client(responder(empty))
    async with http:
        with pytest.raises(AppNotFoundError):
            await client.lookup_app("999", "us")


async def test_lookup_rejects_a_malformed_payload() -> None:
    client, http = make_client(responder(httpx.Response(200, json={"results": "nope"})))
    async with http:
        with pytest.raises(InvalidSourceResponseError):
            await client.lookup_app("1", "us")


async def test_a_404_on_lookup_is_not_reported_as_a_missing_app() -> None:
    """A missing app returns HTTP 200 with no results, so a 404 means Apple broke."""
    client, http = make_client(responder(httpx.Response(404)))
    async with http:
        with pytest.raises(ReviewSourceUnavailableError):
            await client.lookup_app("1", "us")


async def test_a_404_on_a_review_page_means_no_more_pages() -> None:
    client, http = make_client(responder(httpx.Response(404)))
    async with http:
        assert await client.fetch_reviews_page("1", "us", 99) == []


async def test_rate_limiting_is_retried_then_succeeds() -> None:
    handler = responder(
        httpx.Response(429),
        httpx.Response(200, json={"data": []}),
    )
    client, http = make_client(handler)
    async with http:
        assert await client.fetch_reviews_page("1", "us", 1) == []

    assert handler.calls["n"] == 2  # type: ignore[attr-defined]


async def test_retry_after_header_is_honoured() -> None:
    handler = responder(
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"data": []}),
    )
    client, http = make_client(handler)
    async with http:
        await client.fetch_reviews_page("1", "us", 1)

    assert handler.calls["n"] == 2  # type: ignore[attr-defined]


async def test_persistent_server_errors_exhaust_the_retries() -> None:
    handler = responder(httpx.Response(503))
    client, http = make_client(handler)
    async with http:
        with pytest.raises(ReviewSourceUnavailableError):
            await client.fetch_reviews_page("1", "us", 1)

    assert handler.calls["n"] == 3  # max_attempts  # type: ignore[attr-defined]


async def test_client_errors_are_not_retried() -> None:
    handler = responder(httpx.Response(400))
    client, http = make_client(handler)
    async with http:
        with pytest.raises(ReviewSourceUnavailableError):
            await client.fetch_reviews_page("1", "us", 1)

    assert handler.calls["n"] == 1  # type: ignore[attr-defined]


async def test_timeouts_are_retried_then_reported() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectTimeout("timed out", request=request)

    client, http = make_client(handler)
    async with http:
        with pytest.raises(ReviewSourceUnavailableError):
            await client.fetch_reviews_page("1", "us", 1)

    assert calls["n"] == 3


async def test_invalid_json_is_reported_as_a_source_problem() -> None:
    client, http = make_client(responder(httpx.Response(200, text="<html>not json</html>")))
    async with http:
        with pytest.raises(InvalidSourceResponseError):
            await client.fetch_reviews_page("1", "us", 1)


async def test_a_json_array_is_rejected() -> None:
    client, http = make_client(responder(httpx.Response(200, json=[1, 2, 3])))
    async with http:
        with pytest.raises(InvalidSourceResponseError):
            await client.fetch_reviews_page("1", "us", 1)


async def test_a_non_list_data_field_is_rejected() -> None:
    client, http = make_client(responder(httpx.Response(200, json={"data": {"bad": True}})))
    async with http:
        with pytest.raises(InvalidSourceResponseError):
            await client.fetch_reviews_page("1", "us", 1)


async def test_unparseable_entries_are_skipped_not_fatal() -> None:
    payload = {
        "data": [
            {
                "id": "1",
                "type": "user-reviews",
                "attributes": {"rating": 5, "title": "O", "review": "k"},
            },
            {"id": "2", "type": "user-reviews", "attributes": {"rating": 99}},  # out of range
            {"id": "3", "type": "apps"},  # wrong resource type
            "not-an-object",
        ]
    }
    client, http = make_client(responder(httpx.Response(200, json=payload)))
    async with http:
        reviews = await client.fetch_reviews_page("1", "us", 1)

    assert [review.id for review in reviews] == ["1"]


async def test_null_title_and_body_become_empty_strings() -> None:
    """Apple may send JSON null; it must not surface as the string 'None'."""
    payload = {
        "data": [
            {
                "id": "1",
                "type": "user-reviews",
                "attributes": {"rating": 4, "title": None, "review": None, "userName": "u"},
            }
        ]
    }
    client, http = make_client(responder(httpx.Response(200, json=payload)))
    async with http:
        reviews = await client.fetch_reviews_page("1", "us", 1)

    assert reviews[0].title == ""
    assert reviews[0].text == ""


async def test_review_pages_request_the_right_offset() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json={"data": []})

    client, http = make_client(handler)
    async with http:
        await client.fetch_reviews_page("1", "us", 3)

    assert seen[0].params["offset"] == "40"  # (3 - 1) * 20
    assert seen[0].params["limit"] == "20"
