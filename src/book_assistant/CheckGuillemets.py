#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

from pathlib import Path
from Commons import log, red

CHECK_GUILLEMETS_COMMAND = "check-guillemets"

_PUNCTUATION = '.,!?;:-—…'

def _line_with_red_segment(line, start_pos, end_pos) -> str:
    return f"{line[:start_pos]}{red(line[start_pos:end_pos])}{line[end_pos:]}"


def _check_guillemets(file_path: Path):
    results = []

    with open(file_path, 'r', encoding='utf-8') as f:
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
                        log(f"{Path(file_path).name}: {_line_with_red_segment(line, i - 1, j + 1)}")

                    if not has_punct_before and next_word:
                        if always_comma and not has_punct_after:
                            log(f"{Path(file_path).name}: {_line_with_red_segment(line, start_word - 1, k + 1)}")

                        elif not always_comma and has_punct_after:
                            # if next_word in verbs:
                            log(f"{Path(file_path).name}: {_line_with_red_segment(line, start_word - 1, k + 1)}")

                i += 1

    return results


def check_guillemets_args(args):
    pass


def check_guillemets_run(args):
    return _check_guillemets