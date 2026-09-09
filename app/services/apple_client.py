import asyncio
import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.exceptions import (
    AppNotFoundError,
    InvalidAppIdentifierError,
    InvalidSourceResponseError,
    ReviewSourceUnavailableError,
)
from app.schemas.reviews import AppSummary, Review

APP_ID_PATTERN = re.compile(r"(?:^|/)id(?P<app_id>\d+)(?:[/?#]|$)")


class AppleClient:
    """Small client for Apple's public lookup and customer-review feeds."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        max_attempts: int = 4,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self.http_client = http_client
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds

    @staticmethod
    def extract_app_id(value: str) -> str:
        candidate = value.strip()
        if candidate.isdigit():
            return candidate

        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or parsed.hostname != "apps.apple.com":
            raise InvalidAppIdentifierError(
                "app must be a numeric App Store ID or an apps.apple.com URL"
            )

        match = APP_ID_PATTERN.search(parsed.path)
        if not match:
            raise InvalidAppIdentifierError("The App Store URL does not contain an app ID")
        return match.group("app_id")

    async def lookup_app(self, app_id: str, country: str) -> AppSummary:
        payload = await self._get_json(
            "https://itunes.apple.com/lookup",
            params={"id": app_id, "country": country, "entity": "software"},
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise InvalidSourceResponseError("Apple lookup returned an unexpected response")
        if not results:
            raise AppNotFoundError(
                f"Application {app_id} was not found in the {country} storefront"
            )

        item = results[0]
        return AppSummary(
            id=app_id,
            name=str(item.get("trackName") or f"App {app_id}"),
            developer=item.get("artistName"),
            bundle_id=item.get("bundleId"),
            country=country,
            store_url=item.get("trackViewUrl"),
        )

    async def fetch_reviews_page(
        self,
        app_id: str,
        country: str,
        page: int,
    ) -> list[Review]:
        page_size = 20
        url = f"https://apps.apple.com/api/apps/v1/catalog/{country}/apps/{app_id}/reviews"
        payload = await self._get_json(
            url,
            params={
                "platform": "web",
                "offset": str((page - 1) * page_size),
                "limit": str(page_size),
            },
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; AppStoreReviewAnalysis/0.1)",
            },
            empty_on_404=True,
        )
        entries = payload.get("data", [])
        if not isinstance(entries, list):
            raise InvalidSourceResponseError("Apple review endpoint contains invalid data")

        reviews: list[Review] = []
        for entry in entries:
            review = self._parse_review(entry, country)
            if review is not None:
                reviews.append(review)
        return reviews

    @staticmethod
    def _parse_review(entry: Any, country: str) -> Review | None:
        if not isinstance(entry, dict) or entry.get("type") != "user-reviews":
            return None

        try:
            attributes = entry["attributes"]
            return Review(
                id=str(entry["id"]),
                # `or ""` also covers an explicit JSON null, which `.get(key, "")`
                # would otherwise turn into the literal string "None".
                title=str(attributes.get("title") or ""),
                text=str(attributes.get("review") or ""),
                rating=int(attributes["rating"]),
                author=attributes.get("userName"),
                created_at=attributes.get("date"),
                country=country,
            )
        except (KeyError, TypeError, ValueError):
            return None

    async def _get_json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        *,
        empty_on_404: bool = False,
    ) -> dict[str, Any]:
        """Fetch JSON with retries.

        ``empty_on_404`` marks endpoints where 404 means "nothing here" (paging
        past the last review page). Elsewhere a 404 means Apple's API itself
        changed or broke - a missing app returns HTTP 200 with no results - so
        it is reported as an unavailable source rather than silently emptied.
        """
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = await self.http_client.get(url, params=params, headers=headers)
                response.raise_for_status()
                payload = json.loads(response.text, strict=False)
                if not isinstance(payload, dict):
                    raise InvalidSourceResponseError("Apple returned JSON in an unexpected format")
                return payload
            except InvalidSourceResponseError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == self.max_attempts:
                    raise ReviewSourceUnavailableError(
                        "Apple review source is temporarily unavailable"
                    ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404 and empty_on_404:
                    return {"data": []}
                retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
                if not retryable or attempt == self.max_attempts:
                    raise ReviewSourceUnavailableError(
                        f"Apple review source returned HTTP {exc.response.status_code}"
                    ) from exc

                retry_after = exc.response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    await asyncio.sleep(min(float(retry_after), 30.0))
                    continue
            except ValueError as exc:
                raise InvalidSourceResponseError("Apple returned invalid JSON") from exc

            await asyncio.sleep(self.retry_delay_seconds * (2 ** (attempt - 1)))

        raise ReviewSourceUnavailableError("Apple review source is temporarily unavailable")
