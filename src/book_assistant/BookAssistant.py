#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import argparse
from pathlib import Path
from Commons import set_debug, error
from SpellChecker import SPELLCHECK_COMMAND, spell_check_args, spell_check_run


def process(file_path: str, callback=None):
    path = Path(file_path).resolve()
    if not path.exists():
        error(f"Doesn't exist: {file_path}")
        return
    if path.is_file():
        callback(path)
    elif path.is_dir():
        txt_files = sorted(path.rglob("*.txt"))
        for txt_path in txt_files:
            callback(txt_path)


if __name__ == '__main__':
    commands = [
        SPELLCHECK_COMMAND,
    ]
    parser = argparse.ArgumentParser(description="BookAssistant")
    parser.add_argument("command", choices=commands, help=f"Command: {commands})")
    parser.add_argument("path", help="File or folder to process (mandatory).")
    parser.add_argument("--debug", action="store_true", default=False, help="Verbose logging.")

    spell_check_args(parser)

    args = parser.parse_args()
    set_debug(args.debug)

    if args.command == SPELLCHECK_COMMAND:
        process(args.path, spell_check_run(args))
