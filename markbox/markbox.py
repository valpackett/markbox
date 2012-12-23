# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import markdown
import cherrypy
from zlib import crc32
from pyatom import AtomFeed
from jinja2 import Environment, FileSystemLoader
from dateutil.parser import parse as parsedate
from .cache import Cache, NoCache
from .dropbox import Dropbox
from cherrypy.process import servers

def fake_wait_for_occupied_port(host, port):
    return

servers.wait_for_occupied_port = fake_wait_for_occupied_port

here = lambda a: os.path.join(os.path.dirname(__file__), a)


def ctype(ct):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            cherrypy.response.headers['Content-Type'] = ct
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def reading_time(text):
    words = len(text.split(" "))
    minutes = words / 250
    txt = "%s minutes, " % minutes if minutes > 0 else ""
    txt += "%02d seconds" % round(float(words) % 250 / 250 * 60)
    return txt


def get_markdown():
    return markdown.Markdown(extensions=[
        "meta", "extra", "codehilite", "headerid(level=2)",
        "sane_lists", "smartypants"
    ])


class Markbox(object):
    cache = Cache()
    dropbox = Dropbox()

    def public_url(self, url):
        with open(os.path.join(self.public_folder, url)) as f:
            return "/%s?v=%s" % (
                    os.path.join(os.path.basename(self.public_folder), url),
                    crc32(f.read()))

    def __init__(self, public_folder="public", tpl_folder="templates",
            blog_title="Your New Markbox Blog", feed_name="articles",
            author="Anonymous", bare_files=[]):
        self.tpl = Environment(loader=FileSystemLoader([tpl_folder,
            here("../templates")]))
        self.tpl.globals["blog_title"] = self.blog_title = blog_title
        self.tpl.globals["feed_name"] = self.feed_name = feed_name
        self.tpl.globals["author"] = self.author = author
        self.tpl.globals["public_url"] = self.public_url
        self.public_folder = public_folder
        self.bare_files = bare_files

        # CherryPy routes by method name, here we set the method name
        setattr(self, feed_name + "_xml", self._feed)

        if "REDISTOGO_URL" in os.environ:
            import redis
            self.cache.backend = redis.from_url(os.getenv("REDISTOGO_URL"))
        else:
            self.cache.backend = NoCache()

        if "DROPBOX_APP_KEY" in os.environ and \
                "DROPBOX_APP_SECRET" in os.environ:
            self.dropbox.app_key = os.environ.get("DROPBOX_APP_KEY")
            self.dropbox.app_secret = os.environ.get("DROPBOX_APP_SECRET")
        else:
            cherrypy.log("""Dropbox credentials not found in the env.
            Set DROPBOX_APP_KEY and DROPBOX_APP_SECRET env variables!""")
        self.dropbox.cache = self.cache

        self.cache.uncache_key = os.environ.get("UNCACHE_KEY")
        if not self.cache.uncache_key:
            cherrypy.log("Uncache key not found in the env.")

        def handle_404(status, message, traceback, version):
            tpl_404 = self.tpl.get_template("404.html")
            return tpl_404.render(page_title="Page not found")

        cherrypy.config.update({"error_page.404": handle_404})

    @cherrypy.expose
    @ctype("application/atom+xml; charset=utf-8")
    @cache.cached(lambda a: "feed", ["listing"])
    @dropbox.connected
    def _feed(self, *args, **kwargs):
        host = cherrypy.request.base
        atom = AtomFeed(title=self.blog_title, url=host,
                feed_url=cherrypy.url(),
                author=self.author)
        for post in self.listing():
            atom.add(title=post["title"],
                    url=host + post["path"],
                    author=self.author,
                    content_type="html",
                    content=post["html"],
                    updated=post["date"])
        return atom.to_string()

    @cherrypy.expose
    @cache.cached(lambda a: a[1], ["listing"])  # title from (self, title)
    @dropbox.connected
    def default(self, path, **kwargs):
        listing = self.listing()
        if type(listing) != list:  # cache is corrupt
            self.cache.delete("listing")
            listing = self.listing()
        listing.reverse()
        url_listing = [p["path"] for p in listing]
        if not "/" + path in url_listing:
            raise cherrypy.HTTPError(404, "File not found")
        post_index = url_listing.index("/" + path)
        prev_post = next_post = None
        if post_index > 0:
            prev_post = listing[post_index - 1]
        if post_index < len(listing) - 1:
            next_post = listing[post_index + 1]
        src = self.dropbox.read_file(path + ".md")
        mdown = get_markdown()
        html = mdown.convert(src)
        tpl_post = self.tpl.get_template("post.html")
        return tpl_post.render(body=html,
                reading_time=reading_time(src),
                page_title=mdown.Meta["title"][0],
                date=parsedate(mdown.Meta["date"][0]),
                prev_post=prev_post,
                next_post=next_post)

    @cherrypy.expose
    @cache.cached(lambda a: "index", ["listing"])
    @dropbox.connected
    def index(self, *args, **kwargs):
        tpl_list = self.tpl.get_template("list.html")
        return tpl_list.render(posts=self.listing())

    def run(self, host="0.0.0.0", port=8080, production=False):
        if production:
            cherrypy.config.update({"environment": "production"})
        cherrypy.config.update({
            "server.socket_host": host,
            "server.socket_port": port
        })
        conf = {
            "/" + os.path.basename(self.public_folder): {
                "tools.staticdir.on": True,
                "tools.staticdir.dir": self.public_folder
            }
        }
        for f in ["humans.txt", "favicon.ico", "robots.txt"] + self.bare_files:
            conf["/" + f] = {
                "tools.staticfile.on": True,
                "tools.staticfile.filename": os.path.join(self.public_folder, f)
            }
        cherrypy.quickstart(self, "/", conf)

    @cache.cached(lambda a: "listing")
    def listing(self):
        files = self.dropbox.client.search("/", ".md")
        posts = []
        for f in files:
            cont = self.dropbox.read_file(f["path"])
            mdown = get_markdown()
            html = mdown.convert(cont)
            if "title" in mdown.Meta and "date" in mdown.Meta:
                posts.append({
                    "path": f["path"][:-3],  # no extension, keep slash
                    "title": mdown.Meta["title"][0],  # wrapped in a list
                    "date": parsedate(mdown.Meta["date"][0]),
                    "html": html
                })
            else:
                cherrypy.log("No title and/or date in file: " + f["path"])
        posts = sorted(posts, key=lambda p: p["date"])
        posts.reverse()
        return posts

    @cherrypy.expose
    def clearcache(self, *args, **kwargs):
        if "uncache_key" in kwargs and \
                kwargs["uncache_key"] == self.cache.uncache_key:
            self.cache.clear()
