#!/usr/bin/env python

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="jyserver",
    version="0.0.5",
    author="Fernando Trias",
    author_email="sub@trias.org",
    description="Web Framework with Pythonic Javascript Syntax",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ftrias/jyserver",
    packages=setuptools.find_packages(),
    package_data={ 'jyserver': ['jyserver-min.js'] },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Framework :: Flask",
        "Framework :: Django",
        "Framework :: Bottle",
    ],
    python_requires='>=3.6',
)