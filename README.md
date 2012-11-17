# Markbox

A blog engine based on Markdown and Dropbox.
Designed for Heroku, but works on any server.
Like one of [these](http://calepin.co/), but not as-a-Service.
Hackable.
Just a little more than 200 lines of Python.
Based on [CherryPy](http://www.cherrypy.org/).

Pretty opinionated:
- only [Jinja2](http://jinja.pocoo.org/docs/templates/) templates
- only Memcache for caching
- only Atom feed
- only Dropbox
- only Markdown with [SmartyPants](https://bitbucket.org/jeunice/mdx_smartypants), [Pygments](http://packages.python.org/Markdown/extensions/code_hilite.html), [extras](http://packages.python.org/Markdown/extensions/extra.html) (tables, footnotes, etc.)

## Quick Start

First, go to [dropbox.com/developers/apps](https://www.dropbox.com/developers/apps), create an app (Type: Core API, Access: App folder, any name and description), get the API key and secret.

Then, add some files to a fresh git repo:

Procfile:
```bash
web: python run.py
```

requirements.txt:
```bash
pylibmc
git+git://github.com/myfreeweb/markbox.git@master
```
(note: you have to explicitly specify pylibmc for the Heroku bulidpack to build libmemcached)

run.py:
```python
import os
from markbox import Markbox, here

m = Markbox(
    blog_title="Some Kind of Blog",
    author="Greg"
)

m.run(port=int(os.environ.get("PORT")))
```

Now, deploy to Heroku with the app name you want, your Dropbox credentials and an uncache key -- any string you want, this is like a password, but only for cleaning the cache:
```bash
heroku create NAME
heroku config:set DROPBOX_APP_KEY=key DROPBOX_APP_SECRET=secret UNCACHE_KEY=uncache_key
heroku addons:add memcache
git push heroku master
```

Visit your app, sign in with Dropbox. Add posts to your Dropbox/Apps/(the name you set up in the API configuration) with .md as extension and this format:
```markdown
Title: Some Title
Date: 15 Nov 2012

This is the post.

# This is an h2, because the title is an h1.

Some text.
```

To clean the cache of a page, add `?uncache_key=KEY` with the KEY you set when deploying to Heroku.
You have to do this on the index page and the feed when you publish a new post.
