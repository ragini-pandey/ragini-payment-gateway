"""Verify the retry backoff schedule matches the documented design."""

from __future__ import annotations

import pytest

from app.workers.tasks.dispatch_delivery import BACKOFF_SECONDS, _backoff_with_jitter


def test_schedule_matches_design() -> None:
    assert BACKOFF_SECONDS == (60, 300, 1800, 7200, 43200, 86400)


@pytest.mark.parametrize("attempt", [1, 2, 3, 4, 5, 6, 99])
def test_jitter_within_bounds(attempt: int) -> None:
    base = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
    for _ in range(50):
        v = _backoff_with_jitter(attempt)
        assert v >= 1
        assert v <= int(base * 1.16)  # +15% + rounding slack
        assert v >= int(base * 0.84)
