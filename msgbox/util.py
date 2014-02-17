import functools
import time


def status(status, desc):
    assert status in ('OK', 'ERROR')
    return dict(status=status, desc=desc)


def cached_property(ttl):
    """A memoize decorator for class properties."""
    def wrap(fun):
        @functools.wraps(fun)
        def get(self):
            now = time.time()
            try:
                ret, last_update = self._cache[fun]
                if (now - last_update) < ttl:
                    return ret
            except AttributeError:
                self._cache = {}
            except KeyError:
                pass
            ret = fun(self)
            self._cache[fun] = ret, now
            return ret
        return property(get)
    return wrap
