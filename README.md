# Markbox

Super simple Heroku-ready, Markdown- and Dropbox-based customizable blog engine.
Like [this](http://calepin.co/), but not as-a-Service.
Based on [CherryPy](http://www.cherrypy.org/).
Runs [my website](http://floatboth.com/).

Pretty opinionated:

- only [Jinja2](http://jinja.pocoo.org/docs/templates/) for templates
- only [Redis](http://redis.io) for caching
- only [Atom](http://en.wikipedia.org/wiki/Atom_\(standard\)) for the feed
- only [Dropbox](http://dropbox.com) for storage
- only [Markdown](http://daringfireball.net/projects/markdown/) with [SmartyPants](https://bitbucket.org/jeunice/mdx_smartypants), [Pygments](http://packages.python.org/Markdown/extensions/code_hilite.html), [extras](http://packages.python.org/Markdown/extensions/extra.html) (tables, footnotes, etc.) for rendering

But you can replace these parts with subclassing or monkey-patching.
Or just forking the whole thing if you want to use Simplenote, Mako, Memcached, RSS and Textile instead of my configuration.

## Quick Start

First, go to [dropbox.com/developers/apps](https://www.dropbox.com/developers/apps), create an app (Type: Core API, Access: App folder, any name and description), get the API key and secret.

Then, add some files to a fresh git repo:

Procfile:
```bash
web: python run.py
```

requirements.txt:
```bash
git+git://github.com/myfreeweb/markbox.git@master
```

run.py:
```python
import os
from markbox import Markbox

m = Markbox(
    blog_title="Some Kind of Blog",
    author="Greg"
)

m.run(port=int(os.environ.get("PORT")))
```

Now, deploy to Heroku with the app name you want, your Dropbox credentials and an *uncache key* -- any string you want, which will be used like a password, but only for cleaning the cache:
```bash
heroku create NAME
heroku config:set DROPBOX_APP_KEY=key DROPBOX_APP_SECRET=secret UNCACHE_KEY=uncache_key
heroku addons:add redistogo
git push heroku master
```

Visit your app and sign in with Dropbox.

Now you can add posts to your Dropbox/Apps/{the name you set up in the API configuration} with .md as the extension and [MultiMarkdown style metadata](https://github.com/fletcher/peg-multimarkdown/wiki/How-do-I-create-a-MultiMarkdown-document%3F) for the title and the date, like this:
```markdown
Title: Some Title
Date: 15 Nov 2012

This is the post.

# This is an h2, because the title is an h1.

Some text.
```

After adding a post, you need to clean the cache of the index page and the feed. To clean the cache of a page, add `?uncache_key=KEY` to the URL, where `KEY` is the key you set when deploying to Heroku.

So, if you saved your post to `Dropbox/Apps/(Blog folder name)/my-first-post.md`, checked that it's correct (and cached it) by visiting `blog-url.tld/my-first-post`, you can make it visible on the index page and the feed by visiting `blog-url.tld/?uncache_key=KEY` and `blog-url.tld/articles.xml?uncache_key=KEY`.

To completely clear the cache (eg. when you update the design or there's an error), visit `blog-url.tld/clearcache?uncache_key=KEY`

## Customization

This is an example of a highly-customized `run.py` (by the way, you can change the name "run.py" to anything you want, just make sure it's correctly referenced in the Procfile):
```python
import os
from markbox import Markbox

here = lambda a: os.path.join(os.path.dirname(os.path.abspath(__file__)), a)

m = Markbox(
    blog_title="{ float: both }",
    author="Greg V",
    public_folder=here("static"),
    tpl_folder=here("html"),
    feed_name="posts",
    bare_files=["style.css"]
)

def cssify(s):
    return "#" + s.lower().replace(" ", "-").replace("'", "").replace("&", "and")

m.tpl.filters["cssify"] = cssify

m.run(port=int(os.environ.get("PORT")), production=True)
```

This example:

- sets the public folder to "static" (**NOTE**: if you want to have any static files, you must specify the public_folder)
- changes the custom template folder to "html" instead of "templates"
- changes the feed URL from "/articles.xml" to "/posts.xml"
- adds style.css to files served from the root (i.e. "/style.css" will be the same as "/public/style.css") – the default list includes humans.txt, robots.txt and favicon.ico
- adds a filter for use in templates

This is how `html/layout.html` might look then:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta content="width=device-width" name="viewport">
    <title>{% if page_title %}{{page_title|cssify}}{% else %}*{% endif %} {{blog_title}}</title>
    <link href="/{{feed_name}}.xml" rel="alternate" type="application/atom+xml">
    <link href="{{public_url('style.css')}}" rel="stylesheet">
  </head>
  <body role="document">{% block main %}{% endblock %}</body>
</html>
```

This shows the use of the `cssify` filter that we added in run.py, which is used on [my blog](http://floatboth.com) for making post titles look like CSS ids and the use of the `public_url` function, which outputs the URL for a static file with a checksum in the query string for cachebusting.
