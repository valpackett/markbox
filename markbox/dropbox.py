from __future__ import absolute_import
import dropbox
import cherrypy
from time import mktime
from datetime import datetime
from parsedatetime.parsedatetime import Calendar

def read_file(fname):
    try:
        with open(fname, "r") as f:
            return f.read()
    except IOError:
        return None

class Dropbox(object):
    cal = Calendar()

    def __init__(self):
        self.client = None

    def listing(self):
        files = self.client.search("/", ".md")
        posts = []
        for f in files:
            cont = self.read_file(f["path"])
            mdown = self.get_markdown()
            html = mdown.convert(cont)
            if "title" in mdown.Meta and "date" in mdown.Meta:
                posts.append({
                    "path": f["path"][:-3],  # no extension, keep slash
                    "title": mdown.Meta["title"][0],  # wrapped in a list
                    "date": datetime.fromtimestamp(mktime(self.cal.parse(mdown.Meta["date"][0])[0])),
                    "html": html
                })
            else:
                cherrypy.log("No title and/or date in file: " + f["path"])
        posts = sorted(posts, key=lambda p: p["date"])
        posts.reverse()
        return posts

    def read_file(self, fname):
        r = self.client.get_file(fname)
        cont = r.read()
        r.close()
        return cont

    def connect(self, query):
        sess = dropbox.session.DropboxSession(self.app_key,
                self.app_secret, "app_folder")
        # Access token is saved to memcache and the filesystem
        s_token = self.cache.get("s_token") or read_file(".s_token")
        s_token_secret = self.cache.get("s_token_secret") or read_file(".s_token_secret")
        if s_token and s_token_secret:
            sess.set_token(s_token, s_token_secret)
        elif "oauth_token" in query:  # callback from Dropbox
            s_token = sess.obtain_access_token(dropbox.session.OAuthToken(\
                self.cache.get("r_token"), self.cache.get("r_token_secret")))
            self.cache.set("s_token", s_token.key)
            self.cache.set("s_token_secret", s_token.secret)
            with open(".s_token", "w") as f:
                f.write(s_token.key)
            with open(".s_token_secret", "w") as f:
                f.write(s_token.secret)
            self.cache.delete("r_token")
            self.cache.delete("r_token_secret")
        else:  # start of Dropbox auth
            req_token = sess.obtain_request_token()
            self.cache.set("r_token", req_token.key)
            self.cache.set("r_token_secret", req_token.secret)
            url = sess.build_authorize_url(req_token, cherrypy.url())
            raise cherrypy.HTTPRedirect(url)
        self.client = dropbox.client.DropboxClient(sess)

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
