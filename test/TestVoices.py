#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

"""
test-voices.py — Incremental voice sample generator.

Reads test1.txt and renders each active (non-commented) line to its own
MP3 file, skipping lines whose output file is already up-to-date.
An output file is considered stale when it is older than test1.txt itself.

Usage (normally invoked via the Makefile `test-voices` target):

    python test/test-voices.py \\
        --input            test/test1.txt \\
        --output-dir       build/test-results/voices \\
        --voices-config    test/multi-voice.conf \\
        --instruct-config  test/instruct.conf \\
        [--qwen3-clone-config <path>] \\
        [--debug]
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from book_assistant.Commons import log

# Matches the speaker tag at the start of a line, e.g. [Anna, malinconica]:
_SPEAKER_PATTERN = re.compile(r'^\s*\[\s*([^\]]+?)\s*\]\s*:')

# Characters that are illegal in file names on both macOS and Linux
_UNSAFE_CHARS = re.compile(r'[/\\\0]')


def _sanitize(tag: str) -> str:
    """Convert a speaker tag string into a safe file-name stem.

    Spaces are preserved; only characters that are genuinely illegal or
    awkward in file names are replaced with underscores.

    :param tag:     raw text extracted from inside the [...] brackets,
                    e.g. 'Anna, malinconica'
    :return:        sanitized stem, e.g. 'Anna, malinconica'
    """
    return _UNSAFE_CHARS.sub('_', tag).strip()


def _parse_voices(input_path: Path) -> list[tuple[int, str, str]]:
    """Parse active voice lines from *input_path*.

    Returns one entry per non-commented line that carries a speaker tag.
    Each entry is a (line_number, sanitized_stem, raw_line) triple.

    :param input_path:  path to the .txt file (e.g. test1.txt)
    :return:            list of (line_no, stem, raw_line) tuples
    """
    entries = []
    with open(input_path, encoding='utf-8') as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            match = _SPEAKER_PATTERN.match(line)
            if match:
                tag   = match.group(1)
                stem  = _sanitize(tag)
                entries.append((lineno, stem, line))
    return entries


def _is_stale(output_path: Path) -> bool:
    """Return True when *output_path* must be regenerated.

    :param output_path:     candidate output file
    :return:                True if the file is missing or older than the source
    """
    return not output_path.exists()


def _build_command(line: str,
                   output_path: Path,
                   voices_config: list[str],
                   instruct_config: list[str],
                   qwen3_clone_config: list[str],
                   debug: bool) -> list[str]:
    """Assemble the BookAssistant CLI command for a single line.

    The line is passed via stdin using a temporary file written to the
    process via a shell heredoc — actually we write it to a temp file
    approach; instead we pass it through a pipe by writing it to a
    NamedTemporaryFile. Simpler: we write the single line to a temp file
    and pass that as the path argument.

    :param line:                raw text line from test1.txt
    :param output_path:         where to write the MP3
    :param voices_config:       list of --voices-config values
    :param instruct_config:     list of --instruct-config values
    :param qwen3_clone_config:  list of --qwen3-clone-config values (may be empty)
    :param debug:               whether to pass --debug
    :return:                    argv list suitable for subprocess
    """
    cmd = ['BookAssistant', 'tts']

    if debug:
        cmd.append('--debug')

    for v in voices_config:
        cmd += ['--voices-config', v]
    for i in instruct_config:
        cmd += ['--instruct-config', i]
    for q in qwen3_clone_config:
        cmd += ['--qwen3-clone-config', q]

    cmd += ['--format', 'mp3', '--output', str(output_path)]
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="Incremental per-voice MP3 generator for test1.txt")
    parser.add_argument('--input',               required=True,                 help='Path to test1.txt')
    parser.add_argument('--output-dir',          required=True,                 help='Directory for output MP3 files')
    parser.add_argument('--voices-config',       action='append', default=[],   help='--voices-config passed to BookAssistant (repeatable)')
    parser.add_argument('--instruct-config',     action='append', default=[],   help='--instruct-config passed to BookAssistant (repeatable)')
    parser.add_argument('--qwen3-clone-config',  action='append', default=[],   help='--qwen3-clone-config passed to BookAssistant (repeatable)')
    parser.add_argument('--debug', action='store_true', default=False,          help='Pass --debug to BookAssistant and enable verbose output here')

    args = parser.parse_args()

    input_path  = Path(args.input).resolve()
    output_dir  = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.is_file():
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        return 1

    entries      = _parse_voices(input_path)

    if not entries:
        print("No active voice lines found.", file=sys.stderr)
        return 0

    skipped  = 0
    rendered = 0
    errors   = 0

    for lineno, stem, raw_line in entries:
        output_path = output_dir / f"{stem}.mp3"

        if not _is_stale(output_path):
            if args.debug:
                log(f"[line {lineno}] up-to-date: {output_path.name}")
            skipped += 1
            continue

        log(f"[line {lineno}] rendering: {output_path.name}")
        tmp_path = output_dir / f".tmp_line_{lineno}.txt"

        try:
            tmp_path.write_text(raw_line + '\n', encoding='utf-8')

            cmd = _build_command(
                line               = raw_line,
                output_path        = output_path,
                voices_config      = args.voices_config,
                instruct_config    = args.instruct_config,
                qwen3_clone_config = args.qwen3_clone_config,
                debug              = args.debug,
            )
            cmd.append(str(tmp_path))

            if args.debug:
                log(f"  cmd: {' '.join(cmd)}")

            result = subprocess.run(cmd)
            if result.returncode != 0:
                log(f"  error: BookAssistant exited with code {result.returncode}")
                errors += 1
            else:
                rendered += 1
        finally:
            tmp_path.unlink(missing_ok=True)

    log(f"\nDone: {rendered} rendered, {skipped} skipped, {errors} error(s).")
    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())