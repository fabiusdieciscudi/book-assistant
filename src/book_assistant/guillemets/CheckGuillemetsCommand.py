#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

from pathlib import Path
from ..CommandBase import CommandBase
from ..Commons import log, red2

_CHECK_GUILLEMETS_COMMAND = "check-guillemets"
_PUNCTUATION = '.,!?;:-—…'


class CheckGuillemetsCommand(CommandBase):

    def name(self) -> str:
        return _CHECK_GUILLEMETS_COMMAND

    def _run(self, args, path: Path) -> None:
        results = []

        with open(path, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, start=1):
                line = line.rstrip('\n')
                i = 0
                while i < len(line):
                    if line[i] == '»':
                        has_punct_before = i > 0 and line[i-1] in _PUNCTUATION
                        has_punct_after = False

                        j = i + 1
                        while j < len(line) and line[j].isspace():
                            j += 1
                        if j < len(line) and line[j] in _PUNCTUATION:
                            has_punct_after = True

                        k = j
                        while k < len(line) and not line[k].isalnum():
                            k += 1

                        next_word = ""
                        if k < len(line) and line[k].isalpha():
                            start_word = k
                            while k < len(line) and line[k].isalnum():
                                k += 1
                            next_word = line[start_word:k]

                        next_open_found = False
                        m = k
                        while m < len(line):
                            if line[m] == '«':
                                next_open_found = True
                                break
                            m += 1

                        always_comma = False

                        if has_punct_before and has_punct_after:
                            log(f"{path.name}: {red2(line, i - 1, j + 1)}")

                        if not has_punct_before and next_word:
                            if always_comma and not has_punct_after:
                                log(f"{path.name}: {red2(line, start_word - 1, k + 1)}")

                            elif not always_comma and has_punct_after:
                                # if next_word in verbs:
                                log(f"{path.name}: {red2(line, start_word - 1, k + 1)}")

                    i += 1

        return results
