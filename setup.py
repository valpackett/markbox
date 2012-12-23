#!/usr/bin/env python
import sys
from setuptools import setup

if sys.version < "2.5":
    sys.exit("Python 2.5 or higher is required")

setup(
    name="markbox",
    version="0.1.10",
    description="A blogging engine for Dropbox based on Markdown",
    # long_description="""""",
    license="Apache License 2.0",
    author="myfreeweb",
    author_email="floatboth@me.com",
    url="https://github.com/myfreeweb/markbox",
    install_requires=[
        "redis", "Jinja2", "dropbox", "markdown", "pygments",
        "cherrypy", "python-dateutil", "mdx_smartypants", "pyatom"
    ],
    packages=["templates", "markbox"],
    keywords=["web", "http", "dropbox", "markdown", "blog"],
    classifiers=[
        "Environment :: Web Environment",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP",
    ],
    package_data={
        "": ["*.html"]
    },
)
