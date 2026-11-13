#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

"""
Commons.py — Shared utilities for BookAssistant.
"""

import sys
import time
import traceback
from datetime import datetime
import re
import numpy as np
from typing import Any, Tuple, Callable, Iterable

# When True, debug() calls emit output; set via set_debug().
debugging = False

# When True, debug() calls emit output only to the log file; set via set_debug_to_file().
debugging_to_file = False

# When set, log() also writes to this file; set via set_log_file().
log_file = None
log_file_path = None

_ANSI_PATTERN = re.compile(r'\033\[[0-9;]*[A-Za-z]')

# ANSI colour codes
RED     = "\033[31m"
YELLOW  = "\033[93m"
GREEN   = "\033[32m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
RESET   = "\033[0m"   # Resets all attributes back to the terminal default.

def coloured(line: str, start_pos: int, end_pos: int, colour: str) -> str:
    """Wrap a substring of *line* in an ANSI colour code.

    Characters outside [start_pos, end_pos) are left unchanged.

    :param line:        the full string to colourise
    :param start_pos:   inclusive start index of the coloured range
    :param end_pos:     exclusive end index of the coloured range
    :param colour:      an ANSI escape sequence (e.g. RED, YELLOW …)
    :return:            the string with the chosen range wrapped in colour codes
    """
    return f"{line[:start_pos]}{colour}{line[start_pos:end_pos]}{RESET}{line[end_pos:]}"

def red2(line: str, start_pos: int, end_pos: int) -> str:
    """Colour a substring of *line* in red."""
    return coloured(line, start_pos, end_pos, RED)

def red(line: str) -> str:
    """Colour the entire *line* in red."""
    return red2(line, 0, len(line))

def yellow2(line: str, start_pos: int, end_pos: int) -> str:
    """Colour a substring of *line* in yellow."""
    return coloured(line, start_pos, end_pos, YELLOW)

def yellow(line: str) -> str:
    """Colour the entire *line* in yellow."""
    return yellow2(line, 0, len(line))

def green2(line: str, start_pos: int, end_pos: int) -> str:
    """Colour a substring of *line* in green."""
    return coloured(line, start_pos, end_pos, GREEN)

def green(line: str) -> str:
    """Colour the entire *line* in green."""
    return green2(line, 0, len(line))

def magenta2(line: str, start_pos: int, end_pos: int) -> str:
    """Colour a substring of *line* in magenta."""
    return coloured(line, start_pos, end_pos, MAGENTA)

def magenta(line: str) -> str:
    """Colour the entire *line* in magenta."""
    return magenta2(line, 0, len(line))

def cyan2(line: str, start_pos: int, end_pos: int) -> str:
    """Colour a substring of *line* in cyan."""
    return coloured(line, start_pos, end_pos, CYAN)

def cyan(line: str) -> str:
    """Colour the entire *line* in cyan."""
    return cyan2(line, 0, len(line))

def count_words(text: str) -> int:
    """Return the number of whitespace-delimited tokens in *text*.

    Returns 0 for empty or None-like input (the falsy guard handles both
    an empty string and a None value passed by mistake).

    :param text:    the string to count words in
    :return:        word count
    """
    return len(text.split()) if text else 0

def log(message: str, new_line: bool = True) -> None:
    """Write *message* to stderr.

    When *new_line* is False the line ends with a carriage return and an
    ANSI erase-to-end-of-line sequence (\033[K) instead of a newline,
    producing an in-place progress indicator that overwrites itself on the
    next call.

    :param message:     text to print
    :param new_line:    if True (default) append \\n; if False overwrite the
                        current terminal line (used for progress display)
    """
    _log(message, "INFO", message, new_line)

def _log(message: str, level: str, file_message: str, new_line: bool = True) -> None:
    """Write *message* to stderr and *file_message* to the log file, if any, with *level*."""
    print(message + ("" if new_line else "\033[K"), file=sys.stderr, end="\n" if new_line else "\r")
    if new_line:                                    # progress lines, which overwrite themselves, are not repeated
        _log_to_file(level, file_message)

def _log_to_file(level: str, message: str) -> None:
    """Write *message* to the log file, if any: local timestamp to the millisecond, level, text without colours."""
    if log_file is not None:
        timestamp = datetime.now().astimezone().isoformat(sep=" ", timespec="milliseconds")
        print(f"{timestamp} {f'[{level}]':<9} {_ANSI_PATTERN.sub('', message)}", file=log_file, flush=True)

def set_log_file(path: str | None) -> None:
    """Repeat the log, without colours, in the file at *path*, which is overwritten (None to stop).

    :param path:    the file
    """
    global log_file, log_file_path
    if log_file is not None:
        log_file.close()
    log_file = None if path is None else open(path, "w", encoding="utf-8")
    log_file_path = path

def error(message: str) -> None:
    """Log *message* in red to stderr.

    Intended for non-fatal user-facing errors such as missing files or
    unsupported language tags.

    On the terminal, unless debugging, it's followed by a hint about where to find more details.

    :param message:     error description
    """
    _log(red(f"ERROR: {message}"), "ERROR", message)
    if not debugging:
        hint = (f"more details in the log file: {log_file_path}" if debugging_to_file and log_file is not None
                else "run with --debug for more details")
        print(red(f"       ({hint})"), file=sys.stderr)

def exception(e: BaseException) -> None:
    """Log a caught exception: its message as an error, the stack trace only when debugging (on the terminal and
    in the log file with --debug, only in the log file with --debug-to-file).

    :param e:           the exception
    """
    if debugging or debugging_to_file:
        trace = "".join(traceback.format_exception(e)).rstrip()
        if debugging:
            _log(magenta(trace), "DEBUG", trace)
        else:
            _log_to_file("DEBUG", trace)
    error(str(e) or type(e).__name__)

def warning(message: str) -> None:
    """Log *message* in yellow to stderr.

    Intended for warnings.

    :param message:     warning description
    """
    _log(yellow(f"WARNING: {message}"), "WARNING", message)

def debug(message: str) -> None:
    """Log *message* in magenta to stderr, but only when debugging is enabled.

    No-op unless set_debug(True) has been called. Use for internal
    diagnostics that would be too noisy in normal operation (e.g.
    LanguageTool initialisation times, per-file tracing).

    :param message:     diagnostic text
    """
    if debugging:
        _log(magenta(message), "DEBUG", message)
    elif debugging_to_file:
        _log_to_file("DEBUG", message)

def set_debug(_debug: bool) -> None:
    """Enable or disable verbose debug logging globally.

    Flips the module-level *debugging* flag consulted by debug().
    Called once at startup from the CLI argument parser.

    :param _debug:  True to enable debug output, False to suppress it
    """
    global debugging
    debugging = _debug

def set_debug_to_file(_debug: bool) -> None:
    """Enable or disable debug logging only to the log file (see set_log_file()).

    :param _debug:  True to write debug output to the log file, False to suppress it
    """
    global debugging_to_file
    debugging_to_file = _debug

def is_debug() -> bool:
    return debugging

def measure_time(func: Callable[[], Any]) -> Tuple[Any, float]:
    """Call *func*, measure its wall-clock duration, and return both.

    :param func:    a zero-argument callable to time
    :return:        a (result, elapsed_seconds) tuple where *result* is
                    whatever *func* returned and *elapsed_seconds* is a float    start = time.perf_counter_ns()
    """
    start = time.perf_counter_ns()
    result = func()
    end = time.perf_counter_ns()
    return result, (end - start) / 1_000_000_000

def read_dict(file_path: str | Iterable[str]) -> dict[str, str]:
    result = {}

    for path in [file_path] if isinstance(file_path, str) else sorted(file_path):
        with open(path, encoding='utf-8') as f:
            for m in re.finditer(r'^\s*([^#:]+?)\s*:\s*([^#]*?)(?:\s*#.*)?$', f.read(), re.MULTILINE):
                key = m.group(1).strip()
                if key:
                    result[key] = m.group(2).strip()
    return result

def single_channel(audio: np.ndarray) -> np.ndarray:
    audio = audio.astype(np.float32)
    if audio.ndim == 1:
        return audio
    if audio.ndim == 2:
        if audio.shape[0] == 1:
            return audio[0, :]
        elif audio.shape[1] == 1:
            return audio[:, 0]

    raise ValueError(f"Malformed audio: expected mono or simple stereo - ndim: {audio.ndim}, shape: {audio.shape}")
