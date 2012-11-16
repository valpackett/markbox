from __future__ import absolute_import

class Cache(object):
    "Wrapper around a memcache object with a decorator for caching handlers"

    def __init__(self): pass # inject backend and uncache_key later

    def cached(self, cachekey):
        def decorator(fn):
            def wrapper(*args, **kwargs):  # kwargs is query string
                ck = cachekey(args)
                if "uncache_key" in kwargs and kwargs["uncache_key"] == self.uncache_key:
                    self.backend.delete(ck)
                    content = None
                else:
                    content = self.backend.get(ck)
                if not content:
                    content = fn(*args, **kwargs)
                self.backend.set(ck, content)
                return content
            return wrapper
        return decorator

    def __getattr__(self, name):
        return getattr(self.backend, name)
