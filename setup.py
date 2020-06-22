# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

install_requires = open('requirements.txt').read().split('\n')

setup(
    name='pyvoussoir',
    version='0.2',
    author='Johannes Künsebeck',
    author_email='kuensebeck@googlemail.com',
    description='Automatic de-keystoning/page-splitting tool for single camera book scanners',
    license='Apache License 2.0',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url="https://github.com/hnesk/pyvoussoir",
    packages=['voussoir'],
    install_requires = install_requires,
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Operating System :: OS Independent',
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Topic :: Scientific/Engineering :: Image Recognition'
    ],
    keywords=['OCR', 'page splitting', 'page dewarping', 'keystoning', 'perspective correction', 'voussoir'],
    entry_points={
        'console_scripts': [
            'pyvoussoir = voussoir.cli:main',
        ]
    },
)