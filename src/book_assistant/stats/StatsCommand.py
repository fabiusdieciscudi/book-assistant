#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

"""
StatsCommand.py — Per-file and aggregate statistics for manuscript .txt files.

Metrics computed
----------------
words           Whitespace-delimited tokens (after stripping @lang tags).
sentences       Segments ending with . ! ? or … (ellipsis character).
paragraphs      Non-empty lines, excluding the first line (chapter title).
chars           Total character count (spaces included, newlines excluded).
cartelle        Italian editorial unit: 1 cartella = 1 800 characters
                (spaces included), computed on body text excluding the title.
wps             Words per sentence  (words / sentences, or 0 when sentences=0).
wpp             Words per paragraph (words / paragraphs, or 0 when paragraphs=0).
gulpease        Gulpease Index (Lucisano & Piemontese, 1988) — Italian-native
                readability formula: 89 − (10 × chars/words) + (300 × sentences/words).
                Scale: >80 elementary, 60–80 middle school, 40–60 high school, <40 university.
coleman         Coleman-Liau Index — grade-level estimate based on characters and sentences:
                0.0588 × L − 0.296 × S − 15.8  where L = chars/words×100, S = sentences/words×100.
                Calibrated for English but language-neutral in its inputs; treat as approximate.

Optional (requires --latex-toc)
--------------------------------
from_page       First page of the chapter (from the .toc file).
pages           Page count (next chapter's start − this chapter's start).
progressive     Cumulative page count up to and including this chapter.
spg             Sentences per page (sentences / pages).
wpg             Words per page (words / pages).
"""

import math
import re
from argparse import ArgumentParser
from pathlib import Path
from ..CommandBase import CommandBase
from ..Commons import log

_STATS_COMMAND = "stats"

_CHARS_PER_CARTELLA = 1800

# Sentence-ending punctuation runs.
_SENTENCE_END = re.compile(r'[.!?…]+')

# @lang tags — stripped before word/sentence counting.
_LANG_TAG = re.compile(r'@\w*')

# Matches a chapter or part entry in a LaTeX .toc file.
# Group 1 = entry type (chapter|part), group 2 = raw title field, group 3 = page number.
_TOC_ENTRY = re.compile(r'\\contentsline\s*\{(chapter|part)\}\s*\{(.+?)\}\s*\{(\d+)\}\{(?:chapter|part)\.')

# Box-drawing characters for the output table.
_TOP_LEFT, _TOP_RIGHT = '╭', '╮'
_BOT_LEFT, _BOT_RIGHT = '╰', '╯'
_VERT                 = '│'
_DASH                 = '─'
_HEADER_CROSS         = '┬'
_MID_CROSS            = '┼'
_FOOT_CROSS           = '┴'
_LEFT_T, _RIGHT_T     = '├', '┤'

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

_ANSI_RED    = '\033[31m'
_ANSI_YELLOW = '\033[33m'
_ANSI_GREEN  = '\033[32m'
_ANSI_RESET  = '\033[0m'

def _ansi(text: str, code: str) -> str:
    return f"{code}{text}{_ANSI_RESET}"


class _Palette:
    """Holds per-column colouring thresholds computed from the data rows.

    Statistical thresholds (mean ± 1 stddev) are derived from chapter rows
    only — the TOTAL aggregate row is excluded so it doesn't skew the
    distribution.

    Gulpease uses fixed, semantically meaningful thresholds from the original
    scale definition and needs no per-dataset computation.
    """

    def __init__(self, rows: list[dict]) -> None:
        # Exclude the TOTAL row (title == 'TOTAL') and rows with missing data.
        chapters = [r for r in rows if r.get('title') != 'TOTAL']

        self.wps_mean, self.wps_sd = self._stats(chapters, 'wps')
        self.wpp_mean, self.wpp_sd = self._stats(chapters, 'wpp')

    @staticmethod
    def _stats(rows: list[dict], key: str) -> tuple[float, float]:
        """Return (mean, stddev) for *key* across *rows*, ignoring None."""
        vals = [r[key] for r in rows if r.get(key) is not None]
        if not vals:
            return 0.0, 0.0
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        return mean, math.sqrt(variance)

    def colour_gulpease(self, value: float) -> str:
        """Fixed scale: <40 red, 40–60 yellow, 60–80 green, >80 bright green."""
        if value < 40:
            return _ANSI_RED
        if value < 60:
            return _ANSI_YELLOW
        return _ANSI_GREEN

    def colour_wps(self, value: float) -> str:
        """Statistical: >mean+1sd red (long sentences), <mean-1sd green (short)."""
        if self.wps_sd == 0:
            return ''
        if value > self.wps_mean + self.wps_sd:
            return _ANSI_RED
        if value < self.wps_mean - self.wps_sd:
            return _ANSI_GREEN
        return ''

    def colour_wpp(self, value: float) -> str:
        """Statistical: >mean+1sd red (dense paragraphs), <mean-1sd green (light)."""
        if self.wpp_sd == 0:
            return ''
        if value > self.wpp_mean + self.wpp_sd:
            return _ANSI_RED
        if value < self.wpp_mean - self.wpp_sd:
            return _ANSI_GREEN
        return ''


# Each entry: (header label, width, alignment) where alignment is '<' or '>'.
# ---------------------------------------------------------------------------

_COL_FROM     = ('From',      4, '>')
_COL_PAGES    = ('Pages',     5, '>')
_COL_PROG     = ('Prog.',    10, '>')
_COL_TITLE    = ('Chapter',  40, '<')
_COL_WORDS    = ('Words',     7, '>')
_COL_SENT     = ('Sent.',     6, '>')
_COL_SPG      = ('S/Pg',      5, '>')
_COL_WPG      = ('W/Pg',      5, '>')
_COL_PARA     = ('Para.',     5, '>')
_COL_CHARS    = ('Chars',     7, '>')
_COL_CART     = ('Cartelle',  8, '>')
_COL_WPS      = ('W/S',       5, '>')
_COL_WPP      = ('W/P',       5, '>')
_COL_GULPEASE = ('Gulpease',  9, '>')
_COL_COLEMAN  = ('Coleman',   7, '>')

_COLS_BASE  = [_COL_TITLE, _COL_WORDS, _COL_SENT, _COL_PARA, _COL_CHARS, _COL_CART, _COL_WPS, _COL_WPP, _COL_GULPEASE, _COL_COLEMAN]
_COLS_PAGES = [_COL_FROM, _COL_PAGES, _COL_PROG, _COL_TITLE, _COL_WORDS, _COL_SENT, _COL_SPG, _COL_WPG, _COL_PARA, _COL_CHARS, _COL_CART, _COL_WPS, _COL_WPP, _COL_GULPEASE, _COL_COLEMAN]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean(line: str) -> str:
    """Strip @lang tags and surrounding whitespace from a line."""
    return _LANG_TAG.sub('', line).strip()


def _count_sentences(text: str) -> int:
    """Count sentence boundaries (runs of . ! ? …) in *text*.

    Returns at least 1 for any non-empty text (the whole passage is one
    sentence even when it carries no terminal punctuation).
    """
    if not text.strip():
        return 0
    boundaries = len(_SENTENCE_END.findall(text))
    # If text does not end with terminal punctuation there is one more sentence.
    if not _SENTENCE_END.search(text.rstrip()[-1]):
        boundaries += 1
    return max(boundaries, 1)


def _analyse(file_path: Path) -> dict:
    """Compute statistics for a single .txt manuscript file.

    :param file_path:   path to the file
    :return:            dict with keys title, words, sentences, paragraphs,
                        chars, cartelle, wps, wpp, gulpease, coleman
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if not lines:
        return dict(title=file_path.stem, words=0, sentences=0,
                    paragraphs=0, chars=0, cartelle=0.0,
                    wps=0.0, wpp=0.0, gulpease=None, coleman=None)

    # First line = chapter title (not counted in body metrics).
    title = lines[0].strip() or file_path.stem

    words = sentences = paragraphs = chars = 0

    for raw in lines[1:]:
        cleaned = _clean(raw)
        if not cleaned:
            continue
        paragraphs += 1
        chars      += len(raw.rstrip('\n'))   # keep spaces, drop newline
        words      += len(cleaned.split())
        sentences  += _count_sentences(cleaned)

    cartelle = chars / _CHARS_PER_CARTELLA

    # Gulpease Index (Lucisano & Piemontese, 1988).
    # Formula: 89 − (10 × chars/words) + (300 × sentences/words)
    gulpease = (89 - (10 * chars / words) + (300 * sentences / words)) if words else None

    # Coleman-Liau Index.
    # L = average characters per 100 words; S = average sentences per 100 words.
    # Formula: 0.0588 × L − 0.296 × S − 15.8
    if words:
        L = (chars / words) * 100
        S = (sentences / words) * 100
        coleman = 0.0588 * L - 0.296 * S - 15.8
    else:
        coleman = None

    return dict(
        title=title,
        words=words,
        sentences=sentences,
        paragraphs=paragraphs,
        chars=chars,
        cartelle=cartelle,
        wps=words / sentences  if sentences  else 0.0,
        wpp=words / paragraphs if paragraphs else 0.0,
        gulpease=gulpease,
        coleman=coleman,
    )


def _aggregate(rows: list[dict]) -> dict:
    """Sum counts across *rows* and recompute derived ratios."""
    w  = sum(r['words']      for r in rows)
    s  = sum(r['sentences']  for r in rows)
    p  = sum(r['paragraphs'] for r in rows)
    ch = sum(r['chars']      for r in rows)
    c  = sum(r['cartelle']   for r in rows)
    # Page totals: first from_page of first row, sum of all pages, last progressive.
    fp = rows[0].get('from_page') if rows else None
    pg = sum(r.get('pages') or 0 for r in rows)
    pr = rows[-1].get('progressive') if rows else None

    gulpease = (89 - (10 * ch / w) + (300 * s / w)) if w else None
    if w:
        L = (ch / w) * 100
        S = (s  / w) * 100
        coleman = 0.0588 * L - 0.296 * S - 15.8
    else:
        coleman = None

    result = dict(title='TOTAL', words=w, sentences=s, paragraphs=p,
                  chars=ch, cartelle=c,
                  wps=w/s if s else 0.0, wpp=w/p if p else 0.0,
                  gulpease=gulpease, coleman=coleman)
    if fp is not None:
        result.update(from_page=fp, pages=pg, progressive=pr)
    return result


# ---------------------------------------------------------------------------
# LaTeX .toc parsing
# ---------------------------------------------------------------------------

def _strip_latex(raw: str) -> str:
    """Strip LaTeX formatting commands from a .toc title field.

    Handles: \\numberline, \\hspace, \\foreignlanguage, \\xspace, \\' (escaped
    apostrophe), and leading roman numeral prefixes used in part titles.
    """
    s = raw
    s = re.sub(r'\\numberline\s*\{[^}]*\}', '', s)
    # Replace \hspace (plus any trailing whitespace) with a single space so the
    # roman numeral and the title text remain separated before the numeral strip.
    s = re.sub(r'\\hspace\s*\{[^}]*\}\s*', ' ', s)
    s = re.sub(r'\\foreignlanguage\s*\{[^}]*\}\s*\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\xspace\b', '', s)
    s = s.replace("\\'", "'")                   # LaTeX escaped apostrophe \'
    # Strip leading roman numeral (part-number prefix) only when followed by whitespace.
    s = re.sub(r'^M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})\s+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _parse_toc(toc_path: Path) -> dict[str, int]:
    """Parse a LaTeX .toc file and return a mapping of title → start page.

    Both chapter and part entries are parsed.  LaTeX formatting commands
    (\\numberline, \\hspace, \\foreignlanguage, etc.) are stripped from titles
    so they can be matched against the first line of each .txt file.

    :param toc_path:    path to the .toc file
    :return:            ordered dict mapping cleaned title string → page number
                        (insertion order = toc order)
    """
    result: dict[str, int] = {}
    with open(toc_path, 'r', encoding='utf-8') as f:
        for line in f:
            m = _TOC_ENTRY.search(line)
            if m:
                title = _strip_latex(m.group(2))
                page  = int(m.group(3))
                result[title] = page
    return result

def _normalise(title: str) -> str:
    """Collapse whitespace and casefold a title for fuzzy matching.

    Curly apostrophes (U+2018, U+2019) are unified to a straight apostrophe
    before comparison, since .txt files and LaTeX .toc files may use different
    conventions.
    """
    title = title.replace('\u2019', "'").replace('\u2018', "'")
    return re.sub(r'\s+', ' ', title).strip().casefold()

def _enrich_with_pages(rows: list[dict], toc_path: Path) -> None:
    """Attach from_page, pages, and progressive to each row in-place.

    Matching between the .txt first-line title and the .toc title is done
    after normalisation (casefold + whitespace collapse).  Unmatched rows
    receive None for all three page fields.

    :param rows:        list of stat dicts (modified in-place)
    :param toc_path:    path to the LaTeX .toc file
    """
    toc = _parse_toc(toc_path)
    # Build a normalised lookup: normalised_title → page
    norm_toc: dict[str, int] = {_normalise(t): p for t, p in toc.items()}

    # Attach from_page to each row.
    for row in rows:
        key = _normalise(row['title'])
        # Try exact match first, then substring match (title in .txt may include
        # a chapter-number prefix such as "Capitolo 3 " before the real title).
        page = norm_toc.get(key)
        if page is None:
            for toc_key, toc_page in norm_toc.items():
                if toc_key in key or key in toc_key:
                    page = toc_page
                    break
        row['from_page'] = page  # may be None if no match found

    # Compute page counts using the toc's own ordered page sequence.
    # The toc is already in book order, so the page count for each entry is
    # simply (next_toc_page − this_toc_page), regardless of how the rows happen
    # to be ordered.  Build a map from_page → pages using consecutive toc entries.
    toc_pages = list(toc.values())          # page numbers in toc order
    page_count: dict[int, int | None] = {}
    for i, p in enumerate(toc_pages):
        page_count[p] = toc_pages[i + 1] - p if i + 1 < len(toc_pages) else None

    for row in rows:
        if row['from_page'] is None:
            row['pages'] = None
            row['progressive'] = None
        else:
            row['pages'] = page_count.get(row['from_page'])

    # Progressive is not computed here — it depends on sort order and is
    # calculated in _finish() after the rows have been sorted.


def _hline(cols: list[tuple], left: str, mid: str, right: str) -> str:
    segs = [_DASH * (w + 2) for _, w, _ in cols]
    return left + mid.join(segs) + right

_ANSI_ESCAPE = re.compile(r'\033\[[0-9;]*m')

def _visible_len(s: str) -> int:
    """Return the printable length of *s*, stripping ANSI escape codes."""
    return len(_ANSI_ESCAPE.sub('', s))

def _row(cols: list[tuple], values: list[str]) -> str:
    cells = []
    for (_, w, align), v in zip(cols, values):
        # Pad based on visible length so ANSI codes don't disturb alignment.
        pad = w - _visible_len(v)
        if align == '>':
            cells.append(f' {" " * pad}{v} ')
        else:
            cells.append(f' {v}{" " * pad} ')
    return _VERT + _VERT.join(cells) + _VERT

def _fmt(stats: dict, cols: list[tuple], total_pages: int | None = None,
         palette: '_Palette | None' = None) -> list[str]:
    """Format a stats dict into a list of strings matching *cols*.

    When *palette* is provided, Gulpease, W/S and W/P values are wrapped in
    ANSI colour codes.  The colour escape is applied to the raw value string
    only; padding is added afterwards in _row() so column widths stay stable.
    """
    values = []
    for label, w, _ in cols:
        if label == 'Chapter':
            title = stats['title']
            # Strip numbered chapter prefix: "Capitolo 3 ", "Chapter 3 ", "Chapitre 3 "
            title = re.sub(r'^(?:Capitolo|Chapter|Chapitre)\s+\S+\s*', '', title)
            # Strip un-numbered part prefix: "Parte ", "Part ", "Partie "
            title = re.sub(r'^(?:Parte|Part|Partie)\s+', '', title)
            values.append(title[:w - 1] + '…' if len(title) > w else title)
        elif label == 'Words':
            values.append(str(stats['words']))
        elif label == 'Sent.':
            values.append(str(stats['sentences']))
        elif label == 'S/Pg':
            pages = stats.get('pages')
            s = stats.get('sentences', 0)
            values.append(f"{s / pages:.1f}" if pages else '–')
        elif label == 'W/Pg':
            pages = stats.get('pages')
            w_count = stats.get('words', 0)
            values.append(str(round(w_count / pages)) if pages else '–')
        elif label == 'Para.':
            values.append(str(stats['paragraphs']))
        elif label == 'Chars':
            values.append(str(stats['chars']))
        elif label == 'Cartelle':
            values.append(f"{stats['cartelle']:.2f}")
        elif label == 'W/S':
            v = stats['wps']
            s = f"{v:.1f}"
            if palette:
                code = palette.colour_wps(v)
                if code:
                    s = _ansi(s, code)
            values.append(s)
        elif label == 'W/P':
            v = stats['wpp']
            s = f"{v:.1f}"
            if palette:
                code = palette.colour_wpp(v)
                if code:
                    s = _ansi(s, code)
            values.append(s)
        elif label == 'Gulpease':
            v = stats.get('gulpease')
            if v is None:
                values.append('–')
            else:
                s = f"{v:.1f}"
                if palette:
                    s = _ansi(s, palette.colour_gulpease(v))
                values.append(s)
        elif label == 'Coleman':
            v = stats.get('coleman')
            values.append(f"{v:.1f}" if v is not None else '–')
        elif label == 'From':
            v = stats.get('from_page')
            values.append(str(v) if v is not None else '–')
        elif label == 'Pages':
            v = stats.get('pages')
            values.append(str(v) if v is not None else '–')
        elif label == 'Prog.':
            v = stats.get('progressive')
            if v is None:
                values.append('–')
            elif total_pages:
                values.append(f"{v} ({100 * v // total_pages}%)")
            else:
                values.append(str(v))
        else:
            values.append('')
    return values


def _print_table(rows: list[dict], with_pages: bool = False) -> None:
    cols = _COLS_PAGES if with_pages else _COLS_BASE
    headers = [label for label, _, _ in cols]

    total_pages = _aggregate(rows).get('pages') if with_pages else None
    palette = _Palette(rows)

    print(_hline(cols, _TOP_LEFT, _HEADER_CROSS, _TOP_RIGHT))
    print(_row(cols, headers))
    print(_hline(cols, _LEFT_T, _MID_CROSS, _RIGHT_T))

    for r in rows:
        print(_row(cols, _fmt(r, cols, total_pages, palette)))

    if len(rows) > 1:
        print(_hline(cols, _LEFT_T, _FOOT_CROSS, _RIGHT_T))
        # TOTAL row gets palette=None: no colouring on the aggregate.
        print(_row(cols, _fmt(_aggregate(rows), cols, total_pages, palette=None)))

    print(_hline(cols, _BOT_LEFT, _DASH, _BOT_RIGHT))

def _natural_key(row: dict) -> list:
    """Split the chapter title into alternating text/integer chunks.

    'Capitolo 2 Mosaici' → ['capitolo ', 2, ' mosaici']

    This makes '2' sort before '10', as integers compare numerically rather
    than lexicographically.
    """
    return [int(chunk) if chunk.isdigit() else chunk.lower()
            for chunk in re.split(r'(\d+)', row['title'])]

class StatsCommand(CommandBase):
    """Collect and display manuscript statistics."""

    def __init__(self):
        super().__init__()
        self._args = None
        self._rows: list[dict] = []

    def name(self) -> str:
        return _STATS_COMMAND

    def process_args(self, parser: ArgumentParser) -> None:
        parser.add_argument('--latex-toc', metavar='FILE', default=None, help='LaTeX .toc file; adds page columns (From, Pages, Prog.) to the table.')

    def _prepare(self) -> None:
        super()._prepare()
        self._rows = []
        self._args = None

    def _run(self, args, path: Path) -> None:
        self._args = args   # captured here; same object for every file in a run
        log(f"Analysing: {path.name}...", new_line=False)
        self._rows.append(_analyse(path))

    def _finish(self) -> None:
        if not self._rows:
            return
        with_pages = bool(getattr(self._args, 'latex_toc', None))
        if with_pages:
            # Enrich first so from_page is available, then sort by toc page order.
            # Rows with no toc match (from_page=None) go to the end.
            _enrich_with_pages(self._rows, Path(self._args.latex_toc))
            sorted_rows = sorted(self._rows, key=lambda r: (r['from_page'] is None, r.get('from_page') or 0))
        else:
            sorted_rows = sorted(self._rows, key=_natural_key)
        # Compute progressive in sorted order.
        cumulative = 0
        for row in sorted_rows:
            if row.get('pages') is not None:
                cumulative += row['pages']
                row['progressive'] = cumulative
            else:
                row['progressive'] = None
        _print_table(sorted_rows, with_pages=with_pages)
        super()._finish()