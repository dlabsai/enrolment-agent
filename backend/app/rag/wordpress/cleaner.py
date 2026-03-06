import re

from bs4 import BeautifulSoup, Comment

from app.rag.utils import html_to_markdown as html_to_markdown_

_PATTERN_MULTIPLE_NEWLINES = re.compile(r"\n{3,}")

# Excerpt patterns
_PATTERN_BREADCRUMB1 = re.compile(r"^(Home\s*/\s*[^.]+?)\s*([A-Z])")
_PATTERN_BREADCRUMB2 = re.compile(r"^([A-Za-z]+\s*/\s*[^.]+?)\s*([A-Z])")
_PATTERN_TRUNCATION = re.compile(r"\[…\]|\[&hellip;\]")

_MIN_EXCERPT_LENGTH = 10  # Minimum length for a meaningful excerpt
_MIN_WORD_LENGTH = 3  # Minimum length for a meaningful word
_MIN_SIGNIFICANT_WORD_LENGTH = 4  # Minimum length for a significant word
_MIN_PHRASE_LENGTH = 15  # Minimum length for a significant phrase
_DUPLICATE_THRESHOLD = 0.8  # Threshold for considering excerpt a duplicate (80%)
_SUMMARY_LENGTH_THRESHOLD = 150  # Maximum length for what's considered a summary


def clean_wordpress_content(content: str) -> str:
    if not content:
        return ""

    soup = BeautifulSoup(content, "html.parser")

    for script in soup.find_all("script"):
        script.decompose()
    for style in soup.find_all("style"):
        style.decompose()
    for link in soup.find_all("link"):
        link.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.decompose()

    cleaned = soup.decode_contents()
    return _PATTERN_MULTIPLE_NEWLINES.sub("\n\n", cleaned)


def html_to_markdown(html_str: str) -> str:
    markdown_str = html_to_markdown_(html_str)
    return _PATTERN_MULTIPLE_NEWLINES.sub("\n\n", markdown_str)


def extract_and_clean_excerpt(excerpt_html: str, content_html: str | None = None) -> str | None:
    if not excerpt_html:
        return None

    soup = BeautifulSoup(excerpt_html, "html.parser")
    excerpt_text = soup.get_text(strip=True)

    breadcrumb_match = _PATTERN_BREADCRUMB1.search(excerpt_text)
    if breadcrumb_match:
        excerpt_text = breadcrumb_match.group(2) + excerpt_text[breadcrumb_match.end() :]
    else:
        breadcrumb_match = _PATTERN_BREADCRUMB2.search(excerpt_text)
        if breadcrumb_match:
            excerpt_text = breadcrumb_match.group(2) + excerpt_text[breadcrumb_match.end() :]

    excerpt_text = _PATTERN_TRUNCATION.sub("", excerpt_text).strip()

    if not excerpt_text or len(excerpt_text) < _MIN_EXCERPT_LENGTH:
        return None

    if content_html and excerpt_text:
        return _check_excerpt_duplication(excerpt_text, content_html)

    return excerpt_text


def _check_excerpt_duplication(excerpt_text: str, content_html: str) -> str | None:
    content_soup = BeautifulSoup(content_html, "html.parser")
    content_text = content_soup.get_text(strip=True)

    if content_text.startswith(excerpt_text[: min(50, len(excerpt_text))]):
        return None

    if excerpt_text.startswith(content_text[: min(50, len(content_text))]):
        return None

    meaningful_words = [w for w in excerpt_text.split() if len(w) >= _MIN_WORD_LENGTH]
    if meaningful_words:
        phrase_length = min(5, len(meaningful_words))
        phrase = " ".join(meaningful_words[:phrase_length])

        if len(phrase) >= _MIN_PHRASE_LENGTH and phrase in content_text:
            excerpt_words = {
                w.lower() for w in excerpt_text.split() if len(w) >= _MIN_SIGNIFICANT_WORD_LENGTH
            }
            content_words = {
                w.lower() for w in content_text.split() if len(w) >= _MIN_SIGNIFICANT_WORD_LENGTH
            }

            if (
                len(excerpt_words) > 0
                and len(excerpt_words.intersection(content_words)) / len(excerpt_words)
                > _DUPLICATE_THRESHOLD
            ):
                if (
                    len(excerpt_text) < _SUMMARY_LENGTH_THRESHOLD
                    and excerpt_text not in content_text
                ):
                    return excerpt_text
                return None

    return excerpt_text
