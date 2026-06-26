#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

"""
HtmlCleaner.py — Strips TeX4ht boilerplate and converts HTML chapters to
WordPress Gutenberg block markup before publishing.

Transformation rules applied by clean_html():

  Removed entirely:
    - <head>
    - HTML comments (TeX4ht line-number markers such as <!-- l. 410 -->)
    - <div class="crosslinks"> (prev/next chapter navigation)
    - <h2> (chapter title, already set in WordPress)
    - <br> and <br class="newline"> (spacing handled by WP CSS)
    - Empty <a> tags (TeX4ht anchor targets such as <a id="x2-1001r1">)
    - <span class="footnote-mark"> and <sup class="textsuperscript">
      (footnote call references; WP manages them via wp:footnotes)
    - All 'id' attributes on every remaining tag
    - <p> tags left empty after the above stripping

  Converted to <i>:
    - <span class="ec-lmbx-*"> (TeX bold extended)
    - <span class="ec-lmri-*"> (TeX italic)
    - <span class="small-caps">

  Unwrapped (text preserved, tag removed):
    - All remaining <span> tags (lettrine, titlemark, etc.)

  Wrapped in Gutenberg block comments:
    - <p>, <p class="indent">, <p class="noindent"> → wp:paragraph
    - <blockquote>                                  → wp:quote
    - <div class="footnotes">                       → wp:footnotes
"""

from bs4 import BeautifulSoup, Comment, Tag

# Span classes from TeX4ht that map to italic in WordPress.
_ITALIC_SPAN_PREFIXES = ("ec-lmbx", "ec-lmri", "small-caps")

# Gutenberg block wrappers: tag name → (opening comment, closing comment).
# For self-closing blocks the closing comment is None.
_GUTENBERG_BLOCKS: dict[str, tuple[str, str | None]] = {
    "p":          ("<!-- wp:paragraph -->",          "<!-- /wp:paragraph -->"),
    "blockquote": ("<!-- wp:quote -->",               "<!-- /wp:quote -->"),
    "footnotes":  ("<!-- wp:footnotes /-->",          None),
}


def _wrap_gutenberg(tag: Tag) -> str:
    """Return the Gutenberg block markup for a single top-level tag.

    :param tag:     a BeautifulSoup Tag already cleaned of boilerplate
    :return:        Gutenberg-wrapped HTML string, or empty string if the
                    tag should be suppressed
    """
    name = tag.name

    # <div class="footnotes"> uses a self-closing Gutenberg block.
    classes = tag.get("class", [])
    if name == "div" and "footnotes" in classes:
        open_c, close_c = _GUTENBERG_BLOCKS["footnotes"]
        return open_c

    block = _GUTENBERG_BLOCKS.get(name)
    if not block:
        return ""

    open_c, close_c = block
    inner = str(tag)
    return f"{open_c}\n{inner}\n{close_c}"


def clean_html(html: str) -> str:
    """Strip TeX4ht boilerplate and emit Gutenberg block markup.

    :param html:    raw HTML produced by TeX4ht
    :return:        Gutenberg-formatted HTML fragment for a WordPress page body
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1. Remove <head> entirely.
    if soup.head:
        soup.head.decompose()

    # 2. Remove all HTML comments.
    for node in soup.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()

    # 3. Remove <div class="crosslinks">.
    for tag in soup.find_all(class_="crosslinks"):
        tag.decompose()

    # 4. Remove <h2> (chapter title already set in WordPress).
    for tag in soup.find_all("h2"):
        tag.decompose()

    # 5. Replace <br> tags with a space (avoid merging surrounding words).
    for tag in soup.find_all("br"):
        tag.replace_with(" ")

    # 6. Remove empty <a> tags (TeX4ht anchor targets).
    for tag in soup.find_all("a"):
        if not tag.get_text(strip=True) and not tag.find():
            tag.decompose()

    # 7. Remove footnote call markers: <span class="footnote-mark"> and
    #    <sup class="textsuperscript">.
    for tag in soup.find_all(class_="footnote-mark"):
        tag.decompose()
    for tag in soup.find_all(class_="textsuperscript"):
        tag.decompose()

    # 8. Convert TeX typographic spans to <i>.
    for tag in soup.find_all("span"):
        classes = tag.get("class", [])
        if any(
                any(c.startswith(prefix) for prefix in _ITALIC_SPAN_PREFIXES)
                for c in classes
        ):
            tag.name = "i"
            del tag["class"]

    # 9. Unwrap all remaining <span> tags (lettrine, titlemark, etc.).
    for tag in soup.find_all("span"):
        tag.unwrap()

    # 10. Strip all 'id' attributes from every remaining tag.
    for tag in soup.find_all(True):
        if tag.has_attr("id"):
            del tag["id"]

    # 11. Remove <p> tags left empty after the above stripping.
    for tag in soup.find_all("p"):
        if not tag.get_text(strip=True) and not tag.find():
            tag.decompose()

    # 12. Wrap top-level block elements in Gutenberg block comments.
    body = soup.body or soup
    blocks = []
    for tag in body.find_all(True, recursive=False):
        wrapped = _wrap_gutenberg(tag)
        if wrapped:
            blocks.append(wrapped)

    return "\n\n".join(blocks)
