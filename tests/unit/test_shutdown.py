"""app.ui.shutdown: stop all first, then wait within one shared budget."""

from __future__ import annotations

import time

from app.ui.shutdown import Work, drain, still_running


def test_drain_stops_everything_before_waiting() -> None:
    events: list[str] = []
    works = [Work(n, lambda ms, n=n: events.append(f"wait {n}") or True, lambda n=n: events.append(f"stop {n}"))
             for n in ("a", "b")]
    assert drain(works, 100) == []
    assert events == ["stop a", "stop b", "wait a", "wait b"]


def test_drain_shares_one_budget_and_reports_what_still_runs() -> None:
    asked: list[int] = []

    def slow(ms: int) -> bool:
        asked.append(ms)
        time.sleep(ms / 1000)
        return False

    t0 = time.monotonic()
    left = drain([Work("hung", slow, lambda: None), Work("also", slow, lambda: None), Work("ok", lambda ms: True,
                                                                                         lambda: None)], 200)
    assert left == ["hung", "also"]
    assert time.monotonic() - t0 < 0.4  # one budget, not one per worker
    assert asked[0] <= 200 and asked[1] <= 20


def test_still_running_does_not_wait() -> None:
    assert still_running([Work("x", lambda ms: ms == 0 and False, lambda: None), Work("y", lambda ms: True,
                                                                                     lambda: None)]) == ["x"]


def test_settle_uses_one_deadline_for_all_rounds() -> None:
    """Review RV11-V4-02: many rounds must not multiply the wait."""
    from app.ui.shutdown import settle

    asked: list[int] = []

    def slow_then_done(ms: int) -> bool:
        asked.append(ms)
        time.sleep(min(ms, 60) / 1000)
        return True

    deliveries = iter([1] * 10 + [0])
    t0 = time.monotonic()
    settle(lambda: [Work("x", slow_then_done, lambda: None)], 200, rounds=20, deliver=lambda: next(deliveries))
    assert time.monotonic() - t0 < 0.5  # ~200 ms budget in total, not 200 ms per round
    assert asked == sorted(asked, reverse=True) and asked[-1] <= 20
