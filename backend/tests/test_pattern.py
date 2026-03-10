"""Unit tests for the pattern calculation helpers."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.modules.pattern import _calculate_interval, _calculate_next_due


def test_calculate_interval_basic():
    """Evenly spaced gaps should return the mean."""
    gaps = [28, 28, 28]
    interval, outliers = _calculate_interval(gaps)
    assert interval == 28.0
    assert outliers == 0


def test_calculate_interval_varied():
    """Varied but non-outlier gaps."""
    gaps = [25, 30, 28, 27]
    interval, outliers = _calculate_interval(gaps)
    assert 25 <= interval <= 30
    assert outliers == 0


def test_calculate_interval_with_outliers():
    """A very large gap should be removed as an outlier."""
    gaps = [28, 30, 120, 29]  # 120 is > 2x median(~29)
    interval, outliers = _calculate_interval(gaps)
    assert outliers == 1
    assert 28 <= interval <= 30


def test_calculate_interval_empty():
    interval, outliers = _calculate_interval([])
    assert interval == 0.0
    assert outliers == 0


def test_calculate_next_due():
    """Next due date should be last booking + interval days."""
    mock_booking = MagicMock()
    mock_booking.scheduled_at = datetime(2025, 6, 1, 10, 0, tzinfo=timezone.utc)

    result = _calculate_next_due([mock_booking], 28.0)
    assert result == date(2025, 6, 29)


def test_calculate_next_due_empty():
    result = _calculate_next_due([], 28.0)
    assert result is None
