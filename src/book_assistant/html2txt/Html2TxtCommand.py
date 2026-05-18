#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

from pathlib import Path
from ..CommandBase import CommandBase
from ..Commons import log, error, warning
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

    def run(self, args) -> None:
        resolved = Path(args.path).resolve()
        if not resolved.exists():
            error(f"Doesn't exist: {args.path}")
            return

        output_dir = Path(args.output).resolve() if args.output else None
        if resolved.is_dir() and output_dir is not None and output_dir.exists() and not output_dir.is_dir():
            error(f"--output must be a folder when <path> is a folder: {args.output}")
            return

        try:
            self._prepare()
            if resolved.is_file():
                self._run(args, resolved)
            elif resolved.is_dir():
                html_files = sorted(resolved.rglob("*.html"))
                if not html_files:
                    warning(f"No .html files found in: {resolved}")
                for html_path in html_files:
                    target_dir = output_dir / html_path.parent.relative_to(resolved) if output_dir else html_path.parent
                    self._convert(html_path, target_dir / html_path.with_suffix(".txt").name)
        finally:
            self._finish()

    def _run(self, args, path: Path) -> None:
        self._convert(path, self._single_output(path, args.output))

    @staticmethod
    def _single_output(input_path: Path, output: str | None) -> Path:
        """Return the output path for a single input file: --output if given
        (or a file inside it, when it is an existing folder), otherwise the
        input path with a .txt extension."""
        if not output:
            return input_path.with_suffix(".txt")
        out = Path(output).resolve()
        return out / input_path.with_suffix(".txt").name if out.is_dir() else out

    def _convert(self, input_path: Path, output_path: Path) -> None:
        input_path = input_path.resolve()
        output_path = output_path.resolve()

        if output_path == input_path:
            error(f"{input_path.name}: the output would overwrite the input file - skipped (is it really an .html file?).")
            return

        html = input_path.read_text(encoding="utf-8", errors="ignore")
        text = self.__html_to_clean_paragraphs(html)

        if not output_path.exists() or output_path.read_text(encoding="utf-8") != text:
            log(f"Creating {output_path}...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
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
