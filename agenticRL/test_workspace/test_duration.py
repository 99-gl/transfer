import pytest

from duration import format_duration


@pytest.mark.parametrize(
    ("total_seconds", "expected"),
    [
        (0, "0s"),
        (59, "59s"),
        (60, "1m 0s"),
        (61, "1m 1s"),
        (3600, "1h 0m 0s"),
        (3661, "1h 1m 1s"),
        (7325, "2h 2m 5s"),
    ],
)
def test_format_duration(total_seconds: int, expected: str) -> None:
    assert format_duration(total_seconds) == expected


def test_negative_duration_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        format_duration(-1)
