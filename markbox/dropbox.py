# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import with_statement
import dropbox
import cherrypy
from contextlib import closing
from dropbox.client import DropboxClient
from dropbox.session import DropboxSession


def read_file(fname):
    try:
        with open(fname, "r") as f:
            return f.read()
    except IOError:
        return None


class Dropbox(object):
    def __init__(self):
        self.client = None

    def read_file(self, fname):
        with closing(self.client.get_file(fname)) as r:
            return r.read().decode("utf-8")

    def connect(self, query):
        sess = DropboxSession(self.app_key, self.app_secret, "app_folder")
        # Access token is saved to memcache and the filesystem
        s_token = self.cache.get("s_token") or read_file(".s_token")
        s_secret = self.cache.get("s_secret") or read_file(".s_secret")
        if s_token and s_secret:
            sess.set_token(s_token, s_secret)
        elif "oauth_token" in query:  # callback from Dropbox
            s_token = sess.obtain_access_token(dropbox.session.OAuthToken(
                self.cache.get("r_token"), self.cache.get("r_token_secret")))
            self.cache.set("s_token", s_token.key)
            self.cache.set("s_secret", s_token.secret)
            with open(".s_token", "w") as f:
                f.write(s_token.key)
            with open(".s_secret", "w") as f:
                f.write(s_token.secret)
            self.cache.delete("r_token")
            self.cache.delete("r_token_secret")
        else:  # start of Dropbox auth
            req_token = sess.obtain_request_token()
            self.cache.set("r_token", req_token.key)
            self.cache.set("r_token_secret", req_token.secret)
            url = sess.build_authorize_url(req_token, cherrypy.url())
            raise cherrypy.HTTPRedirect(url)
        self.client = DropboxClient(sess)

    def connected(self, fn):
        def wrapper(*args, **kwargs):
            if not self.client:
                self.connect(kwargs)
            try:
                return fn(*args, **kwargs)
            except dropbox.rest.ErrorResponse, e:
                if e.status == 404:
                    raise cherrypy.HTTPError(404, "File not found")
                else:
                    return self.error_html(e)
        return wrapper

    def error_html(self, e):
        import traceback
        return "<!DOCTYPE html><pre>Dropbox error: " + \
            traceback.format_exc(e) + "</pre>"
