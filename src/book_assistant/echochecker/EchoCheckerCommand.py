#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT
#
from argparse import ArgumentParser
from collections import deque
from pathlib import Path
import re
from book_assistant.CommandBase import CommandBase
import zlib

from book_assistant.Commons import log

_ECHO_CHECKER_COMMAND = "echo"

_DEFAULT_WINDOW = 150

_IGNORED = set("""
essere avere della delle dello degli nella nelle nello nell negli sulla sulle
sullo sugli sull dalla dalle dallo dall dagli quella quelle quello quelli questa
queste questo questi come dove quando mentre perche perché anche ancora
aveva avevano avevo erano fosse fossero sarebbe sarebbero stato stata
stati state veniva vennero venne verrebbe prima dopo senza sotto sopra
verso contro tutto tutta tutti tutte molto molta molti molte poco poca
pochi poche sempre spesso ormai forse quasi appena finche finché quindi
pero però infatti dunque comunque tuttavia eppure invece proprio propria
allo alle
propri proprie altro altra altri altre ogni qualche stesso stessa stessi
stesse loro nostro nostra nostri nostre vostro vostra vostri vostre
poteva potevano potrebbe possono dovere doveva dovevano dovrebbe
qualcosa qualcuno nessuno niente nulla
""".split())

class EchoCheckerCommand(CommandBase):

    def __init__(self):
        super().__init__(_ECHO_CHECKER_COMMAND)

    def process_args(self, parser: ArgumentParser) -> None:
        parser.add_argument("--window", type=int, default=_DEFAULT_WINDOW,
                            help=f"Number of words to look back for repetitions (default: {_DEFAULT_WINDOW}).")
        parser.add_argument("--no-colour", action="store_true", default=False, help="Suppresses colour.")
        parser.add_argument("--print-all-lines", action="store_true", default=False, help="Print also lines with no occurrences.")

    def _run(self, args, path: Path) -> None:
        file_name = Path(path).name
        sentences, marks = self._find_nearby_echoes(path, args.window)
        occurrences = 0

        for idx, sentence in enumerate(sentences):
            xlist = marks.get(idx)
            if xlist:
                s, o = _marked(sentence, xlist, not args.no_colour)
                occurrences += o
                print(f"{file_name}[{idx: >3}] {s.replace('\n', ' ')}")
            elif args.print_all_lines:
                print(f"{file_name}[{idx: >3}] {sentence.replace('\n', ' ')}")

        if occurrences:
            log(f"{file_name}: Occurrences: {occurrences}")
        else:
            log("No nearby word repetitions found.")

    def _find_nearby_echoes(self, file_path: Path, window_size=_DEFAULT_WINDOW):
        """Ritorna (sentences, marks): l'elenco completo delle frasi e una
        mappa indice-frase -> [(parola, offset), ...] delle occorrenze."""
        word_queue = deque(maxlen=window_size)
        marks = {}
        seen = set()

        sentence_pattern = re.compile(r'[^.!?…]+(?:[.!?…]+|\Z)')
        word_pattern = re.compile(r"\b\w+(?:-\w+)?\b")

        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # Frasi conservate nella forma originale, apostrofi compresi.
        sentences = [s.strip() for s in sentence_pattern.findall(text) if s.strip()]

        for sent_idx, sentence in enumerate(sentences):
            # Copia normalizzata solo per la tokenizzazione (l'aereo -> l aereo);
            # la sostituzione conserva le lunghezze, quindi gli offset valgono
            # anche sulla frase originale.
            split_sentence = sentence.replace("'", " ").replace("\u2019", " ")

            for match in word_pattern.finditer(split_sentence):
                word = match.group(0).lower()

                if len(word) < 4 or word in _IGNORED:
                    continue

                current = (word, sent_idx, match.start())

                for prev in word_queue:
                    if _word_match(prev[0], word):
                        for w, idx, pos in (current, prev):
                            if (w, idx, pos) not in seen:
                                seen.add((w, idx, pos))
                                marks.setdefault(idx, []).append((w, pos))

                word_queue.append(current)

        return sentences, marks

# --- Colori -----------------------------------------------------------------
# Rosso: riservato alle ripetizioni dentro la stessa frase.
# Echi tra frasi diverse: a ogni parola è associato stabilmente un colore
# della palette (via CRC32, deterministico tra esecuzioni e tra capitoli:
# «aereo» avrà sempre lo stesso colore, ovunque). Con 12 colori due parole
# diverse possono condividere la tinta: inevitabile, ma la coppia da
# accoppiare visivamente è quasi sempre vicina, quindi in pratica funziona.

_ANSI_RESET = "\033[0m"
_ANSI_RED = "\033[91m"

# Palette senza rossi e senza toni invisibili su sfondi comuni.
_PALETTE = [
    "\033[92m",        # verde brillante
    "\033[93m",        # giallo brillante
    "\033[94m",        # blu brillante
    "\033[95m",        # magenta brillante
    "\033[96m",        # ciano brillante
    "\033[32m",        # verde
    "\033[33m",        # giallo
    "\033[36m",        # ciano
    "\033[38;5;208m",  # arancione
    "\033[38;5;135m",  # viola
    "\033[38;5;43m",   # verde acqua
    "\033[38;5;111m",  # azzurro polvere
]


def _word_match(w1: str, w2: str) -> bool:
    if w1 == w2:
        return True
    if len(w1) != len(w2) or len(w1) < 1:
        return False
    vowels = set('aeiouàèéìíòóùúAEIOUÀÈÉÌÍÒÓÙÚ')
    return w1[-1] in vowels and w2[-1] in vowels and w1[:-1] == w2[:-1]

def _word_color(word: str) -> str:
    return _PALETTE[zlib.crc32(word[:-1].lower().encode("utf-8")) % len(_PALETTE)]


def _paint(code: str, s: str, colour: bool) -> str:
    return f"{code}{s}{_ANSI_RESET}" if colour else f"{{{s}}}"


def _marked(s: str, xlist: list, colour: bool) -> tuple[str, int]:
    occurrences = 0
    # Inserimento da destra a sinistra: gli offset precedenti restano validi.
    for w, p in sorted(xlist, key=lambda t: t[1], reverse=True):
        count = sum(1 for w1, _ in xlist if w1 == w)
        code = _ANSI_RED if count > 1 else _word_color(w)
        s = f"{s[:p]}{_paint(code, s[p:p + len(w)], colour)}{s[p + len(w):]}"
        occurrences += 1
    return s, occurrences