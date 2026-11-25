import pytest

from pipeline.retry import retry_call


def test_succeeds_after_transient_failures():
    calls = {"count": 0}
    delays = []

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("temporary")
        return "ok"

    result = retry_call(
        flaky,
        attempts=3,
        base_delay_seconds=1.0,
        max_delay_seconds=10.0,
        sleep=delays.append,
    )

    assert result == "ok"
    assert calls["count"] == 3
    assert delays == [1.0, 2.0]


def test_raises_after_attempts_exhausted():
    calls = {"count": 0}

    def always_fails():
        calls["count"] += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        retry_call(
            always_fails,
            attempts=3,
            sleep=lambda delay: None,
        )

    assert calls["count"] == 3


def test_non_retryable_error_is_not_retried():
    calls = {"count": 0}

    def fails_once():
        calls["count"] += 1
        raise ValueError("permanent")

    with pytest.raises(ValueError):
        retry_call(
            fails_once,
            attempts=5,
            retry_if=lambda exc: False,
            sleep=lambda delay: None,
        )

    assert calls["count"] == 1


def test_delay_is_capped():
    delays = []
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 4:
            raise RuntimeError("temporary")
        return "ok"

    retry_call(
        flaky,
        attempts=4,
        base_delay_seconds=2.0,
        max_delay_seconds=3.0,
        sleep=delays.append,
    )

    assert delays == [2.0, 3.0, 3.0]
