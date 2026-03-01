#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import os
from pathlib import Path
from language_tool_python import LanguageTool
from Commons import log, red, debug, measure_time

SPELLCHECK_COMMAND = "spellcheck"

_LANGUAGE_MAP = {
    'dutch':      'nl',
    'english':    'en',
    'french':     'fr',
    'german':     'de',
    'irish':      'ga',
    'italian':    'it',
    'latin':      'it',
    'portuguese': 'pt',
    'spanish':    'es',
    'swedish':    'sv',
    'turkish':    'tr'
}


def _load_custom_dictionary(file_path: str | Path, dictionary: dict[str, set[str]]) -> None:
    """Loads a custom dictionary from a file into the given dictionary.

    :param file_path:   the file with the dictionary
    :param dictionary:  the dictionary to store into
    """
    file_path = Path(file_path).resolve()

    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    lang = "italian"

    with open(file_path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()

            if not line or line.startswith('#'):
                continue

            if line.startswith('@'):
                lang = line[1:].strip().lower()
                if lang not in dictionary:
                    dictionary[lang] = set()
                continue

            word = line.strip()
            if word:
                dictionary[lang].add(word)


class SpellChecker:
    """Stateful spell checker: owns its LanguageTool instances and custom dictionaries."""

    def __init__(self):
        self._lang_tools: dict[str, LanguageTool] = {}
        self._dictionary: dict[str, set[str]] = {}

    def load_dictionary(self, file_path: str | Path) -> None:
        """Load a custom dictionary file into this checker.

        :param file_path:   path to the dictionary file
        """
        _load_custom_dictionary(file_path, self._dictionary)

    def check(self, file_path: Path) -> None:
        """Spell-check a single file.

        :param file_path:   path to the .txt file to check
        """
        current_lang_code = 'it'
        current_lang_name = 'italian'
        accumulator: list[str] = []
        line_number = 0

        file_name = file_path.name
        debug(f"Processing: {file_name}...")

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line_number += 1
            log(f"{file_name}[{line_number}/{len(lines)}]", new_line=False)
            line = line.replace("’", "'")

            for word in line.split():
                word = ''.join(c for c in word if not c in '.,!?;:—…()[]{}"“”«»').strip()

                if not word.startswith("@"):
                    accumulator.append(word)
                else:
                    requested_lang = word[1:].lower().strip() or "italian"

                    if requested_lang not in _LANGUAGE_MAP:
                        log(f"{file_name}[{line_number}]: Unsupported language: @{requested_lang}")
                    else:
                        new_lang_code = _LANGUAGE_MAP[requested_lang]
                        if new_lang_code != current_lang_code:
                            self._check_words(accumulator, current_lang_code, current_lang_name, file_name, line_number)
                            accumulator = []
                            current_lang_code = new_lang_code
                            current_lang_name = requested_lang

            self._check_words(accumulator, current_lang_code, current_lang_name,
                              file_name, line_number)
            accumulator = []

    def close(self) -> None:
        """Close all LanguageTool instances and release resources."""
        for tool in self._lang_tools.values():
            tool.close()
        self._lang_tools.clear()

    def _get_or_create_tool(self, lang_code: str) -> LanguageTool:
        """Return a cached LanguageTool, creating it on first use.

        :param lang_code:   BCP-47 language code
        :return:            the LanguageTool instance
        """
        if lang_code not in self._lang_tools:
            self._lang_tools[lang_code] = self._create_language_tool(lang_code)
        return self._lang_tools[lang_code]

    @staticmethod
    def _create_language_tool(lang_code: str) -> LanguageTool:
        """Instantiate a LanguageTool for the given language code.

        :param lang_code:   BCP-47 language code
        :return:            a new LanguageTool instance
        """
        os.environ['JAVA_HOME'] = os.environ['JAVA17_HOME']
        tool, seconds = measure_time(lambda: LanguageTool(lang_code, config={
            'cacheSize': 2000,
            'pipelineCaching': True,
            'maxPipelinePoolSize': 200,
            'pipelineExpireTimeInSeconds': 7200,
            'maxCheckThreads': 20,
            'maxCheckTimeMillis': 5000,
        }))
        debug(f"LanguageTool for {lang_code} created in: {seconds:.3f} sec")
        return tool

    def _check_words(self,
                     accumulator: list[str],
                     lang_code: str,
                     lang_name: str,
                     file_name: str,
                     line_number: int) -> None:
        """Run LanguageTool on the accumulated words and report spelling errors.

        :param accumulator:     words collected since the last flush
        :param lang_code:       BCP-47 language code
        :param lang_name:       human-readable language name (used for dictionary lookup)
        :param file_name:       source file name (for error messages)
        :param line_number:     current line number (for error messages)
        """
        if not accumulator:
            return

        partial_text = ' '.join(accumulator)
        tool = self._get_or_create_tool(lang_code)
        matches = tool.check(partial_text)

        errors = [
            m for m in matches
            if m.rule_id.startswith('MORFOLOGIK_RULE')
               or 'TYPO' in m.rule_id
               or m.category == 'TYPOS'
        ]

        known_words = self._dictionary.get(lang_name, set())
        for err in errors:
            if err.matched_text not in known_words:
                log(f"{file_name}[{line_number}]: '{lang_name}' '{red(err.matched_text)}' {err.category}")


def spell_check_args(parser) -> None:
    """Configure the command-line arguments parser.

    :param parser:  the argparse parser
    """
    parser.add_argument("--dict", action="append", default=None,
                        help="Optional custom dictionary file. Can be repeated.")


def spell_check_run(args):
    """Prepare and return a per-file spell-check callback.

    Creates a single SpellChecker, loads any requested dictionaries,
    and returns a closure that checks one file at a time. The checker
    is closed (and its LanguageTool instances released) after each file
    so that no stale handles accumulate across a batch run.

    :param args:    parsed command-line arguments
    :return:        a callable (Path) -> None
    """
    checker = SpellChecker()

    for dict_file in (args.dict or []):
        checker.load_dictionary(dict_file)
        log(f"Custom dictionary loaded from: {dict_file}")

    def run(file_path: Path) -> None:
        try:
            checker.check(file_path)
        finally:
            checker.close()

    return run