#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()

setup(
    name='msgbox',
    version='dev',
    description='modem based http/sms gateway implemented in Python',
    author='Paolo Losi',
    author_email='paolo.losi@gmail.com',
    url='https://github.com/paolo-losi/msgbox',
    packages=[
        'msgbox',
    ],
    include_package_data=True,
    install_requires=[
        'tornado == 3.2',
        'python-gsmmodem',
    ],
    scripts=['bin/msgbox'],
    license="MIT",
    zip_safe=False,
)
