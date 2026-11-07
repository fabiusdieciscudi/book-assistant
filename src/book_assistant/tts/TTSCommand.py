#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import io
import re
import string
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, BinaryIO
import librosa
import numpy as np
import soundfile as sf
from book_assistant.CommandBase import CommandBase
from book_assistant.Commons import count_words, log, read_dict, yellow, cyan, debug, single_channel, measure_time
from .AbstractTTS import AbstractTTS
from .AzzurraVoiceTTS import AzzurraVoiceTTS
from .MacOSTTS import MacOSTTS
from .PiperTTS import PiperTTS
from .SibiliaTTS import SibiliaTTS
from .Qwen3TTS import Qwen3TTS
from .Qwen3TTSbase import Qwen3Params, AUDIOBOOK_PARAMS, register_custom_voice_model, _Qwen3TTSBase
from .VoxtralTTS import VoxtralTTS
from .LRUModelCache import LRUModelCache

_TTS_COMMAND = "tts"
_SPEAKER_PATTERN = re.compile(r'^\s*\[\s*([^,\]]+?)\s*(?:,\s*([^,\]]+?)\s*)?\]\s*:\s*')
# Inline pause tag: [pause] or [pause:<seconds>], e.g. [pause:1.5].
_PAUSE_TAG_PATTERN = re.compile(r'\[\s*pause\b([^\]]*)\]', re.IGNORECASE)
_PAUSE_ARG_PATTERN = re.compile(r'^\s*:\s*(\d+(?:\.\d+)?)\s*s?\s*$')
_CHAR_TRANSLATIONS = str.maketrans({"’": "'", "…": "...", '“': '"', '”': '"'})
_DEFAULT_PAUSE_LINES: set[str] = {"", "***"}


def _dump_config(name: str, config: dict) -> None:
    if config:
        debug(f"{name}:")
        for key in sorted(config.keys()):
            debug(f"    {key: >30} -> {config[key]}")


def _parse_qwen3_params(raw: list[str] | None) -> Qwen3Params:
    """Parses ``--qwen3-params`` CLI values into a :class:`Qwen3Params`.

    Each item in *raw* is a ``key:value`` string, e.g. ``temperature:0.9``.
    The special value ``audiobook`` expands to :data:`AUDIOBOOK_PARAMS`.
    Unknown keys raise :class:`ValueError`.

    Examples::

        --qwen3-params audiobook
        --qwen3-params temperature:0.9 --qwen3-params repetition_penalty:1.05
    """
    if not raw:
        return Qwen3Params()

    # Flatten in case multiple --qwen3-params flags each carry a list
    items = []
    for entry in raw:
        items.extend(entry.split())

    if "audiobook" in items:
        return AUDIOBOOK_PARAMS

    kwargs = {}
    for item in items:
        if ":" not in item:
            raise ValueError(f"--qwen3-params: expected 'key:value', got '{item}'")
        key, _, val = item.partition(":")
        kwargs[key] = _convert_param(key, val, "--qwen3-params")

    return Qwen3Params(**kwargs)


_INT_PARAMS   = {"top_k", "subtalker_top_k", "max_tokens"}
_FLOAT_PARAMS = {"temperature", "top_p", "repetition_penalty",
                 "subtalker_temperature", "subtalker_top_p", "speed"}
_ALL_PARAMS   = _INT_PARAMS | _FLOAT_PARAMS
# Parameters that any voice accepts, because they are applied by BookAssistant itself
# after generation. All the others are Qwen3 sampling parameters.
_UNIVERSAL_PARAMS = {"speed"}
_PARAM_ALIASES = {"temp": "temperature"}
_VOICE_PARAMS_SEPARATOR = ";"


def _convert_param(key: str, val: str, context: str) -> int | float:
    """Validates *key* and converts *val* to the parameter's type.

    :param key:                     the parameter name
    :param val:                     the raw value
    :param context:                 where the parameter comes from, for error messages
    :return:                        the converted value
    """
    if key not in _ALL_PARAMS:
        raise ValueError(f"{context}: unknown parameter '{key}'. Valid: {sorted(_ALL_PARAMS)}")
    try:
        value = int(val) if key in _INT_PARAMS else float(val)
    except ValueError:
        raise ValueError(f"{context}: invalid value '{val}' for parameter '{key}'") from None
    if key == "speed" and value <= 0:
        raise ValueError(f"{context}: speed must be greater than zero, got {value}")
    return value


def _split_pauses(text: str) -> list[str | float | None]:
    """Splits *text* at the inline pause tags.

    :param text:                    the text, possibly containing ``[pause]`` or ``[pause:<seconds>]``
    :return:                        the text segments (``str``) interleaved with the pauses:
                                    ``None`` for the default duration, a ``float`` for an explicit one
    """
    parts: list[str | float | None] = []
    position = 0
    for match in _PAUSE_TAG_PATTERN.finditer(text):
        parts.append(text[position:match.start()])
        argument = match.group(1)
        if not argument.strip():
            parts.append(None)
        else:
            duration = _PAUSE_ARG_PATTERN.match(argument)
            if not duration:
                raise ValueError(f"Invalid pause tag '{match.group(0)}': expected [pause] or [pause:<seconds>], e.g. [pause:1.5]")
            parts.append(float(duration.group(1)))
        position = match.end()
    parts.append(text[position:])
    # Drops empty segments and leftovers made only of punctuation (e.g. the '.' in "Ciao. [pause].").
    return [part for part in parts if not isinstance(part, str) or any(c.isalnum() for c in part)]


def _normalized_pauses(text: str) -> str:
    """Rewrites the pause tags in a compact form (e.g. ``[ pause : 1.5 ]`` -> ``[pause:1.5]``),
    so that sentence splitting never cuts through a tag."""
    return _PAUSE_TAG_PATTERN.sub(lambda m: f"[pause:{float(_PAUSE_ARG_PATTERN.match(m.group(1)).group(1))}]"
                                  if m.group(1).strip() else "[pause]", text)


def _time_stretch(chunk: np.ndarray, sample_rate: int, speed: float) -> np.ndarray:
    """Changes the speed of a mono chunk without changing its pitch, using Sonic.

    Sonic is a pitch-synchronous algorithm designed for speech.

    :param chunk:                   the mono audio
    :param sample_rate:             the sample rate of the audio
    :param speed:                   the speed multiplier (> 1 faster, < 1 slower)
    :return:                        the stretched audio
    """
    from libsonic import SonicStream

    stream = SonicStream(sample_rate, 1)
    stream.set_speed(speed)
    stream.write(np.clip(chunk, -1.0, 1.0).astype(np.float32))
    stream.flush()
    return np.asarray(stream.read(stream.available_frames()), dtype=np.float32)


def _parse_voice_spec(speaker: str, spec: str) -> tuple[str, dict[str, int | float]]:
    """Splits a voices config value into the voice name and its per-voice parameters.

    The value is the voice name, optionally followed by ``;key=value`` items, e.g.
    ``Qwen3:F-eA-pN-tG-vN-008;temperature=0.9;speed=0.9``. ``temp`` is accepted as
    an alias for ``temperature``.

    :param speaker:                 the speaker the value belongs to, for error messages
    :param spec:                    the raw value
    :return:                        the voice name and the parameters
    """
    tts_name, *items = [part.strip() for part in spec.split(_VOICE_PARAMS_SEPARATOR)]
    context = f"Voices config, speaker '{speaker}'"
    params = {}
    for item in items:
        if not item:
            continue
        key, sep, val = item.partition("=")
        if not sep:
            raise ValueError(f"{context}: expected 'key=value', got '{item}'")
        key = key.strip()
        key = _PARAM_ALIASES.get(key, key)
        params[key] = _convert_param(key, val.strip(), context)
    return tts_name, params


class TTSCommand(CommandBase):

    def __init__(self):
        super().__init__(_TTS_COMMAND)
        self._word_count = 0

    def process_args(self, parser: ArgumentParser) -> None:
        parser.add_argument("--voices-config",                default=None, action="append", help="Multi voice configuration")
        parser.add_argument("--instruct-config",              default=None, action="append", help="Voice instruct configuration")
        parser.add_argument("--qwen3-clone-config",           default=None, action="append", help="Configuration for Qwen3 cloned voices")
        parser.add_argument("--qwen3-model-config",           default=None, action="append", help="Extra CustomVoice-compatible Qwen3 checkpoints (name: HF repo_id)")
        parser.add_argument("--word-patches",                 default=None, action="append", help="Word patches")
        parser.add_argument("--qwen3-params",                 default=None, action="append", help="Qwen3 generation parameters (key:value, e.g. temperature:0.9)")
        parser.add_argument("--max-lines",          type=int, default=99999,                 help="Max. number of lines to process")
        parser.add_argument("--max-loaded-models",  type=int, default=5,                     help="Max. number of models to keep in memory")
        parser.add_argument("--format",                       default="WAV",                 help="Output file format (default: WAV)")
        parser.add_argument("--compression",                  default=0,                     help="Output file compression level ([0...100) - default: 0)")
        parser.add_argument("--output",                       default=None,                  help="Output file (default: stdout)")

    def _run(self, args, path: Path) -> None:
        self._setup(voice_config=args.voices_config,
                    instruct_config=args.instruct_config,
                    qwen3_clone_config=args.qwen3_clone_config,
                    qwen3_model_config=args.qwen3_model_config,
                    qwen3_params=args.qwen3_params,
                    word_patches=args.word_patches,
                    output=args.output,
                    format=args.format,
                    compression_level=args.compression / 100,
                    max_lines=args.max_lines,
                    max_loaded_models=args.max_loaded_models,
                    dry_run=args.dry_run)
        self.generate_wav_from_file(str(path))

    def _finish(self) -> None:
        super()._finish()
        log(f"Generated text from {self._word_count} words, {self._word_count / (self._duration / 1_000_000_000):.1f} words/sec")

    def _setup(self,
               voice_config=None,
               instruct_config=None,
               qwen3_clone_config=None,
               qwen3_model_config=None,
               qwen3_params=None,
               word_patches=None,
               output=None,
               format="WAV",
               compression_level=0,
               max_lines=99999,
               max_loaded_models=5,
               dry_run=False) -> None:
        raw_voice_map             = read_dict(voice_config) if voice_config else {}
        self._tts_name_by_speaker = {}
        self._voice_params_by_speaker: dict[str, dict[str, int | float]] = {}
        for speaker, spec in raw_voice_map.items():
            tts_name, voice_params = _parse_voice_spec(speaker, spec)
            self._tts_name_by_speaker[speaker] = tts_name
            if voice_params:
                self._voice_params_by_speaker[speaker] = voice_params
        self._instruct_map        = read_dict(instruct_config) if instruct_config else {}
        self._word_patches_map    = read_dict(word_patches) if word_patches else {}
        self._output_file_name    = output
        self._max_lines           = max_lines
        self._sample_rate         = 22050
        self._new_line_silence_duration = 0.1
        self._pause_silence_duration    = 1
        self._pause_lines         = _DEFAULT_PAUSE_LINES
        self._format              = format
        self._compression_level   = compression_level
        self._dry_run             = dry_run

        qwen3_clone_map = read_dict(qwen3_clone_config) if qwen3_clone_config else {}
        qwen3_model_map = read_dict(qwen3_model_config) if qwen3_model_config else {}
        q3params = _parse_qwen3_params(qwen3_params)
        _dump_config("Voice config",       raw_voice_map)
        _dump_config("Instruct config",    self._instruct_map)
        _dump_config("Word patches",       self._word_patches_map)
        _dump_config("Qwen3 clone map",    qwen3_clone_map)
        _dump_config("Qwen3 model map",    qwen3_model_map)

        tts_by_name = {
            "MacOS:Federica": MacOSTTS("Federica (Premium)", "italian"),
            "MacOS:Siri":     MacOSTTS("", "italian"),
            "MacOS:Luca":     MacOSTTS("Luca (Enhanced)", "italian"),
            "MacOS:Paola":    MacOSTTS("Paola (Enhanced)", "italian"),
            "MacOS:Emma":     MacOSTTS("Emma (Premium)", "italian"),
            "MacOS:Alice":    MacOSTTS("Alice (Enhanced)", "italian"),

            "Piper:Riccardo": PiperTTS("it_IT-riccardo-x_low", "italian", "rhasspy/piper-voices", "it/it_IT/riccardo/x_low", 16000, "v1.0.0"),
            "Piper:Paola":    PiperTTS("it_IT-paola-medium",   "italian", "rhasspy/piper-voices", "it/it_IT/paola/medium",   22050, "v1.0.0"),
            "Piper:Aurora":   PiperTTS("it_IT-aurora-medium",  "italian", "kirys79/piper_italiano", "Aurora", 22050),

            "Qwen3":          Qwen3TTS("",         "italian", params=q3params),
            "Qwen3:Aiden":    Qwen3TTS("aiden",    "italian", params=q3params),
            "Qwen3:Dylan":    Qwen3TTS("dylan",    "italian", params=q3params),
            "Qwen3:Eric":     Qwen3TTS("eric",     "italian", params=q3params),
            "Qwen3:Ono Anna": Qwen3TTS("ono_anna", "italian", params=q3params),
            "Qwen3:Ryan":     Qwen3TTS("ryan",     "italian", params=q3params),
            "Qwen3:Serena":   Qwen3TTS("serena",   "italian", params=q3params),
            "Qwen3:Sohee":    Qwen3TTS("sohee",    "italian", params=q3params),
            "Qwen3:Uncle Fu": Qwen3TTS("uncle_fu", "italian", params=q3params),
            "Qwen3:Vivian":   Qwen3TTS("vivian",   "italian", params=q3params),
            "Qwen3:Design":   Qwen3TTS("design",   "italian", params=q3params),

            "AzzurraVoice":   AzzurraVoiceTTS(),

            "Sibilia":        SibiliaTTS(),

            # Voxtral-4B-TTS-2603 (Mistral, CC BY-NC 4.0 — personal use only)
            # Italian preset voices
            "Voxtral:Male":           VoxtralTTS("it_male",   "italian"),
            "Voxtral:Female":         VoxtralTTS("it_female", "italian"),
            # French preset voices — useful for cross-lingual generation:
            "Voxtral:FrMale":         VoxtralTTS("fr_male",   "french"),
            "Voxtral:FrFemale":       VoxtralTTS("fr_female", "french"),
            # English presets
            "Voxtral:CasualMale":     VoxtralTTS("casual_male",     "english"),
            "Voxtral:CasualFemale":   VoxtralTTS("casual_female",   "english"),
            "Voxtral:NeutralMale":    VoxtralTTS("neutral_male",    "english"),
            "Voxtral:NeutralFemale":  VoxtralTTS("neutral_female",  "english"),
            "Voxtral:Cheerful":       VoxtralTTS("cheerful_female", "english"),
        }

        for key, value in qwen3_clone_map.items():
            if "@" not in key:
                tts_by_name[f"Qwen3:{key}"] = Qwen3TTS(value, "italian", ref_text=qwen3_clone_map.get(f"{key}@ref", ""), params=q3params)

        for key, repo_id in qwen3_model_map.items():
            # Registers a fine-tuned, CustomVoice-API-compatible checkpoint
            # (e.g. an Italian-expressive fine-tune) under a new model_size
            # key, and exposes it as "Qwen3:<key>" using the default speaker.
            register_custom_voice_model(key, pt_repo=repo_id, mlx_repo=repo_id)
            tts_by_name[f"Qwen3:{key}"] = Qwen3TTS("", "italian", model_size=key, params=q3params)

        for speaker, voice_params in self._voice_params_by_speaker.items():
            tts_name = self._tts_name_by_speaker[speaker]
            sampling_keys = sorted(set(voice_params) - _UNIVERSAL_PARAMS)
            if sampling_keys and tts_name in tts_by_name and not isinstance(tts_by_name[tts_name], _Qwen3TTSBase):
                raise ValueError(f"Voices config, speaker '{speaker}': parameters {sampling_keys} "
                                 f"are only supported by Qwen3 voices, not by '{tts_name}'")

        _dump_config("Per-voice params",   self._voice_params_by_speaker)
        self._tts_by_name = LRUModelCache(tts_by_name, capacity=max_loaded_models)

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

    def _process_text(self, tts: AbstractTTS, sentence: str, instruct: str, waveforms: list[Any],
                      voice_params: dict[str, int | float] | None = None) -> None:
        """Render a single sentence.

        :param tts:                     the TTS to use
        :param sentence:                the sentence to render
        :param instruct:                the TTS instruct for adapting the voice
        :param waveforms:               where to append the generated waveforms
        :param voice_params:            the per-voice parameters from the voices config
        """
        debug(f"_process_text({tts.prefix()}, '{sentence}', '{instruct}', {voice_params or {}}, ...)")
        sentence = sentence.strip()
        voice_params = voice_params or {}

        if sentence in self._pause_lines:
            waveforms.append(self._silence(self._pause_silence_duration))
            return

        rendered = False
        for part in _split_pauses(sentence):
            if isinstance(part, str):
                chunk = self._render_segment(tts, part.strip(), instruct, voice_params)
                if chunk.size > 0:
                    waveforms.append(chunk)
                    rendered = True
            else:
                duration = self._pause_silence_duration if part is None else part
                debug(f"Inline pause: {duration} sec")
                waveforms.append(self._silence(duration))

        pause = tts.pause_after_new_line()
        if rendered and pause:
            waveforms.append(self._silence(pause))

    def _render_segment(self, tts: AbstractTTS, text: str, instruct: str,
                        voice_params: dict[str, int | float]) -> np.ndarray:
        """Renders a piece of text with no pause tags, at the output sample rate.

        :param tts:                     the TTS to use
        :param text:                    the text to render
        :param instruct:                the TTS instruct for adapting the voice
        :param voice_params:            the per-voice parameters from the voices config
        :return:                        the waveform (possibly empty)
        """
        instruct_key = f"{tts.prefix()}.{instruct}"
        text = self._patched(text)
        instruct_text = self._instruct_map.get(instruct_key, "")
        sampling_params = {k: v for k, v in voice_params.items() if k not in _UNIVERSAL_PARAMS}

        def render() -> np.ndarray:
            if sampling_params:
                with tts.overridden_params(sampling_params):
                    return tts.generate_single_chunk(text, instruct_text)
            return tts.generate_single_chunk(text, instruct_text)

        chunk, seconds = measure_time(lambda: single_channel(render()))
        debug(f">>>> rendered in {seconds:.1f} sec ({count_words(text) / seconds:.1f} words/sec)")

        if chunk.size > 0:
            current_sr = tts.sample_rate()
            if current_sr != self._sample_rate:
                chunk = librosa.resample(y=chunk, orig_sr=current_sr, target_sr=self._sample_rate, res_type='soxr_hq')

            # Speed is applied here for every voice: the Qwen3 models don't support it natively.
            speed = voice_params.get("speed")
            if speed is None and isinstance(tts, _Qwen3TTSBase):
                speed = tts.params().speed
            if speed and speed != 1.0:
                debug(f"Applying speed {speed}")
                chunk = _time_stretch(chunk, self._sample_rate, speed)

        return chunk

    def _patched(self, sentence: str) -> str:
        """Patch *sentence* using the word-patches map.

        Each key is replaced only where it stands as a whole token, i.e.
        where it is not flanked by a letter. This stops a French
        'Michel' -> 'Miscèl' patch from turning the Italian 'Michele'
        into 'Miscèle'. A boundary is anything that is not a letter:
        punctuation, whitespace, digits or a string edge. Accented
        letters (à, è, ç, ...) count as letters, so an adjacent accent
        still blocks the match.

        Keys may span several words or whole foreign phrases; any run of
        whitespace inside a key matches any run of whitespace in the text
        (so 'detti seguito' still matches across a double space or a line
        break). Matching is case-sensitive and every pair is applied
        independently in a single left-to-right pass, so a substitution's
        output is never re-matched by another key.

        :param sentence:                the sentence
        :return:                        the patched sentence
        """
        if not self._word_patches_map:
            return sentence
        pattern = self._word_patches_pattern()
        return pattern.sub(
            lambda m: self._word_patches_groups[m.lastgroup], sentence
        )

    def _word_patches_pattern(self):
        """Return the compiled alternation for the patch map, built once.

        Each key becomes a named group whose body escapes the literal text
        but turns every internal whitespace run into '\\s+', so multi-word
        keys (or whole foreign phrases) tolerate any spacing in the text --
        a plain space, a double space, a line break or a non-breaking space.
        The replacement is fetched by the matched group's name rather than
        by the matched text, so it stays correct whatever the real spacing
        was. Keys are sorted longest-first so a longer key wins over one
        that is a prefix of it (e.g. 'Michelangelo' before 'Michel'). The
        outer lookarounds assert the match is not flanked by a Unicode
        letter -- [^\\W\\d_] means 'a letter': Unicode-aware (so à/è/ç
        count), digits and '_' do not. Compiled lazily on first use and
        cached, together with a group-name -> replacement map for lookups.
        """
        pattern = getattr(self, "_word_patches_re", None)
        if pattern is None:
            import re
            letter = r"[^\W\d_]"
            self._word_patches_groups = {}
            parts = []
            keys = sorted(self._word_patches_map, key=len, reverse=True)
            for index, key in enumerate(keys):
                tokens = key.split()
                if not tokens:
                    continue
                name = f"wp{index}"
                self._word_patches_groups[name] = self._word_patches_map[key]
                body = r"\s+".join(re.escape(token) for token in tokens)
                parts.append(f"(?P<{name}>{body})")
            alternation = "|".join(parts)
            pattern = re.compile(rf"(?<!{letter})(?:{alternation})(?!{letter})")
            self._word_patches_re = pattern
        return pattern

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
                    try:
                        parts = _split_pauses(line)
                    except ValueError as e:
                        raise ValueError(f"{file_name}, line {l}: {e}") from None
                    line = _normalized_pauses(line)

                    # A line with only pause tags needs no voice.
                    if parts and all(not isinstance(part, str) for part in parts):
                        if not dry_run:
                            for part in parts:
                                duration = self._pause_silence_duration if part is None else part
                                log(f"{file_name}[ {l: >3}   ]: pause {duration} sec")
                                waveforms.append(self._silence(duration))
                        waveforms.append(self._silence(self._new_line_silence_duration))
                        continue

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

                    speaker_variant = f"{speaker}.{instruct}"
                    if speaker_variant in self._tts_name_by_speaker:
                        speaker = speaker_variant
                    if speaker in self._tts_name_by_speaker:
                        tts_name = self._tts_name_by_speaker[speaker]
                        if not tts_name in self._tts_by_name.keys():
                            raise ValueError(f"Unknown TTS: '{tts_name}' - valid values: {','.join(sorted(self._tts_by_name.keys()))}")
                    elif speaker in self._tts_by_name:
                        tts_name = speaker
                    else:
                        raise ValueError(f"Unknown speaker: '{speaker}' - valid values: {','.join(sorted(self._tts_name_by_speaker.keys()))} or {','.join(sorted(self._tts_by_name.keys()))}")

                    tts = self._tts_by_name[tts_name]
                    voice_params = self._voice_params_by_speaker.get(speaker, {})

                    if not dry_run and (prev_speaker != speaker or prev_instruct != instruct):
                        log(f"Changed speaker: {yellow(speaker)}, voice: {yellow(tts_name)}, instruct: {yellow(instruct)}"
                            + (f", params: {yellow(str(voice_params))}" if voice_params else ""))

                    if speaker != "default" and line and not line[-1] in string.punctuation:
                        line = f"{line}."

                    if count_words(line) <= tts.max_words():
                        if not dry_run:
                            words = count_words(line)
                            self._word_count += words
                            log(f"{file_name}[ {l: >3}   ]: ({words : >3} words): {cyan(line)}")
                            self._process_text(tts, line, instruct, waveforms, voice_params)
                    else:
                        sentences = re.split(r'(?<=[.;:!?])\s+|\s*\.{3}\s*', line)
                        if not dry_run:
                            for s, sentence in enumerate(sentences, 1):
                                words = count_words(sentence)
                                self._word_count += words
                                log(f"{file_name}[ {l: >3}.{s:<2}]: ({words : >3} words): {cyan(sentence)}")
                                self._process_text(tts, sentence.strip(), instruct, waveforms, voice_params)

                waveforms.append(self._silence(self._new_line_silence_duration))

        return waveforms

    def generate_wav_from_file(self, input_file_path: str) -> None:
        """Renders text in a file.

        :param input_file_path:         the input file with the text to render
        """
        # First round to check that all speakers are configured.
        self._generate_wav_from_file(input_file_path, dry_run=True)

        if not self._dry_run:
            debug(f"Writing to '{self._output_file_name}' ...")
            output = sys.stdout.buffer if self._output_file_name is None else open(self._output_file_name, "wb")
            try:
                waveforms = self._generate_wav_from_file(input_file_path, dry_run=False)
                if waveforms:
                    self._write_output(output, waveforms)
            finally:
                if output is not None:
                    output.close()
