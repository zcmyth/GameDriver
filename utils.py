# Credit to gregburek@ and andresriancho@
import time

COMMON = [
    'ok',
    'login',
    'login2',
    'submit',
    'close',
    'close2'
]

NON_LOGIN = [
    'ok',
    'submit',
    'close',
    'close2'
]

from functools import wraps


def rate_limited(max_per_second, block=True):
    """
    Decorator that make functions not be called faster than
    """
    min_interval = 1.0 / float(max_per_second)

    def decorate(func):
        last_time_called = [0.0]

        @wraps(func)
        def rate_limited_function(*args, **kwargs):
            elapsed = time.time() - last_time_called[0]
            left_to_wait = min_interval - elapsed

            if left_to_wait > 0 and not block:
                return
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            last_time_called[0] = time.time()
            return func(*args, **kwargs)

        return rate_limited_function

    return decorate
