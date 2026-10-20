"""Tests for the rolling daily quota."""

from __future__ import annotations

from app.geography.quota import DailyQuota


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_consumes_up_to_the_limit() -> None:
    quota = DailyQuota(3, clock=FakeClock())
    assert [quota.try_consume() for _ in range(4)] == [True, True, True, False]
    assert quota.remaining() == 0
    assert quota.exhausted()


def test_window_rolls_over_after_24h() -> None:
    clock = FakeClock()
    quota = DailyQuota(2, clock=clock)
    assert quota.try_consume() and quota.try_consume()
    assert quota.exhausted()

    clock.advance(86_399)
    assert quota.exhausted(), "window must not reset early"

    clock.advance(2)
    assert not quota.exhausted()
    assert quota.remaining() == 2


def test_zero_limit_is_immediately_exhausted() -> None:
    quota = DailyQuota(0, clock=FakeClock())
    assert quota.exhausted()
    assert quota.try_consume() is False


def test_reset_restores_budget() -> None:
    quota = DailyQuota(1, clock=FakeClock())
    quota.try_consume()
    assert quota.exhausted()
    quota.reset()
    assert quota.remaining() == 1
