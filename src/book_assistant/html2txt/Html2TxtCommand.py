#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

from pathlib import Path
from ..CommandBase import CommandBase
from ..Commons import log, error
from bs4 import BeautifulSoup, Tag, NavigableString

_HTML2TXT_COMMAND = "html2txt"
# Dictionary for decomposing common ligatures
LIGATURE_MAP = {
    '\ufb00': 'ff',   # ﬀ
    '\ufb01': 'fi',   # ﬁ
    '\ufb02': 'fl',   # ﬂ
    '\ufb03': 'ffi',  # ﬃ
    '\ufb04': 'ffl',  # ﬄ
}

# Each block with one of these tags goes to a new line
_BLOCK_TAGS = {
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'dt', 'dd', 'div', 'section', 'article', 'blockquote', 'pre', 'tr'
}

class Html2TxtCommand(CommandBase):

    def __init__(self):
        super().__init__(_HTML2TXT_COMMAND)

    def _run(self, args, path: Path) -> None:
        input_path = path

        if not input_path.exists():
            error(f"File not found: {input_path}")
            return

        html = input_path.read_text(encoding="utf-8", errors="ignore")
        text = self.__html_to_clean_paragraphs(html)

        output_path = Path(args.output) if args.output else input_path.with_suffix(".txt")

        if not output_path.exists() or output_path.read_text(encoding="utf-8") != text:
            log(f"Creating {output_path}...")
            output_path.write_text(text, encoding="utf-8")
        else:
            log(f"{output_path} is unchanged")

    @staticmethod
    def __html_to_clean_paragraphs(html_content: str) -> str:
        soup = BeautifulSoup(html_content, "lxml-xml")

        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "svg"]):
            tag.decompose()

        lines = []

        for elem in soup.find_all(_BLOCK_TAGS):
            text = Html2TxtCommand.__own_text(elem)
            text = " ".join(text.split())  # normalizza spazi interni

            if text:
                lines.append(text)

        # Remove duplicated empty lines
        cleaned = []

        for line in lines:
            if line or (cleaned and cleaned[-1]):
                cleaned.append(line)

        return Html2TxtCommand.__decompose_ligatures("\n".join(cleaned))

    @staticmethod
    def __own_text(elem) -> str:
        parts = []
        for child in elem.children:
            if isinstance(child, Tag):
                if child.name in _BLOCK_TAGS:
                    continue
                parts.append(Html2TxtCommand.__own_text(child))
            elif type(child) is NavigableString:
                parts.append(str(child))
        return " ".join(parts)

    @staticmethod
    def __decompose_ligatures(text: str) -> str:
        for lig, plain in LIGATURE_MAP.items():
            text = text.replace(lig, plain)
        return text
