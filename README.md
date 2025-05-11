# SEEK Scraper

Scraper and EPUB generator for Wildbow's web-serial **SEEK**.

---

## Features

* **Scrape** every published chapter starting from the first (uses the in-chapter navigation links to crawl forward).
* **Word count analysis** – prints a coloured breakdown by arc and chapter, plus summary statistics.
* **EPUB builder** – optionally downloads linked images and packages the entire serial into a nicely-formatted EPUB file.

## Installation

> Requires Python 3.8+

### From PyPI (when released)
```bash
pip install seek-scraper
```

### From source
```bash
# Clone the repository (or download)
cd seek-scraper
pip install .  # installs the console-script `seek-scraper`
```

## Command-line usage
```text
usage: seek-scraper [-h] [-v] [-e] [-o OUTPUT]
```

Flag | Description
---- | -----------
`-v`, `-vv`, ... | Increase logging verbosity (use twice for `DEBUG`).
`-e`, `--epub` | Build an EPUB after scraping.
`-o`, `--output PATH` | Custom path/filename for the EPUB (default: `SEEK.epub`).

### Examples
1. **Print word-count statistics only**
   ```bash
   seek-scraper
   ```

2. **Generate an EPUB in the current directory**
   ```bash
   seek-scraper -e
   ```

3. **Generate an EPUB with a custom filename and verbose logging**
   ```bash
   seek-scraper -v -e -o ~/Books/Seek_2025-01-01.epub
   ```

## Output explained

### Word Count Report
After scraping, a formatted table like this is printed (colours shown in supporting terminals):

```
============================================================
SEEK Word Count Analysis
============================================================

Total Word Count: 192,714
------------------------------------------------------------

Arc 1: HACK
   ├─ Word Count: 22,057 (11.4%)
   └─ Chapters:
      ├─ 0.1.O : 4,870 (22.1%)
      ├─ 0.2.B : 4,597 (20.8%)
      ├─ 0.3.W : 6,714 (30.4%)
      └─ 0.4.O : 5,876 (26.6%)

Arc 2: MUTE
   ├─ Word Count: 46,983 (24.4%)
   └─ Chapters:
      ├─ 1.1.B : 5,391 (8.5%)
      ├─ 1.2.W : 9,344 (14.7%)
      ├─ 1.3.B : 6,345 (10.0%)
      ├─ 1.4.W : 8,853 (13.9%)
      ...

============================================================
Summary
------------------------------------------------------------
Arc Statistics (sorted by word count):
   ├─ CONTROL: 63,750 words (33.1%)
   ├─ MUTE:    46,983 words (24.4%)
   ...

Average Statistics:
   ├─ Average chapters per arc: 6.2
   ├─ Average words per chapter: 7,709
   └─ Average words per arc: 48,179

============================================================
```
It ends with summary statistics such as average words per arc/chapter.

### EPUB file
When `--epub` is supplied the program downloads every chapter (including images) and writes a standards-compliant EPUB, e.g. `SEEK.epub`.

Structure of the book:
* Title page.
* Arc title pages.
* One XHTML file per chapter, retaining inline images (centred & responsive).
* A stylesheet (`style.css`) that sets reasonable typography.

You can side-load the generated file into any reader that supports EPUB 3 (e.g. Calibre, Apple Books, KOReader, etc.).

## Development & Contributing
Pull requests are welcome—especially improvements to parsing edge-cases, additional output formats, or CI.

### Running locally
```bash
python -m seek-scraper.main --help  # directly via module
python seek-scraper/main.py --epub  # via path
```

### Tests
_No formal test-suite yet. Manual invocation is the easiest way to verify behaviour._

## License
This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.
