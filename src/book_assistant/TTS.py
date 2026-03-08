#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import io
import re
import sys
from pathlib import Path
from typing import Any, BinaryIO

import librosa
import numpy as np
import soundfile as sf

from AbstractTTS import AbstractTTS
from AzzurraVoiceTTS import AzzurraVoiceTTS
from Commons import count_words, log, read_dict, yellow, cyan, debug, single_channel, measure_time
from MacOSTTS import MacOSTTS
from PiperTTS import PiperTTS
from SibiliaTTS import SibiliaTTS
from Qwen3TTS import Qwen3TTS

TTS_COMMAND = "tts"
_SPEAKER_PATTERN = re.compile(r'^\s*\[\s*([^,\]]+?)\s*(?:,\s*([^,\]]+?)\s*)?\]\s*:\s*')
_CHAR_TRANSLATIONS = str.maketrans({"’": "'", "…": "...", '“': '"', '”': '"'})
_DEFAULT_PAUSE_LINES: set[str] = {"", "***"}

class TTS:
    """Generates speech."""
    def __init__(self,
                 tts_by_name: dict[str, AbstractTTS] = {},
                 tts_name_by_speaker: dict[str, str] = {},
                 instruct_map: dict[str, str] = {},
                 word_patches_map: dict[str, str] = {},
                 output_file_name: str = None,
                 max_lines = 99999,
                 sample_rate = 22050,
                 new_line_silence_duration = 0.1,
                 pause_silence_duration = 1,
                 pause_lines=_DEFAULT_PAUSE_LINES,
                 format: str = "WAV",
                 compression_level = 0,
                 dry_run = False):
        """Creates a new instance.

        :param tts_by_name:             the map of TTS generators by name
        :param tts_name_by_speaker:     the map of TTS names by speaker
        :param instruct_map:            the map of instructions
        :param word_patches_map:        the map of word patches
        :param output_file_name:        the name of the file where to store the generated speech (None means stdout)
        :param max_lines:               how many lines of the input file to process
        :param sample_rate:             the sample rate to use
        :param new_line_silence_duration: the duration of silence to add between two lines
        :param pause_silence_duration:  the duration of silence to add for pauses
        :param pause_lines:             the lines that represent a pause in the narration
        :param format:                  the file format (WAV, MP3, ...)
        :param compression_level:       the compression level [0..1)
        :param dry_run:                 whether actual speech rendering is omitted
        """
        self._tts_by_name = tts_by_name
        self._tts_name_by_speaker = tts_name_by_speaker
        self._instruct_map = instruct_map
        self._word_patches_map = word_patches_map
        self._output_file_name = output_file_name
        self._max_lines = max_lines
        self._sample_rate = sample_rate
        self._new_line_silence_duration = new_line_silence_duration
        self._pause_silence_duration = pause_silence_duration
        self._pause_lines = pause_lines
        self._format = format
        self._compression_level = compression_level
        self._dry_run = dry_run

    def _write_output(self, output: BinaryIO, waveforms: list[Any]) -> None:
        """Writes the waveforms to a file.

        :param waveforms:               the list of weveforms to write
        """
        full_waveform = np.concatenate(waveforms)
        log(f"Total generated samples: {len(full_waveform)}, {len(full_waveform) / self._sample_rate:.1f} seconds")
        buffer = io.BytesIO()
        match self._format.upper():
            case "WAV":
                sf.write(buffer, full_waveform, samplerate=self._sample_rate, format="WAV", subtype="PCM_16")
            case "MP3":
                sf.write(buffer, full_waveform, samplerate=self._sample_rate, format="MP3", subtype="MPEG_LAYER_III",
                         bitrate_mode="VARIABLE", compression_level=self._compression_level)
            case _:
                raise ValueError(f"Unsupported format: {self._format}")
        buffer.seek(0)
        output.write(buffer.read())
        output.flush()

    def _process_text(self, tts: AbstractTTS, sentence: str, instruct: str, waveforms: list[Any]) -> None:
        """Render a single sentence.

        :param tts:                     the TTS to use
        :param sentence:                the sentence to render
        :param instruct:                the TTS instruct for adapting the voice
        :param waveforms:               where to append the generated waveforms
        """
        debug(f"_process_text({tts.prefix()}, '{sentence}', '{instruct}', ...)")
        sentence = sentence.strip()

        if sentence in self._pause_lines:
            waveforms.append(self._silence(self._pause_silence_duration))
        else:
            instruct_key = f"{tts.prefix()}.{instruct}"
            sentence = self._patched(sentence)
            chunk, seconds = measure_time(lambda: single_channel(tts.generate_single_chunk(sentence, self._instruct_map.get(instruct_key, ""))))
            debug(f">>>> rendered in {seconds:.1f} sec ({count_words(sentence) / seconds:.1f} words/sec)")

            if chunk.size > 0:
                current_sr = tts.sample_rate()

                if current_sr != self._sample_rate:
                    chunk = librosa.resample(y=chunk, orig_sr=current_sr, target_sr=self._sample_rate, res_type='soxr_hq')

                waveforms.append(chunk)
                pause = tts.pause_after_new_line()

                if pause:
                    waveforms.append(self._silence(pause))

    def _patched(self, sentence: str) -> str:
        """Patches a sentence by using the word_patches_map.

        :param sentence:                the sentence
        :return:                        the patched sentence
        """
        for key, value in self._word_patches_map.items():
            sentence = sentence.replace(key, value)
        return sentence

    def _silence(self, duration: float) -> np.ndarray:
        """Generates a silence waveform.

        :param duration:                the duration of the silence
        :return:                        the waveform
        """
        return np.zeros(int(duration * self._sample_rate), dtype=np.float32)

    def _generate_wav_from_file(self, input_file_path: str, dry_run: bool = False) -> list[Any]:
        """Renders text in a file.

        :param input_file_path:         the input file with the text to render
        :param dry_run:                 whether actual speech rendering should be omitted
        :return:                        the list of waveforms
        """
        log(f"{'Processing' if not dry_run else 'Validating'}: {input_file_path}")
        file_name = Path(input_file_path).name

        with open(input_file_path, "r", encoding="utf-8") as lines_source:
            waveforms = []
            speaker = None
            instruct = None

            for l, line in enumerate(lines_source, 1):
                if l > self._max_lines:
                    break

                if line and not line.startswith("#"):
                    line = line.translate(_CHAR_TRANSLATIONS).strip()
                    match = _SPEAKER_PATTERN.match(line)
                    prev_speaker = speaker
                    prev_instruct = instruct

                    if not match:
                        speaker = "default"
                        instruct = "default"
                    else:
                        speaker = match.group(1).strip()
                        instruct = match.group(2).strip() if match.lastindex >= 2 else "default"
                        line = _SPEAKER_PATTERN.sub('', line).strip()

                    if speaker in self._tts_name_by_speaker:
                        tts_name = self._tts_name_by_speaker[speaker]
                        if not tts_name in self._tts_by_name.keys():
                            raise ValueError(f"Unknown TTS: '{tts_name}' - valid values: {','.join(sorted(self._tts_by_name.keys()))}")
                    elif speaker in self._tts_by_name:
                        tts_name = speaker
                    else:
                        raise ValueError(f"Unknown speaker: '{speaker}' - valid values: {','.join(sorted(self._tts_name_by_speaker.keys()))} or {','.join(sorted(self._tts_by_name.keys()))}")

                    tts = self._tts_by_name[tts_name]

                    if not dry_run and (prev_speaker != speaker or prev_instruct != instruct):
                        log(f"Line {l}: Speaker: {yellow(speaker)}, voice: {yellow(tts_name)}, instruct: {yellow(instruct)}")

                    if count_words(line) <= tts.max_words():
                        if not dry_run:
                            log(f"{file_name}[ {l: >3}   ]: ({count_words(line): >3} words): {cyan(line)}")
                            self._process_text(tts, line, instruct, waveforms)

                    else:
                        sentences = re.split(r'(?<=[.;:!?])\s+|\s*\.{3}\s*', line)
                        if not dry_run:
                            for s, sentence in enumerate(sentences, 1):
                                log(f"{file_name}[ {l: >3}.{s:<2}]: ({count_words(sentence): >3} words): {cyan(sentence)}")
                                self._process_text(tts, sentence.strip(), instruct, waveforms)

                waveforms.append(self._silence(self._new_line_silence_duration))

        return waveforms

    def generate_wav_from_file(self, input_file_path: str) -> None:
        """Renders text in a file.

        :param input_file_path:         the input file with the text to render
        """
        self._generate_wav_from_file(input_file_path, dry_run=True)

        if not self._dry_run:
            output = sys.stdout.buffer if self._output_file_name is None else open(self._output_file_name, "wb")

            try:
                waveforms = self._generate_wav_from_file(input_file_path, dry_run=False)

                if waveforms:
                    self._write_output(output, waveforms)
            finally:
                if output is not None:
                    output.close()

def _dump_config(name: str, config: dict) -> None:
    """Dumps a configuration.

    :param name:                        the name of the configuration
    :param config:                      the configuration
    """
    if dict:
        debug(f"{name}:")
        for key in sorted(config.keys()):
            debug(f"    {key: >20} -> {config[key]}")

def tts_configure(voice_config: str = None,
                  instruct_config: str = None,
                  qwen3_clone_config: str = None,
                  word_patches: str = None,
                  output: BinaryIO = None,
                  format: str = "WAV",
                  compression_level = 0,
                  max_lines=99999,
                  dry_run = False) -> TTS:
    """Instantiates a configured TTS.

    :param voice_config:                the configuration of voices
    :param instruct_config:             the configuration of voice instructions
    :param qwen3_clone_config:          the configuration for Qwen3 cloned voices
    :param word_patches:                the patches to apply to text
    :param output:                      the output file
    :param format:                      the file format (WAV, MP3, ...)
    :param compression_level:           the compression level [0..1)
    :param max_lines:                   the maximum number of lines to process
    :param dry_run:                     whether actual speech rendering should be omitted
    :return:                            an instance of TTS
    """
    tts_name_by_speaker = read_dict(voice_config) if voice_config else {}
    instruct_map = read_dict(instruct_config) if instruct_config else {}
    qwen3_clone_map = read_dict(qwen3_clone_config) if qwen3_clone_config else {}
    word_patches_map = read_dict(word_patches) if word_patches else {}
    _dump_config("Voice config", tts_name_by_speaker)
    _dump_config("Instruct config", instruct_map)
    _dump_config("Word patches", word_patches_map)

    tts_by_name = {
        "MacOS:Federica": MacOSTTS("Federica (Premium)", "italian"),
        "MacOS:Siri":     MacOSTTS("", "italian"),
        "MacOS:Luca":     MacOSTTS("Luca (Enhanced)", "italian"),
        "MacOS:Paola":    MacOSTTS("Paola (Enhanced)", "italian"),
        "MacOS:Emma":     MacOSTTS("Emma (Premium)", "italian"),
        "MacOS:Alice":    MacOSTTS("Alice (Enhanced)", "italian"),

        # Leonardo e Giorgio sono pessimi
        "Piper:Riccardo": PiperTTS("it_IT-riccardo-x_low", "italian", "rhasspy/piper-voices", "it/it_IT/riccardo/x_low", 16000, "v1.0.0"),
        "Piper:Paola":    PiperTTS("it_IT-paola-medium", "italian", "rhasspy/piper-voices", "it/it_IT/paola/medium", 22050, "v1.0.0"),
        "Piper:Aurora":   PiperTTS("it_IT-aurora-medium", "italian", "kirys79/piper_italiano", "Aurora", 22050),

        "Qwen3":          Qwen3TTS("", "italian"),
        "Qwen3:Aiden":    Qwen3TTS("aiden", "italian"),
        "Qwen3:Dylan":    Qwen3TTS("dylan", "italian"),
        "Qwen3:Eric":     Qwen3TTS("eric", "italian"),
        "Qwen3:Ono Anna": Qwen3TTS("ono_anna", "italian"),
        "Qwen3:Ryan":     Qwen3TTS("ryan", "italian"),
        "Qwen3:Serena":   Qwen3TTS("serena", "italian"),
        "Qwen3:Sohee":    Qwen3TTS("sohee", "italian"),
        "Qwen3:Uncle Fu": Qwen3TTS("uncle_fu", "italian"),
        "Qwen3:Vivian":   Qwen3TTS("vivian", "italian"),
        # "Qwen3":          Qwen3TTS("", "italian"),
        # "Qwen3:Aiden":    Qwen3TTS("aiden", "italian"),
        # "Qwen3:Dylan":    Qwen3TTS("dylan", "italian"),
        # "Qwen3:Eric":     Qwen3TTS("eric", "italian"),
        # "Qwen3:Ono Anna": Qwen3TTS("ono_anna", "italian"),
        # "Qwen3:Ryan":     Qwen3TTS("ryan", "italian"),
        # "Qwen3:Serena":   Qwen3TTS("serena", "italian"),
        # "Qwen3:Sohee":    Qwen3TTS("sohee", "italian"),
        # "Qwen3:Uncle Fu": Qwen3TTS("uncle_fu", "italian"),
        # "Qwen3:Vivian":   Qwen3TTS("vivian", "italian"),
        "AzzurraVoice":   AzzurraVoiceTTS(),
        "Sibilia":        SibiliaTTS(),
    }

    _dump_config("Qwen3_clone_map", qwen3_clone_map)
    for key, value in qwen3_clone_map.items():
        if not "@" in key:
            tts_by_name.update({f"Qwen3:{key}": Qwen3TTS(value, "italian", ref_text=qwen3_clone_map.get(f"{key}@ref", ""))})

    return TTS(tts_by_name=tts_by_name,
               tts_name_by_speaker=tts_name_by_speaker,
               instruct_map=instruct_map,
               word_patches_map=word_patches_map,
               output_file_name=output,
               format=format,
               compression_level=compression_level,
               max_lines=max_lines,
               dry_run=dry_run)

def tts_args(parser) -> None:
    """Configure the line argument parser.

    :param parser:                      the parser
    """
    parser.add_argument("--voices-config",        default=None, action="append",  help="Multi voice configuration")
    parser.add_argument("--instruct-config",      default=None, action="append",  help="Voice instruct configuration")
    parser.add_argument("--qwen3-clone-config",   default=None, action="append",  help="Configuration for Qwen3 cloned voices")
    parser.add_argument("--word-patches",         default=None, action="append",  help="Word patches")
    parser.add_argument("--max-lines",  type=int, default=99999,                  help="Max. number of lines to process")
    parser.add_argument("--format",               default="WAV",                  help="Output file format (default: WAV)")
    parser.add_argument("--compression",          default=0,                      help="Output file compression level ([0...100) - default: 0)")
    parser.add_argument("--output",               default=None,                   help="Output file (default: stdout)")

def tts_run(args):
    """ Prepares the TTS to run.

    :param args:                        the command line arguments
    :return:                            a function to call for performing the job
    """
    tts = tts_configure(voice_config=args.voices_config,
                        instruct_config=args.instruct_config,
                        qwen3_clone_config=args.qwen3_clone_config,
                        word_patches=args.word_patches,
                        output=args.output,
                        format=args.format,
                        compression_level=args.compression / 100,
                        max_lines=args.max_lines,
                        dry_run=args.dry_run)
    return tts.generate_wav_from_file
