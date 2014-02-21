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


def convert_to_international(number, smsc):
    if number.startswith('+'):
        return number
    else:
        if smsc.startswith('+55'): # brazil
            return '+55' + number[1:]
        if smsc.startswith('+39'): # italy
            return '+39' + number
        raise ValueError('convert_to_int. number=%s smsc=%s' % (number, smsc))
