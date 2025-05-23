from setuptools import setup

# Project metadata
NAME = "seek-scraper"
PACKAGE = "main"  # single-file module
VERSION = "0.2.0"
DESCRIPTION = "Scraper and EPUB generator for Wildbow's webserial SEEK"
URL = "https://github.com/yourusername/seek-scraper"
AUTHOR = "Your Name"
AUTHOR_EMAIL = "you@example.com"
PYTHON_REQUIRES = ">=3.8"
LICENSE = "MIT"

# Dependencies required for the scraper to work
REQUIRED = [
    "requests>=2.28",
    "beautifulsoup4>=4.12",
    "ebooklib>=0.18",
]

# Read the long description from the README file
try:
    with open("README.md", "r", encoding="utf-8") as fh:
        LONG_DESCRIPTION = fh.read()
except FileNotFoundError:
    LONG_DESCRIPTION = DESCRIPTION

setup(
    name=NAME,
    version=VERSION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url=URL,
    python_requires=PYTHON_REQUIRES,
    py_modules=[PACKAGE],
    install_requires=REQUIRED,
    entry_points={
        "console_scripts": [
            "seek-scraper=main:cli",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Utilities",
    ],
    license=LICENSE,
)
