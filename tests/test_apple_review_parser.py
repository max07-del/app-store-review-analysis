from app.services.apple_client import AppleClient


def test_parses_app_store_web_review() -> None:
    entry = {
        "id": "123456",
        "type": "user-reviews",
        "attributes": {
            "date": "2026-09-01T10:30:00Z",
            "rating": 2,
            "review": "The application crashes after the update.",
            "title": "Latest update",
            "userName": "example_user",
        },
    }

    review = AppleClient._parse_review(entry, "us")

    assert review is not None
    assert review.id == "123456"
    assert review.rating == 2
    assert review.text == "The application crashes after the update."
    assert review.country == "us"


def test_skips_non_review_resources() -> None:
    assert AppleClient._parse_review({"id": "1", "type": "apps"}, "us") is None
