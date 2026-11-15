# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

"""Tests that the voices are rendered correctly.

The cloned voices are those defined in the Qwen3 clone configs listed, separated by spaces, in the environment variable
VOICES; if it isn't set (or is empty), in all the *voices.conf files of the voices repository, cloned (shallow) into
build/repositories/voices if not already there (delete that folder to clone it again). The native voices are those
listed in native-voices.conf (file name: voice name), next to this file. Each voice reads a sample text, rendered as an
MP3 file in build/test-results; voices already rendered (a non-empty file) aren't rendered again, and with
--skip-rendered their tests are skipped. Every file is then transcribed with Whisper and the test fails if the transcription differs too much from the sample text (word error rate
above MAX_WORD_ERROR_RATE). The tts command logs at the debug level (shown by pytest for the failed tests, or always
with -s).
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from book_assistant.Commons import read_dict, set_debug

_VOICES_REPOSITORY = "https://github.com/fabiusdieciscudi/voices"

_VOICES_CLONE = Path(__file__).parents[1] / "build" / "repositories" / "voices"

_NATIVE_VOICES = read_dict(str(Path(__file__).parent / "native-voices.conf"))

_STT_MODEL = "mlx-community/whisper-large-v3-turbo-asr-fp16"

_STT_SAMPLE_RATE = 16000

MAX_WORD_ERROR_RATE = 0.2

_SAMPLE_TEXT = ("Mi chiamo {name}. Sono una voce narrante. Parlo bene in italiano. Vediamo l'inglese: this is a wonderful "
                "day. E proviamo anche il francese: c'est la vie.")

_DIGITS = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove"]

_LETTERS = {"A": "a", "B": "bi", "C": "ci", "D": "di", "E": "e", "F": "effe", "G": "gi", "H": "acca", "I": "i",
            "J": "i lunga", "K": "cappa", "L": "elle", "M": "emme", "N": "enne", "O": "o", "P": "pi", "Q": "cu",
            "R": "erre", "S": "esse", "T": "ti", "U": "u", "V": "vu", "W": "doppia vu", "X": "ics", "Y": "ipsilon",
            "Z": "zeta"}

# Consonants transcribed as single letters, as they are when a voice name is spelled (e.g. 'M' for 'emme'); the vowels
# needn't be mapped, as their names are the letters themselves
_CONSONANT_NAMES = {letter.lower(): name for letter, name in _LETTERS.items() if letter not in "AEIOU"}

# Characters not allowed in file names on macOS, Linux or Windows
_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


def _voices_configs() -> list[str]:
    """Returns the Qwen3 clone configs: those in the environment variable VOICES or, if it isn't set, all the
    *voices.conf files of the voices repository, which is cloned (shallow, without history) if not already there.

    :return:                        the config files
    """
    if os.environ.get("VOICES"):
        return os.environ["VOICES"].split()
    if not _VOICES_CLONE.is_dir():
        # Cloned aside and then renamed, so that an interrupted clone isn't taken as a good one
        partial = _VOICES_CLONE.with_name(_VOICES_CLONE.name + ".partial")
        shutil.rmtree(partial, ignore_errors=True)
        partial.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", "--quiet", _VOICES_REPOSITORY, str(partial)], check=True)
        partial.rename(_VOICES_CLONE)
    return sorted(str(path) for path in _VOICES_CLONE.rglob("*voices.conf"))


_VOICES_CONFIGS = _voices_configs()


def _qwen3_voices(config_paths: list[str]) -> list[str]:
    """Returns the native names of the voices defined in Qwen3 clone configs (e.g. ``Qwen3:084M``), as the tts command
    names them; the ``@`` entries (e.g. ``084M@ref``) are attributes of a voice, not voices.

    :param config_paths:            the config files, merged as the tts command does; if none, there are no voices (and
                                    the test is skipped)
    :return:                        the voice names
    """
    if not config_paths:
        return []
    return [f"Qwen3:{key}" for key in read_dict(config_paths) if "@" not in key]


def _spoken_name(voice: str) -> str:
    """Returns the name of a voice as Qwen3 can pronounce it, without the engine prefix: digits are spelled one by one,
    and so are the letters of codes (uppercase runs of at most three letters); words are kept; separators become spaces.
    E.g. ``Qwen3:041M`` -> ``zero quattro uno emme``, ``Qwen3:CML.8181`` -> ``ci emme elle otto uno otto uno``.

    :param voice:                   the voice name
    :return:                        the spoken name
    """
    words = []
    for token in re.findall(r'\d|[^\W\d_]+', voice.split(":", 1)[-1]):
        if token.isdigit():
            words.append(_DIGITS[int(token)])
        elif token.isupper() and len(token) <= 3 and all(c in _LETTERS for c in token):
            words.extend(_LETTERS[c] for c in token)
        else:
            words.append(token)
    return " ".join(words)


def _normalized_words(text: str) -> list[str]:
    """Returns the words of a text in a form that can be compared with a transcription: lowercase, without punctuation
    and apostrophes (e.g. ``l'inglese`` -> ``linglese``), digits spelled one by one, single consonants spelled
    (e.g. ``084M`` -> ``zero otto quattro emme``).

    :param text:                    the text
    :return:                        the words
    """
    words = []
    for token in re.findall(r'\d|[^\W\d_]+', re.sub(r"['’`]", "", text.lower())):
        if token.isdigit():
            words.append(_DIGITS[int(token)])
        else:
            words.append(_CONSONANT_NAMES.get(token, token))
    return words


def _word_error_rate(expected: list[str], actual: list[str]) -> float:
    """Returns the word error rate: the words substituted, deleted or inserted (Levenshtein distance between the
    word sequences), divided by the number of expected words.

    :param expected:                the expected words
    :param actual:                  the actual words
    :return:                        the word error rate
    """
    previous = list(range(len(actual) + 1))
    for i, expected_word in enumerate(expected, 1):
        current = [i]
        for j, actual_word in enumerate(actual, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (expected_word != actual_word)))
        previous = current
    return previous[-1] / max(len(expected), 1)


def _file_name(voice: str) -> str:
    """Returns the name of the output file of a voice, with the characters not allowed in file names replaced by _.

    :param voice:                   the voice name
    :return:                        the file name
    """
    return _UNSAFE_CHARS.sub("_", voice) + ".mp3"


@pytest.fixture(scope="session")
def tts_command():
    """The tts command, set up once for all the tests, so that the models are loaded once and shared by the voices."""
    from book_assistant.tts.TTSCommand import TTSCommand
    set_debug(True)
    command = TTSCommand()
    command._setup(qwen3_clone_config=_VOICES_CONFIGS, format="MP3")
    return command


@pytest.fixture(scope="session")
def stt_model():
    """The speech-to-text model, loaded once for all the tests."""
    from mlx_audio.stt import load
    return load(_STT_MODEL)


@pytest.fixture(scope="session")
def results_dir(pytestconfig: pytest.Config) -> Path:
    """The folder where the rendered samples are written."""
    path = pytestconfig.rootpath / "build" / "test-results"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.mark.parametrize("voice", _qwen3_voices(_VOICES_CONFIGS))
def test_voice(voice: str, results_dir: Path, tmp_path: Path, request: pytest.FixtureRequest,
               capsys: pytest.CaptureFixture[str]):
    _check_voice(voice, _spoken_name(voice), results_dir / _file_name(voice), tmp_path, request, capsys)


@pytest.mark.parametrize("file_name, voice", _NATIVE_VOICES.items(), ids=list(_NATIVE_VOICES))
def test_native_voice(file_name: str, voice: str, results_dir: Path, tmp_path: Path,
                      request: pytest.FixtureRequest, capsys: pytest.CaptureFixture[str]):
    _check_voice(voice, file_name.replace("_", " "), results_dir / (_UNSAFE_CHARS.sub("_", file_name) + ".mp3"),
                 tmp_path, request, capsys)


def _check_voice(voice: str, name: str, output_path: Path, tmp_path: Path, request: pytest.FixtureRequest,
                 capsys: pytest.CaptureFixture[str]) -> None:
    """Renders the sample text with a voice, unless already rendered, and checks its transcription; with
    --skip-rendered, a voice already rendered is skipped.

    :param voice:                   the voice name
    :param name:                    the name the voice says it has
    :param output_path:             the rendered file
    :param tmp_path:                a temporary folder
    :param request:                 the pytest request, for the options and to get the models only when needed
    :param capsys:                  the pytest capture, to print on the terminal
    """
    text = _SAMPLE_TEXT.format(name=name)
    with capsys.disabled():
        print(f"\nTesting voice {voice}")

    if output_path.is_file() and output_path.stat().st_size > 0:
        if request.config.getoption("--skip-rendered"):
            pytest.skip(f"already rendered: {output_path}")
        with capsys.disabled():
            print(f"Already rendered: {output_path}")
    else:
        # Requested only here, so that the TTS models aren't loaded when all the voices are already rendered
        tts_command = request.getfixturevalue("tts_command")
        text_file = tmp_path / "sample.txt"
        text_file.write_text(f"[{voice}]: {text}\n", encoding="utf-8")
        tts_command._output_file_name = str(output_path)
        tts_command.generate_wav_from_file(str(text_file))

    import librosa
    import soundfile as sf

    audio, sample_rate = sf.read(output_path, dtype="float32", always_2d=True)
    audio = librosa.resample(audio.mean(axis=1), orig_sr=sample_rate, target_sr=_STT_SAMPLE_RATE)
    # Requested only here, so that the STT model isn't loaded when all the voices are skipped
    stt_model = request.getfixturevalue("stt_model")
    transcription = stt_model.generate(audio, language="it").text.strip()
    word_error_rate = _word_error_rate(_normalized_words(text), _normalized_words(transcription))
    with capsys.disabled():
        print(f"Transcription: {transcription}")
        print(f"Word error rate: {word_error_rate:.2f} (max {MAX_WORD_ERROR_RATE})")
    if word_error_rate > MAX_WORD_ERROR_RATE:
        # No traceback: the failure is the mismatch of the text, the code has nothing to show
        pytest.fail(f"word error rate {word_error_rate:.2f} (max {MAX_WORD_ERROR_RATE}):\n"
                    f"  expected:    {text}\n  transcribed: {transcription}", pytrace=False)
