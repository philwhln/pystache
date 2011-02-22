#!/usr/bin/env python

from distutils.core import setup

README = open("README.md").read()

setup(
    name='pystache',
    version='0.4.x-dev',
    description='Mustache for Python',
    long_description=README,
    author='Paul J. Davis',
    author_email='paul.joseph.davis@gmail.com',
    url='http://github.com/davisp/pystache',
    packages=['pystache'],
    license='MIT',
    classifiers = [
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
    ]
)

