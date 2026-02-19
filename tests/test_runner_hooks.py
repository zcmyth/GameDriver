import pytest

from game_driver.runner import run_game_loop


class FakeEngine:
    def __init__(self):
        self.refresh_count = 0

    def refresh(self):
        self.refresh_count += 1


class FakeStrategy:
    def __init__(self, should_fail=False):
        self.calls = []
        self.should_fail = should_fail

    def step(self, engine, i):
        self.calls.append((engine, i))
        if self.should_fail:
            raise RuntimeError('boom')


def test_runner_executes_hooks_in_order():
    engine = FakeEngine()
    strategy = FakeStrategy()
    order = []

    hooks = {
        'before_sleep': lambda **_kwargs: order.append('before_sleep'),
        'before_refresh': lambda **_kwargs: order.append('before_refresh'),
        'before_step': lambda **_kwargs: order.append('before_step'),
        'after_step': lambda **_kwargs: order.append('after_step'),
    }

    run_game_loop(engine, strategy, sleep_seconds=0, max_iter=1, hooks=hooks)

    assert order == ['before_sleep', 'before_refresh', 'before_step', 'after_step']
    assert engine.refresh_count == 1
    assert len(strategy.calls) == 1


def test_runner_on_error_hook_can_handle_exception():
    engine = FakeEngine()
    strategy = FakeStrategy(should_fail=True)
    errors = []

    hooks = {
        'on_error': lambda **kwargs: errors.append(str(kwargs['error'])),
    }

    run_game_loop(engine, strategy, sleep_seconds=0, max_iter=1, hooks=hooks)
    assert errors == ['boom']


def test_runner_raises_without_on_error_hook():
    engine = FakeEngine()
    strategy = FakeStrategy(should_fail=True)

    with pytest.raises(RuntimeError):
        run_game_loop(engine, strategy, sleep_seconds=0, max_iter=1)
