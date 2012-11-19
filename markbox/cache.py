# -*- coding: utf-8 -*-
from __future__ import absolute_import


class Cache(object):
    "Wrapper around a memcache object with a decorator for caching handlers"

    def __init__(self):
        self.pool = None
        # inject backend and uncache_key later

    def use_pooling(self):
        import pylibmc
        self.pool = pylibmc.ClientPool(self.backend, 20)

    def cached(self, cachekey, dep_cachekeys=[]):
        def decorator(fn):
            def wrapper(*args, **kwargs):  # kwargs is query string
                ck = cachekey(args)
                if "uncache_key" in kwargs and \
                        kwargs["uncache_key"] == self.uncache_key:
                    self.delete_multi(dep_cachekeys + [ck])
                    content = None
                else:
                    content = self.get(ck)
                if not content:
                    content = fn(*args, **kwargs)
                self.set(ck, content)
                return content
            return wrapper
        return decorator

    def __getattr__(self, name):
        if self.pool:
            with self.pool.reserve() as mc:
                return getattr(mc, name)
        return getattr(self.backend, name)
