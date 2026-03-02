#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT
#
from argparse import ArgumentParser
from collections import deque
from pathlib import Path
import re
from typing import Any
from book_assistant.CommandBase import CommandBase
from book_assistant.Commons import red, log, yellow

_ECHO_CHECKER_COMMAND = "echo"

_IGNORED = ["ancora", "degli", "della", "delle", "nella", "alla", "dalla", "sono", "sulla", "Roberto", "Claire", "Goodwill", "Buongiorno", "sono", "siamo", "suoi", "Jacques", "Géraldine"]


class EchoCheckerCommand(CommandBase):

    def __init__(self):
        super().__init__(_ECHO_CHECKER_COMMAND)

    def process_args(self, parser: ArgumentParser) -> None:
        parser.add_argument("--window", type=int, default=100, help="Number of words to look back for repetitions (default: 100).")

    def _run(self, args, path: Path) -> None:
        file_name = Path(path).name
        repeats = self._find_nearby_echoes(path, args.window)

        if not repeats:
            print("No nearby word repetitions found.")
            return

        prev_sentence = None
        xlist = []

        occurrences = 0

        for word, index, sentence, position in sorted(repeats, key=lambda t: t[1]):  # sorted by index
            if prev_sentence != sentence and prev_sentence or index == len(repeats) + 1:
                s, o = self._marked(prev_sentence, xlist)
                occurrences = occurrences + o

                if o:
                    print(f"{file_name}[{index: >3}] {s}")

                xlist.clear()

            xlist.append((word, position))  # FIXME: the last one is lost?
            prev_sentence = sentence

        print(f"Occurrences: {occurrences}")

    def _find_nearby_echoes(self, file_path: Path, window_size=100):
        word_queue = deque(maxlen=window_size)
        occurrences = []

        sentence_pattern = re.compile(r'[^.!?]+[.!?]+')
        word_pattern = re.compile(r"\b\w+(?:[''-]\w+)?\b")

        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        sentences = sentence_pattern.findall(text)

        for sent_idx, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue

            for match in word_pattern.finditer(sentence):
                word = match.group(0)
                if len(word) < 4:
                    continue

                current_tuple = (word, sent_idx, sentence, match.start())

                for prev_word, prev_idx, prev_sentence, prev_pos in word_queue:
                    if prev_word == word:
                        prev_tuple = (prev_word, prev_idx, prev_sentence, prev_pos)

                        if current_tuple not in occurrences:
                            occurrences.append(current_tuple)

                        if prev_tuple not in occurrences:
                            occurrences.append(prev_tuple)

                word_queue.append(current_tuple)

        return occurrences

    @staticmethod
    def _marked(s: str, xlist: list[Any]) -> tuple[str, int]:
        occurrences = 0
        for w, p in reversed(sorted(xlist, key=lambda t: t[1])):
            count = 0
            for w1, p1 in xlist:
                if w1 == w:
                    count = count + 1

            if count > 1 or w not in _IGNORED:
                color = yellow if count == 1 else red
                s = f"{s[:p]}{color(s[p:p + len(w)])}{s[p + len(w):]}"
                occurrences = occurrences + 1

        return s, occurrences