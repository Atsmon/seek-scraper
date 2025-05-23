import argparse
import logging
import mimetypes
import os

from collections import OrderedDict
from datetime import datetime
from urllib.parse import urlparse


import requests

from bs4 import BeautifulSoup
from ebooklib import epub


def setup_logging(verbose_level):
    """Configure logging based on verbosity level."""
    log_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}  # Default to WARNING level
    log_level = log_levels.get(verbose_level, logging.DEBUG)

    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def _sanitize_nav_links(elem):
    """Remove wrapper anchor tags that correspond to navigation blocks or that solely wrap images."""
    NAV_TEXTS = ("Previous Chapter", "Next Chapter")

    # -- Unwrap anchors --
    for a in elem.find_all("a"):
        # Navigation anchors containing Previous/Next Chapter strong tag
        if a.find("strong", string=lambda t: t in NAV_TEXTS if t else False):
            a.unwrap()
            continue
        # Pure image links (no visible text)
        if a.find("img") and not a.get_text(strip=True):
            a.unwrap()

    # -- Remove standalone navigation strong tags or text nodes --
    # Remove strong tags with nav text
    for s in elem.find_all("strong"):
        if s.get_text(strip=True) in NAV_TEXTS:
            s.decompose()

    # Remove any bare strings exactly matching nav texts
    from bs4 import NavigableString

    for text_node in list(elem.find_all(string=True)):
        if isinstance(text_node, NavigableString) and text_node.strip() in NAV_TEXTS:
            text_node.extract()

    return elem


class Chapter:
    def __init__(self, link):
        logging.info(f"Scraping chapter from: {link}")
        self._link = link

        request = requests.get(link)
        self._raw = BeautifulSoup(request.content, "html.parser")

        # Extract all properties immediately
        self._arc = self._scrape_arc()
        self._name = self._scrape_name()
        self._previous_chapter = self._scrape_previous_chapter() if self._has_previous_chapter() else None
        self._next_chapter = self._scrape_next_chapter() if self._has_next_chapter() else None
        self._content_html, self._text, self._images = self._extract_content()

    def __hash__(self):
        return hash(self._raw)

    def __eq__(self, other):
        return self._raw == other._raw

    def _extract_content(self):
        logging.info(f"Extracting content from {self._name}")

        # Find the main content div
        content_div = self._raw.find("div", class_="entry-content")
        if not content_div:
            logging.warning("No content div found")
            return None, "", []

        # Create a new BeautifulSoup object for the content
        content_soup = BeautifulSoup('<div class="chapter-content"></div>', "html.parser")
        content_div_new = content_soup.find("div")

        # Find all relevant elements (include figure to capture standalone images)
        elements = content_div.find_all(["p", "div", "figure"])
        start_index = None
        end_index = None
        text = ""
        image_urls = []

        # Check if this is the first chapter by looking for Previous Chapter at the start
        is_first_chapter = True
        for element in elements[:3]:  # Only check first few elements
            strong_tags = element.find_all("strong")
            for strong in strong_tags:
                if strong.text == "Previous Chapter":
                    is_first_chapter = False
                    break
            if not is_first_chapter:
                break

        logging.debug(f"Is first chapter: {is_first_chapter}")

        # Find the first "Next Chapter" to start content (common for all chapters)
        for i, element in enumerate(elements):
            strong_tags = element.find_all("strong")
            for strong in strong_tags:
                if strong.text == "Next Chapter":
                    logging.debug(f"Found Next Chapter #1 at {i}")
                    start_index = i
                    logging.debug(f"Setting start index at {i}")
                    break
            if start_index is not None:
                break

        # For first chapter, find the second "Next Chapter" to end content
        end_marker = "Next Chapter" if is_first_chapter else "Previous Chapter"

        if start_index is not None:
            for i, element in enumerate(elements[start_index + 1 :], start=start_index + 1):
                strong_tags = element.find_all("strong")
                for strong in strong_tags:
                    if strong.text == end_marker:
                        end_index = i - 1  # exclude navigation paragraph
                        logging.debug(
                            f"Found navigation marker '{strong.text}' at {i}, setting end index to {end_index}"
                        )
                        break
                if end_index is not None:
                    break

        # Copy any image-only elements that appear BEFORE the navigation header so they aren't lost
        if start_index is not None:
            for element in elements[:start_index]:
                if element.find("img"):
                    sanitized = _sanitize_nav_links(element)
                    content_div_new.append(sanitized)
                    for img_tag in sanitized.find_all("img"):
                        src = img_tag.get("src")
                        src = src.split('?')[0]  # Remove params to avoid scaling issues
                        if src and src not in image_urls:
                            image_urls.append(src)

        if start_index is None or end_index is None:
            logging.warning("Could not find content markers, copying all content")
        else:
            logging.debug(f"Extracting content from index {start_index + 1} to {end_index + 1}")
            elements = elements[start_index + 1 : end_index + 1]  # include end element

        for element in elements:
            element = _sanitize_nav_links(element)
            # Add !important to all inline styles to override Lithium's override
            if "style" in element.attrs:
                element.attrs["style"] += " !important"
            content_div_new.append(element)
            # Collect images within this element
            for img_tag in element.find_all("img"):
                src = img_tag.get("src")
                src = src.split('?')[0]  # Remove params to avoid scaling issues
                if src and src not in image_urls:
                    image_urls.append(src)
            if element.name == "p":
                text += f"\n\n{element.text}"

        return str(content_soup), text.strip(), image_urls

    def _scrape_name(self):
        chapter_number = self._raw.title.string.strip().split()[0].upper()
        if chapter_number.endswith("0"):
            # Fix first arc Orion chapters being called .0 instead of .O.
            chapter_number = f"{chapter_number[:-1]}O"
        return chapter_number

    def _scrape_arc(self):
        return self._raw.title.string.strip().split()[2]

    def _has_previous_chapter(self):
        return any(
            [
                p.strong is not None and p.strong.text == "Previous Chapter" and p.a is not None
                for p in self._raw.find_all("p")
            ]
        )

    def _has_next_chapter(self):
        return any(
            [
                p.strong is not None and p.strong.text == "Next Chapter" and p.a is not None
                for p in self._raw.find_all("p")
            ]
        )

    def _scrape_previous_chapter(self):
        return [
            a for a in self._raw.find_all("a") if a.strong is not None and a.strong.text == "Previous Chapter"
        ][0]["href"]

    def _scrape_next_chapter(self):
        return [
            a for a in self._raw.find_all("a") if a.strong is not None and a.strong.text == "Next Chapter"
        ][0]["href"]

    @property
    def link(self):
        return self._link

    @property
    def arc(self):
        return self._arc

    @property
    def name(self):
        return self._name

    @property
    def previous_chapter(self):
        return self._previous_chapter

    @property
    def next_chapter(self):
        return self._next_chapter

    @property
    def content_html(self):
        return self._content_html

    @property
    def text(self):
        return self._text

    @property
    def images(self):
        return self._images

    @property
    def word_count(self):
        return len(self.text.split())


class Arc(OrderedDict):
    def __init__(self, name, *args, **kwargs):
        self._name = name

        super().__init__(*args, **kwargs)

    def __hash__(self):
        return hash(self.name) ^ super().__hash__()

    def __eq__(self, other):
        return self.name == other.name and super().__eq__(other)

    @property
    def name(self):
        return self._name

    @property
    def word_count(self):
        return sum([chapter.word_count for chapter in self.values()])


class Scraper(OrderedDict):
    FIRST_CHAPTER_URL = "https://seekwebserial.wordpress.com/2024/10/18/0-1-0-hack/"

    def __init__(self, *args, **kwargs):
        self._book = OrderedDict()
        self._is_scraped = False

        super().__init__(*args, **kwargs)

    def scrape(self):
        chapter = Chapter(self.FIRST_CHAPTER_URL)
        while True:
            if chapter.arc not in self:
                self[chapter.arc] = Arc(chapter.arc)
            self[chapter.arc][chapter.name] = chapter

            if chapter.next_chapter is None:
                break

            chapter = Chapter(chapter.next_chapter)

        self._is_scraped = True

    def print_word_count(self):
        # ANSI color codes
        HEADER = "\033[1;36m"  # Cyan
        TOTAL = "\033[1;32m"  # Green
        ARC = "\033[1;33m"  # Yellow
        CHAPTER = "\033[0;37m"  # White
        PERCENT = "\033[0;36m"  # Cyan
        RESET = "\033[0m"  # Reset

        # Print header
        print("\n" + "=" * 60)
        print(f"{HEADER}SEEK Word Count Analysis{RESET}")
        print("=" * 60)

        # Print total word count with formatting
        total_words = self.word_count
        print(f"\n{TOTAL}Total Word Count: {total_words:,}{RESET}")
        print("-" * 60)

        # Store arc statistics for summary
        arc_stats = []

        # Print arc and chapter breakdowns
        for arc in self.values():
            arc_percent = (arc.word_count / total_words) * 100
            arc_stats.append((arc.name, arc.word_count, arc_percent))

            print(f"\n{ARC}Arc: {arc.name}{RESET}")
            print(f"   ├─ Word Count: {arc.word_count:,} ({PERCENT}{arc_percent:.1f}%{RESET})")
            print("   └─ Chapters:")

            # Calculate max chapter name length for alignment
            max_chapter_len = max(len(chapter.name) for chapter in arc.values())

            # Get list of chapters for this arc
            chapters = list(arc.values())

            for i, chapter in enumerate(chapters):
                # Calculate chapter percentage of arc
                chapter_percent = (chapter.word_count / arc.word_count) * 100
                # Format chapter name with padding for alignment
                chapter_name = chapter.name.ljust(max_chapter_len)
                # Use └─ for last chapter, ├─ for others
                pipe = "└─" if i == len(chapters) - 1 else "├─"
                print(
                    f"      {pipe} {CHAPTER}{chapter_name}{RESET} : {chapter.word_count:,} ({PERCENT}{chapter_percent:.1f}%{RESET})"
                )

        # Print summary section
        print("\n" + "=" * 60)
        print(f"{HEADER}Summary{RESET}")
        print("-" * 60)

        # Sort arcs by word count
        arc_stats.sort(key=lambda x: x[1], reverse=True)

        # Print arc summary
        print(f"\n{ARC}Arc Statistics (sorted by word count):{RESET}")
        for i, (arc_name, arc_words, arc_percent) in enumerate(arc_stats):
            pipe = "└─" if i == len(arc_stats) - 1 else "├─"
            print(f"   {pipe} {arc_name}: {arc_words:,} words ({PERCENT}{arc_percent:.1f}%{RESET})")

        # Calculate and print averages
        avg_chapters_per_arc = sum(len(arc) for arc in self.values()) / len(self)
        avg_words_per_chapter = total_words / sum(len(arc) for arc in self.values())
        avg_words_per_arc = total_words / len(self)

        print(f"\n{HEADER}Average Statistics:{RESET}")
        print(f"   ├─ Average chapters per arc: {avg_chapters_per_arc:.1f}")
        print(f"   ├─ Average words per chapter: {avg_words_per_chapter:,.0f}")
        print(f"   └─ Average words per arc: {avg_words_per_arc:,.0f}")

        print("\n" + "=" * 60 + "\n")

    @property
    def word_count(self):
        return sum([arc.word_count for arc in self.values()])

    def create_epub(self, output_path=None):
        """Create an EPUB file from the scraped content."""
        if not self._is_scraped:
            self.scrape()

        # Create EPUB book
        book = epub.EpubBook()

        # Set metadata
        book.set_identifier("seek-webserial")
        book.set_title("SEEK")
        book.set_language("en")
        book.add_author("John C. McCrae (Wildbow)")
        book.add_metadata("DC", "description", "SEEK webserial by John C. McCrae (Wildbow)")
        book.add_metadata("DC", "date", datetime.now().strftime("%Y-%m-%d"))

        # Prepare image cache to avoid duplicate downloads across chapters
        image_cache = {}  # url -> (file_name, mime_type)

        # Create title page
        title_page = epub.EpubHtml(title="SEEK", file_name="title.xhtml", lang="en")
        title_page.content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>SEEK</title>
            <link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\" />
        </head>
        <body>
            <h1 style=\"text-align:center !important; margin-top:40vh;\">SEEK</h1>
        </body>
        </html>
        """
        book.add_item(title_page)

        # Create chapters
        spine = [title_page]
        toc = []

        # Process each arc
        for i, (arc_name, arc) in enumerate(self.items()):
            # Create arc title page
            arc_page = epub.EpubHtml(title=arc_name, file_name=f"{arc_name}.xhtml", lang="en")
            arc_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{arc_name}</title>
                <link rel="stylesheet" type="text/css" href="style.css" />
            </head>
            <body>
                <h1>Arc {i + 1}: {arc_name}</h1>
            </body>
            </html>
            """
            arc_page.content = arc_content
            book.add_item(arc_page)
            spine.append(arc_page)

            # Add arc title to TOC
            arc_toc = []

            # Process each chapter in the arc
            for chapter_name, chapter in arc.items():
                # Create chapter
                c = epub.EpubHtml(title=chapter_name, file_name=f"{chapter_name}.xhtml", lang="en")

                # ---------- Handle images in chapter ----------
                # Parse the chapter HTML to find images
                chapter_soup = BeautifulSoup(chapter.content_html, "html.parser")

                for img_tag in chapter_soup.find_all("img"):
                    img_url = img_tag.get("src").split('?')[0]  # Remove params to avoid scaling issues
                    if not img_url:
                        continue

                    # If we've already processed this image, reuse the cached filename
                    if img_url in image_cache:
                        file_name, mime_type = image_cache[img_url]
                    else:
                        try:
                            response = requests.get(img_url)
                            response.raise_for_status()
                            img_data = response.content
                        except Exception as exc:
                            logging.warning(f"Failed to download image {img_url}: {exc}")
                            continue

                        # Derive a safe filename for the image inside the EPUB
                        parsed = urlparse(img_url)
                        base_name = os.path.basename(parsed.path)
                        if not base_name:
                            base_name = f"img_{len(image_cache)}"

                        # Always store images under an images/ folder inside the EPUB
                        base_name = base_name.replace(" ", "_")  # remove spaces

                        # Ensure filename uniqueness (consider folder)
                        unique_name = f"images/{base_name}"
                        counter = 1
                        while any(unique_name == val[0] for val in image_cache.values()):
                            name_part, ext_part = os.path.splitext(base_name)
                            unique_name = f"images/{name_part}_{counter}{ext_part}"
                            counter += 1

                        # Guess mime type, default to jpeg if unknown/unsupported
                        mime_type, _ = mimetypes.guess_type(unique_name)
                        if mime_type is None or not mime_type.startswith("image"):
                            # Fallback
                            mime_type = "image/jpeg"

                        # Add image to the EPUB using EpubImage helper
                        image_item = epub.EpubItem(
                            uid=unique_name, file_name=unique_name, media_type=mime_type, content=img_data
                        )
                        book.add_item(image_item)

                        # Cache it
                        image_cache[img_url] = (unique_name, mime_type)
                        file_name = unique_name

                    # Remove all remote attributes
                    img_tag.attrs.clear()

                    # Point the <img> tag to the local image file
                    img_tag["src"] = file_name

                    # Ensure inline centering for readers that ignore external CSS
                    existing_style = img_tag.get("style", "")
                    centering_style = (
                        "display:block;margin-left:auto;margin-right:auto;max-width:100%;height:auto;"
                    )
                    if centering_style not in existing_style:
                        img_tag["style"] = f"{existing_style} {centering_style}".strip()

                # ---------- Build final chapter HTML ----------
                content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{chapter_name}</title>
                    <link rel="stylesheet" type="text/css" href="style.css" />
                </head>
                <body>
                    <h1>{chapter_name}</h1>
                    {str(chapter_soup)}
                </body>
                </html>
                """

                c.content = content

                # Add chapter to book
                book.add_item(c)
                spine.append(c)
                arc_toc.append(c)

            # Add arc to TOC
            toc.append((epub.Link(f"{arc_name}.xhtml", arc_name, arc_name), arc_toc))

        # Add default NCX and Nav files
        book.toc = toc
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Create CSS
        style = """
        body {
            font-family: Cambria, Liberation Serif, Bitstream Vera Serif, Georgia, Times, Times New Roman, serif;
            line-height: 1.5;
            padding: 2em;
            margin: 0 auto;
            max-width: 35em;
        }
        h1 {
            font-size: 1.5em;
            margin-bottom: 0.5em;
        }
        .chapter-content {
            margin-top: 2em;
        }
        /* Center images horizontally */
        .chapter-content img {
            display: block;
            margin-left: auto;
            margin-right: auto;
            max-width: 100%;
            height: auto;
        }
        /* existing chapter-content img rule can stay but global rule ensures */
        """
        css = epub.EpubItem(uid="style_nav", file_name="style.css", media_type="text/css", content=style)
        book.add_item(css)

        # Create spine
        book.spine = spine

        # Set output path
        if output_path is None:
            output_path = "SEEK.epub"

        # Write EPUB file
        epub.write_epub(output_path, book, {})
        return output_path


def main(args):
    setup_logging(args.verbose)

    scraper = Scraper()
    scraper.scrape()

    scraper.print_word_count()

    if args.epub:
        output_path = scraper.create_epub(args.output)
        logging.info(f"EPUB created successfully: {output_path}")


def parse_args(args=None, namespace=None):
    parser = argparse.ArgumentParser("SEEK Word Counter")

    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-e", "--epub", action="store_true", help="Create EPUB version of the book")
    parser.add_argument("-o", "--output", help="Output path for EPUB file (default: SEEK.epub)")

    return parser.parse_args(args, namespace)


def cli():
    """Entry-point for command line usage (e.g. via `seek-scraper` console script)."""
    cli_args = parse_args()
    main(cli_args)


if __name__ == "__main__":
    cli()
