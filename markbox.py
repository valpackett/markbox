#!/usr/bin/env python
# Markbox - a blogging engine for Dropbox based on Markdown
# by Greg V <floatboth@me.com> http://floatboth.com

import os
import dropbox
import markdown
from parsedatetime.parsedatetime import Calendar
from bottle import Bottle, request, response, redirect, static_file, abort
from jinja2 import Environment, FileSystemLoader
from pyatom import AtomFeed
from time import mktime
from datetime import datetime

here = lambda a: os.path.join(os.path.dirname(__file__), a)

class Markbox(object):
    def __init__(self, public_folder="public", tpl_folder="templates",
            blog_title="Your New Markbox Blog", feed_name="articles",
            feed_author="Anonymous"):
        self.app = Bottle()
        self.cal = Calendar()
        self.tpl = Environment(loader=FileSystemLoader([tpl_folder,
            here("templates")]))
        self.tpl.globals["blog_title"] = blog_title
        self.tpl.globals["feed_name"] = feed_name

        if "MEMCACHE_SERVERS" in os.environ:
            import pylibmc
            self.cache = pylibmc.Client(
                servers=[os.environ.get("MEMCACHE_SERVERS")],
                username=os.environ.get("MEMCACHE_USERNAME"),
                password=os.environ.get("MEMCACHE_PASSWORD"),
                binary=True)
        else:
            import mockcache
            self.cache = mockcache.Client()

        if "DROPBOX_APP_KEY" in os.environ and \
                "DROPBOX_APP_SECRET" in os.environ:
            self.db_app_key = os.environ.get("DROPBOX_APP_KEY")
            self.db_app_secret = os.environ.get("DROPBOX_APP_SECRET")
        else:
            print "Dropbox credentials not found in the env."
            print "Set DROPBOX_APP_KEY and DROPBOX_APP_SECRET env variables!"

        uncache_key = os.environ.get("UNCACHE_KEY")
        if not uncache_key:
            print "Uncache key not found in the env."

        def uncacheable(cachekey):
            def decorator(fn):
                def wrapper(*args, **kwargs):
                    if uncache_key and request.query.uncache_key == uncache_key:
                        self.cache.delete(cachekey(kwargs))
                    return fn(*args, **kwargs)
                return wrapper
            return decorator

        def cached(cachekey):
            def decorator(fn):
                def wrapper(*args, **kwargs):
                    content = self.cache.get(cachekey(kwargs))
                    if not content:
                        content = fn(*args, **kwargs)
                    return content
                return wrapper
            return decorator

        def ctype(ct):
            def decorator(fn):
                def wrapper(*args, **kwargs):
                    response.content_type = ct
                    return fn(*args, **kwargs)
                return wrapper
            return decorator

        @self.app.route("/public/<filename>")
        def static(filename):
            return static_file(filename, root=public_folder)

        @self.app.route("/"+feed_name+".xml")
        @ctype("application/atom+xml; charset=utf-8")
        @uncacheable(lambda a: "feed")
        @cached(lambda a: "feed")
        def feed():
            d = self.dropbox_connect()
            try:
                posts = self.dropbox_listing(d)
                host = "http://"+request.headers.get("Host")
                atom = AtomFeed(title=blog_title, url=host,
                        feed_url=host+"/"+feed_name+".xml",
                        author=feed_author)
                for post in posts:
                    atom.add(title=post["title"],
                            url=host+post["path"],
                            author=feed_author,
                            content_type="html",
                            content=post["html"],
                            updated=post["date"])
                content = atom.to_string()
                self.cache.set("feed", content)
                return content
            except dropbox.rest.ErrorResponse, e:
                return self.dropbox_error(e)

        tpl_post = self.tpl.get_template("post.html")
        @self.app.route("/<title>")
        @uncacheable(lambda a: a["title"])
        @cached(lambda a: a["title"])
        def post(title):
            d = self.dropbox_connect()
            try:
                src = self.dropbox_file(d, title + ".md")
                mdown = self.markdown()
                html = mdown.convert(src)
                content = tpl_post.render(body=html,
                        page_title=mdown.Meta["title"][0],
                        date=mdown.Meta["date"][0])
                self.cache.set(title, content)
                return content
            except dropbox.rest.ErrorResponse, e:
                if e.status == 404:
                    abort(404, "File not found")
                else:
                    return self.dropbox_error(e)

        tpl_list = self.tpl.get_template("list.html")
        @self.app.route("/")
        @uncacheable(lambda a: "index")
        @cached(lambda a: "index")
        def listing():
            d = self.dropbox_connect()
            try:
                posts = self.dropbox_listing(d)
                content = tpl_list.render(posts=posts)
                self.cache.set("index", content)
                return content
            except dropbox.rest.ErrorResponse, e:
                return self.dropbox_error(e)

        tpl_404 = self.tpl.get_template("404.html")
        @self.app.error(404)
        def handle_404(error):
            return tpl_404.render(page_title="Page not found")

    def markdown(self):
        return markdown.Markdown(extensions=["meta", "extra",
            "codehilite", "headerid(level=2)", "sane_lists",
            "smartypants"])

    def dropbox_listing(self, d):
        files = d.search("/", ".md")
        posts = []
        for f in files:
            cont = self.dropbox_file(d, f["path"])
            mdown = self.markdown()
            html = mdown.convert(cont)
            if "title" in mdown.Meta and "date" in mdown.Meta:
                posts.append({
                    "path": f["path"][:-3],
                    "title": mdown.Meta["title"][0],
                    "date": datetime.fromtimestamp(mktime(self.cal.parse(mdown.Meta["date"][0])[0])),
                    "html": html
                })
            else:
                print "No title and/or date in file: " + f["path"]
        posts = sorted(posts, key=lambda p: p["date"])
        posts.reverse()
        return posts

    def dropbox_file(self, d, fname):
        r = d.get_file(fname)
        cont = r.read()
        r.close()
        return cont

    def read_file(self, fname):
        try:
            return open(fname, "r").read()
        except IOError:
            return None

    def dropbox_connect(self):
        sess = dropbox.session.DropboxSession(self.db_app_key,
                self.db_app_secret, "app_folder")
        s_token = self.cache.get("s_token") or self.read_file(".s_token")
        s_token_secret = self.cache.get("s_token_secret") or self.read_file(".s_token_secret")
        if s_token and s_token_secret:
            sess.set_token(s_token, s_token_secret)
        elif request.query.oauth_token:
            s_token = sess.obtain_access_token(dropbox.session.OAuthToken(\
                self.cache.get("r_token"), self.cache.get("r_token_secret")))
            self.cache.set("s_token", s_token.key)
            self.cache.set("s_token_secret", s_token.secret)
            open(".s_token", "w").write(s_token.key)
            open(".s_token_secret", "w").write(s_token.secret)
            self.cache.delete("r_token")
            self.cache.delete("r_token_secret")
        else:
            req_token = sess.obtain_request_token()
            self.cache.set("r_token", req_token.key)
            self.cache.set("r_token_secret", req_token.secret)
            callback = "http://" + request.headers.get("Host") + \
                request.path
            url = sess.build_authorize_url(req_token, callback)
            redirect(url)  # throws an exception
        return dropbox.client.DropboxClient(sess)

    def dropbox_error(self, e):
        import traceback
        return "<!DOCTYPE html><pre>Dropbox error: " + \
                traceback.format_exc(e) + "</pre>"
