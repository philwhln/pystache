#!/usr/bin/env python

from distutils.core import setup

README = open("README.rst").read()

setup(
    name='pystache',
    version='0.4.0',
    description='Mustache for Python',
    long_description=README,
    author='Chris Wanstrath',
    author_email='chris@ozmm.org',
    url='http://github.com/defunkt/pystache',
    packages=['pystache'],
    license='MIT',
    classifiers = [
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
    ]
)

