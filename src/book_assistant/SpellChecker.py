#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import os
from pathlib import Path
from language_tool_python import LanguageTool
from Commons import log, red, debug
from Commons import measure_time

SPELLCHECK_COMMAND = "spellcheck"

_LANG_TOOLS: dict[str, LanguageTool] = {}
_DICTIONARY: dict[str, set[str]] = {}

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
    """Loads a custom dictionary from a file.

    :param file_path:               the file with the dictionary
    :param dictionary:              the dictionary to store into
    :return:
    """
    file_path = Path(file_path).resolve()

    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.strip()

            if not line:
                continue

            if line.startswith('#'):
                continue

            if line.startswith('@'):
                lang = line[1:].strip().lower()
                if lang not in dictionary:
                    dictionary[lang] = set()
                continue

            word = line.strip()

            if word:
                dictionary[lang].add(word)

def _create_language_tool(lang_code: str) -> LanguageTool:
    """ Instantiate a LanguageTool for the given language.

    :param lang_code:               the language
    :return:                        the LaguageTool
    """
    os.environ['JAVA_HOME'] = os.environ['JAVA17_HOME']
    tool, seconds = measure_time(lambda:
        LanguageTool(lang_code, config={
            'cacheSize': 2000,
            'pipelineCaching': True,
            'maxPipelinePoolSize': 200,
            'pipelineExpireTimeInSeconds': 7200,
            'maxCheckThreads': 20,
            'maxCheckTimeMillis': 5000  # evita check infiniti
        }))
    debug(f"LanguageTool for {lang_code} created in: {seconds:.3f} sec")
    return tool

def _spell_check_words(accumulator: list[str],
                       current_lang_code: str,
                       current_lang_name: str,
                       file_name: str,
                       line_number: int,
                       tools_map_by_code: dict[str, LanguageTool]) -> None:
    """ Performs a spell check.

    :param accumulator:             the accumulator of results
    :param current_lang_code:       the language code
    :param current_lang_name:       the language name
    :param file_name:               the file name
    :param line_number:             the current line number
    :param tools_map_by_code:       the map of language tools
    :return:
    """
    partial_text = ' '.join(accumulator)

    if not current_lang_code in tools_map_by_code:
        tools_map_by_code[current_lang_code] = _create_language_tool(current_lang_code)

    matches = tools_map_by_code[current_lang_code].check(partial_text)

    errors = [
        m for m in matches
        if m.rule_id.startswith('MORFOLOGIK_RULE') or  # spelling base
           'TYPO' in m.rule_id
           or m.category == 'TYPOS'
           # or m.category == 'CASING'
    ]

    for error in errors:
        if not error.matched_text in _DICTIONARY.get(current_lang_name, {}):
            log(f"{file_name}[{line_number}]: '{current_lang_name}' '{red(error.matched_text)}' {error.category}")

def _spell_check(file_path: Path) -> None:
    """ Spell checks the given file.

    :param file_path:               the path of the file to check
    """
    current_lang_code = 'it'
    current_lang_name = 'italian'
    accumulator = []
    line_number = 0

    try:
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
                if word.startswith("@"):
                    requested_lang = word[1:].lower().strip()

                    if not requested_lang:
                        requested_lang = "italian"

                    if not requested_lang in _LANGUAGE_MAP:
                        log(f"{file_name}[{line_number}]: Unsupported language: @{requested_lang}")
                    else:
                        new_lang_code = _LANGUAGE_MAP[requested_lang]

                        if new_lang_code != current_lang_code:
                            _spell_check_words(accumulator, current_lang_code, current_lang_name, file_name, line_number, _LANG_TOOLS)
                            accumulator = []
                            current_lang_code = new_lang_code
                            current_lang_name = requested_lang
                    continue
                else:
                    accumulator.append(word)

            _spell_check_words(accumulator, current_lang_code, current_lang_name, file_name, line_number, _LANG_TOOLS)
            accumulator = []

    finally:
        for tool in _LANG_TOOLS.values():
            tool.close()

def spell_check_args(parser) -> None:
    """ Configures the command line arguments parser.

    :param parser:              the parser
    """
    parser.add_argument("--dict",  action="append", default=None, help="Optional custom dictionary.")


def spell_check_run(args):
    """ Prepares the spell checker to run.

    :param args:                 the command line arguments
    :return:                     a function to call for performing the job
    """
    for dict in (args.dict or []):
        _load_custom_dictionary(dict, _DICTIONARY)
        log(f"Custom dictionary loaded from: {dict}")
    return _spell_check