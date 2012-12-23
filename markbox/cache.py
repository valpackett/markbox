# -*- coding: utf-8 -*-
from __future__ import absolute_import
try:
    import cPickle as pickle
except ImportError:
    import pickle


class Cache(object):
    "Wrapper around a Redis-like object with a decorator for caching handlers"

    def __init__(self):
        pass # inject backend and uncache_key later

    def cached(self, cachekey, dep_cachekeys=[]):
        def decorator(fn):
            def wrapper(*args, **kwargs):  # kwargs is query string
                ck = cachekey(args)
                if "uncache_key" in kwargs and \
                        kwargs["uncache_key"] == self.uncache_key:
                    self.delete(ck)
                    for ck in dep_cachekeys:
                        self.delete(ck)
                    content = None
                else:
                    content = self.get(ck)
                if not content:
                    content = fn(*args, **kwargs)
                    self.set(ck, content)
                return content
            return wrapper
        return decorator

    def get(self, key):
        l = self.backend.get(key)
        if l:
            return pickle.loads(l)

    def set(self, key, val):
        return self.backend.set(key, pickle.dumps(val))

    def clear(self):
        keys = self.keys()
        keys.remove("s_token")
        keys.remove("s_secret")
        return [self.delete(k) for k in keys]

    def __getattr__(self, name):
        return getattr(self.backend, name)


class NoCache(object):

    def __init__(self):
        pass

    def get(self, key):
        pass

    def delete(self, key):
        pass

    def clear(self):
        pass

    def set(self, key, value):
        pass
