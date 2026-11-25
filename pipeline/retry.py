import time


class RetryError(RuntimeError):
    def __init__(self, attempts, last_error):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"failed after {attempts} attempts: {last_error}")


def retry_call(
    function,
    attempts=3,
    base_delay_seconds=1.0,
    max_delay_seconds=20.0,
    retry_if=None,
    sleep=time.sleep,
    on_retry=None,
):
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    should_retry = retry_if or (lambda exc: True)
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            return function()
        except Exception as exc:
            last_error = exc
            if attempt == attempts or not should_retry(exc):
                raise
            delay = min(
                max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1))
            )
            if on_retry is not None:
                on_retry(attempt, delay, exc)
            sleep(delay)

    raise RetryError(attempts, last_error)
