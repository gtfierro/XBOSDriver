#!/usr/bin/env python3

from distutils.core import setup

setup(name='XBOSDriver',
      version='0.0.1',
      description='Drivers for XBOS',
      author='Gabe Fierro',
      author_email='gtfierro@eecs.berkeley.edu',
      packages=['XBOSDriver','XBOSDriver.drivers'],
      scripts=['bin/xbos-driver-start'],
     )
