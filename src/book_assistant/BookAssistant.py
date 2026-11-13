#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import argparse
import importlib
import sys
from pathlib import Path
import book_assistant
from book_assistant import CommandBase
from book_assistant.Commons import set_debug, set_debug_to_file, set_log_file, error, exception
from book_assistant.Version import __version__


def _load_commands() -> None:
    """Import every direct subpackage of book_assistant.

    Each subpackage __init__.py is responsible for appending its own
    command instance to CommandBase.COMMANDS.
    """
    pkg_path = Path(book_assistant.__file__).parent
    for sub in sorted(pkg_path.iterdir()):
        if sub.is_dir() and (sub / "__init__.py").exists():
            importlib.import_module(f"book_assistant.{sub.name}")


if __name__ == '__main__':
    _load_commands()
    command_map: dict[str, CommandBase] = {cmd.name(): cmd for cmd in book_assistant.COMMANDS}
    parser = argparse.ArgumentParser(description="BookAssistant")
    parser.add_argument("command", choices=list(command_map), help="Command to run.")
    parser.add_argument("path", nargs="?", default=None, help="File or folder to process.")
    parser.add_argument("--version", action="version", version=f"BookAssistant {__version__}")
    parser.add_argument("--debug", action="store_true", default=False, help="Verbose logging (terminal and log file).")
    parser.add_argument("--debug-to-file", action="store_true", default=False, help="Verbose logging only to the log file.")
    parser.add_argument("--log-file", default=None, help="Also write the log to this file (overwritten).")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Validate without time-expensive operations.")

    for command in command_map.values():
        command.process_args(parser)

    args = parser.parse_args()
    if args.path is None and not (args.command == "tts" and getattr(args, "list_unused", False)):
        parser.error("the following arguments are required: path")
    if args.debug_to_file and not args.log_file:
        parser.error("--debug-to-file requires --log-file")
    set_debug(args.debug)
    set_debug_to_file(args.debug_to_file)
    set_log_file(args.log_file)
    try:
        command_map[args.command].run(args)
    except Exception as e:
        exception(e)
        sys.exit(1)
