from __future__ import absolute_import
import os
import markdown
import cherrypy
from jinja2 import Environment, FileSystemLoader
from pyatom import AtomFeed
from time import mktime
from datetime import datetime
from parsedatetime.parsedatetime import Calendar
from .cache import Cache
from .dropbox import Dropbox

here = lambda a: os.path.join(os.path.dirname(__file__), a)


def ctype(ct):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            cherrypy.response.headers['Content-Type'] = ct
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_markdown():
    return markdown.Markdown(extensions=[
        "meta", "extra", "codehilite", "headerid(level=2)",
        "sane_lists", "smartypants"
    ])


class Markbox(object):
    cache = Cache()
    dropbox = Dropbox()
    cal = Calendar()

    def __init__(self, public_folder="public", tpl_folder="templates",
            blog_title="Your New Markbox Blog", feed_name="articles",
            feed_author="Anonymous"):
        self.tpl = Environment(loader=FileSystemLoader([tpl_folder,
            here("../templates")]))
        self.tpl.globals["blog_title"] = self.blog_title = blog_title
        self.tpl.globals["feed_name"] = self.feed_name = feed_name
        self.public_folder = public_folder
        self.feed_author = feed_author

        # CherryPy routes by method name, here we set the method name
        setattr(self, feed_name + "_xml", self._feed)

        if "MEMCACHE_SERVERS" in os.environ:
            import pylibmc
            self.cache.backend = pylibmc.Client(
                servers=[os.environ.get("MEMCACHE_SERVERS")],
                username=os.environ.get("MEMCACHE_USERNAME"),
                password=os.environ.get("MEMCACHE_PASSWORD"),
                binary=True)
        else:
            import mockcache
            self.cache.backend = mockcache.Client()

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
    @cache.cached(lambda a: "feed")
    @dropbox.connected
    def _feed(self, *args, **kwargs):
        host = cherrypy.request.base
        atom = AtomFeed(title=self.blog_title, url=host,
                feed_url=cherrypy.url(),
                author=self.feed_author)
        for post in self.listing():
            atom.add(title=post["title"],
                    url=host + post["path"],
                    author=self.feed_author,
                    content_type="html",
                    content=post["html"],
                    updated=post["date"])
        return atom.to_string()

    @cherrypy.expose
    @cache.cached(lambda a: a[1])  # title from (self, title)
    @dropbox.connected
    def default(self, title, **kwargs):
        src = self.dropbox.read_file(title + ".md")
        mdown = get_markdown()
        html = mdown.convert(src)
        tpl_post = self.tpl.get_template("post.html")
        return tpl_post.render(body=html,
                page_title=mdown.Meta["title"][0],
                date=mdown.Meta["date"][0])

    @cherrypy.expose
    @cache.cached(lambda a: "index")
    @dropbox.connected
    def index(self, *args, **kwargs):
        tpl_list = self.tpl.get_template("list.html")
        return tpl_list.render(posts=self.listing())

    def run(self, host="0.0.0.0", port=8080):
        cherrypy.config.update({
            "server.socket_host": host,
            "server.socket_port": port
        })
        cherrypy.quickstart(self, "/", {
            "/" + os.path.basename(self.public_folder): {
                "tools.staticdir.on": True,
                "tools.staticdir.dir": self.public_folder
            }
        })

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
                    "date": datetime.fromtimestamp(
                        mktime(self.cal.parse(mdown.Meta["date"][0])[0])),
                    "html": html
                })
            else:
                cherrypy.log("No title and/or date in file: " + f["path"])
        posts = sorted(posts, key=lambda p: p["date"])
        posts.reverse()
        return posts
