#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import sys
import re

debug   = False

RED     = "\033[31m"
YELLOW  = "\033[93m"
GREEN   = "\033[32m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
RESET   = "\033[0m"

def coloured(line, start_pos, end_pos, colour) -> str:
    return f"{line[:start_pos]}{colour}{line[start_pos:end_pos]}{RESET}{line[end_pos:]}"

def red2(line, start_pos, end_pos ) -> str:
    return coloured(line, start_pos, end_pos, RED)

def red(line) -> str:
    return red2(line, 0, len(line))

def yellow2(line, start_pos, end_pos ) -> str:
    return coloured(line, start_pos, end_pos, YELLOW)

def yellow(line) -> str:
    return yellow2(line, 0, len(line))

def green2(line, start_pos, end_pos ) -> str:
    return coloured(line, start_pos, end_pos, GREEN)

def green(line) -> str:
    return green2(line, 0, len(line))

def magenta2(line, start_pos, end_pos ) -> str:
    return coloured(line, start_pos, end_pos, MAGENTA)

def magenta(line) -> str:
    return magenta2(line, 0, len(line))

def cyan2(line, start_pos, end_pos ) -> str:
    return coloured(line, start_pos, end_pos, CYAN)

def cyan(line) -> str:
    return cyan2(line, 0, len(line))

def count_words(text: str) -> int:
    return len(text.split()) if text else 0


def log(message: str, new_line = True):
    print(message + ("" if new_line else "\033[K"), file=sys.stderr, end="\n" if new_line else "\r")


def error(message: str):
    log(red(message))


def debug(message: str):
    if debug:
        log(magenta(message))


def set_debug(_debug: bool):
    global debug
    debug = _debug


def read_dict(filepath: str) -> dict[str, str]:
    with open(filepath, encoding='utf-8') as f:
        return dict((m.group(1).strip(), m.group(2).strip())
            for m in re.finditer(r'^\s*([^#:]+?)\s*:\s*([^#]*?)(?:\s*#.*)?$', f.read(), re.MULTILINE) if m.group(1).strip())
