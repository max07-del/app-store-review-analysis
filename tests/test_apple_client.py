import pytest

from app.exceptions import InvalidAppIdentifierError
from app.services.apple_client import AppleClient


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("389801252", "389801252"),
        ("https://apps.apple.com/us/app/instagram/id389801252", "389801252"),
        ("https://apps.apple.com/app/id123456789?l=uk", "123456789"),
    ],
)
def test_extract_app_id(value: str, expected: str) -> None:
    assert AppleClient.extract_app_id(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "instagram",
        "https://example.com/app/id389801252",
        "https://apps.apple.com/us/app/instagram",
    ],
)
def test_extract_app_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidAppIdentifierError):
        AppleClient.extract_app_id(value)
