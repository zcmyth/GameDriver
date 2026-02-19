import logging
import time


def run_game_loop(
    engine,
    strategy,
    sleep_seconds=2,
    max_iter=9_999_999,
    hooks=None,
):
    logger = logging.getLogger(__name__)
    hooks = hooks or {}

    for i in range(max_iter):
        if callable(hooks.get('before_sleep')):
            hooks['before_sleep'](engine=engine, strategy=strategy, iteration=i)

        time.sleep(sleep_seconds)
        logger.info('Processing iteration: %s/%s', i + 1, max_iter)

        if callable(hooks.get('before_refresh')):
            hooks['before_refresh'](engine=engine, strategy=strategy, iteration=i)

        engine.refresh()

        if callable(hooks.get('before_step')):
            hooks['before_step'](engine=engine, strategy=strategy, iteration=i)

        try:
            strategy.step(engine, i)
        except Exception as exc:
            logger.exception('Strategy step failed at iteration %s', i)
            if callable(hooks.get('on_error')):
                hooks['on_error'](
                    engine=engine,
                    strategy=strategy,
                    iteration=i,
                    error=exc,
                )
            else:
                raise

        if callable(hooks.get('after_step')):
            hooks['after_step'](engine=engine, strategy=strategy, iteration=i)
