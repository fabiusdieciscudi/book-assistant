#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

"""Sound library and mixing for ambiences ([ambient:…]) and sound effects ([sfx:…]).

Sounds are configured on two levels, like the voices:

* the sound files config (like the Qwen3 clone config) maps a mnemonic to an audio file; a relative
  path is resolved against the folder of the config file:

      FS.123456:  freesound/123456-heavy-rain.flac
      FS.98765:   freesound/98765-door-knock.wav

* the sounds config (like the voices config) maps the names used in the text to a mnemonic, with
  optional parameters; ``loudness`` (alias ``l``) is a gain in dB applied every time the sound is used:

      pioggia:    FS.123456;loudness=-24
      bussare:    FS.98765

A name used in the text can also be a mnemonic directly, as a speaker can be a voice name.
"""
import math
import os
from dataclasses import dataclass

import numpy as np

from book_assistant.Commons import read_dict, debug

DEFAULT_FADE = 1.0          # seconds, for ambiences without an explicit fade
_LOOP_CROSSFADE = 0.05      # seconds, between the repetitions of a looped ambience
_LOUDNESS_KEYS = {"loudness", "l"}
_LOUDNESS_RANGE = (-60.0, 20.0)


@dataclass(frozen=True)
class Sfx:
    """An inline sound effect: played in sequence (the narration waits) or over the following audio."""
    name: str
    overlay: bool = False
    loudness: float = 0.0
    fade: float = 0.0               # seconds of fade-in and of fade-out
    skip: float = 0.0               # seconds dropped at the start of the sound
    cut: float = 0.0                # seconds dropped at the end of the sound
    duration: float | None = None   # seconds kept (after skip), None for all
    delay: float = 0.0              # seconds of silence before the sound


@dataclass(frozen=True)
class Ambient:
    """A change of ambience at a position of the output: a new sound, or None to stop it."""
    position: int
    name: str | None
    loudness: float = 0.0
    fade: float = DEFAULT_FADE
    repeat: bool = True
    skip: float = 0.0
    cut: float = 0.0
    duration: float | None = None


def parse_loudness(value: str, context: str) -> float:
    text = value.strip()
    if text.lower().endswith("db"):
        text = text[:-2].strip()
    try:
        gain = float(text)
    except ValueError:
        raise ValueError(f"{context}: invalid loudness '{value}': expected a value in dB, e.g. -6") from None
    low, high = _LOUDNESS_RANGE
    if not low <= gain <= high:
        raise ValueError(f"{context}: loudness {gain} dB out of range [{low}, {high}]")
    return gain


_SECONDS_KEYS = ("fade", "skip", "cut", "duration", "delay")


def parse_sound_tag(body: str, kind: str) -> tuple[str, dict]:
    """Parses the body of a sound tag, e.g. ``tuono;overlay;loudness=-3`` or ``pioggia;fade=3``.

    :param body:                    what follows ``ambient:`` or ``sfx:``
    :param kind:                    ``ambient`` or ``sfx``, for validation and messages
    :return:                        the sound name and the options
    """
    name, *items = [part.strip() for part in body.split(";")]
    if not name:
        raise ValueError(f"{kind} tag without a sound name")
    options: dict = {}
    for item in items:
        if not item:
            continue
        key, sep, value = item.partition("=")
        key = key.strip().lower()
        if key in _LOUDNESS_KEYS and sep:
            options["loudness"] = parse_loudness(value, f"{kind} '{name}'")
        elif key in _SECONDS_KEYS and sep:
            try:
                seconds = float(value)
            except ValueError:
                raise ValueError(f"{kind} '{name}': invalid {key} '{value}': expected seconds") from None
            if seconds < 0 or (key == "duration" and seconds == 0):
                raise ValueError(f"{kind} '{name}': {key} must be {'greater than zero' if key == 'duration' else 'zero or more'}")
            options[key] = seconds
        elif key == "repeat" and sep and kind == "ambient":
            flag = value.strip().lower()
            if flag not in ("on", "off"):
                raise ValueError(f"ambient '{name}': invalid repeat '{value}': expected on or off")
            options["repeat"] = flag == "on"
        elif key == "overlay" and kind == "sfx":
            options["overlay"] = (value.strip().lower() not in ("false", "no", "0")) if sep else True
        else:
            valid = ("cut,delay,duration,fade,loudness,l,overlay,skip" if kind == "sfx"
                     else "cut,delay,duration,fade,loudness,l,repeat,skip")
            raise ValueError(f"{kind} '{name}': unknown option '{item}' - valid values: {valid}")
    return name, options


class SoundLibrary:

    def __init__(self, sound_files_config: str | list[str] | None, sounds_config: str | list[str] | None):
        self._files: dict[str, str] = {}                       # mnemonic -> path
        self._sounds: dict[str, tuple[str, float]] = {}        # name -> (mnemonic, loudness)
        self._cache: dict[tuple[str, int], np.ndarray] = {}
        self._durations: dict[str, float] = {}

        for file_path in _as_list(sound_files_config):
            base = os.path.dirname(os.path.abspath(file_path))
            for mnemonic, path in read_dict(file_path).items():
                if not path:
                    raise ValueError(f"Sound files config '{file_path}', '{mnemonic}': missing file")
                self._files[mnemonic] = path if os.path.isabs(path) else os.path.normpath(os.path.join(base, path))

        for file_path in _as_list(sounds_config):
            for name, spec in read_dict(file_path).items():
                mnemonic, *items = [part.strip() for part in spec.split(";")]
                context = f"Sounds config, sound '{name}'"
                if mnemonic not in self._files:
                    raise ValueError(f"{context}: unknown sound file '{mnemonic}' (not in the sound files config)"
                                     f" - valid values: {_valid_values(self._files)}")
                loudness = 0.0
                for item in items:
                    key, sep, value = item.partition("=")
                    if key.strip().lower() in _LOUDNESS_KEYS and sep:
                        loudness = parse_loudness(value, context)
                    elif item:
                        raise ValueError(f"{context}: unknown option '{item}' - valid values: loudness,l")
                self._sounds[name] = (mnemonic, loudness)

    def _resolve(self, name: str) -> tuple[str, float]:
        """Returns the mnemonic and the loudness for a name used in the text, which can also be a mnemonic."""
        return self._sounds[name] if name in self._sounds else (name, 0.0)

    def __contains__(self, name: str) -> bool:
        return name in self._sounds or name in self._files

    def duration(self, name: str) -> float:
        """The duration in seconds of the file of a sound, read from its header.

        :raises ValueError:         if the file doesn't exist or can't be read
        """
        import soundfile as sf
        mnemonic = self._resolve(name)[0]
        path = self._files[mnemonic]
        if mnemonic not in self._durations:
            if not os.path.isfile(path):
                raise ValueError(f"sound '{name}': file of '{mnemonic}' not found: {path}")
            try:
                self._durations[mnemonic] = sf.info(path).duration
            except (RuntimeError, sf.LibsndfileError) as e:
                raise ValueError(f"sound '{name}': file of '{mnemonic}' can't be read: {path}: {e}") from None
        return self._durations[mnemonic]

    def is_stereo(self, name: str, sample_rate: int) -> bool:
        return is_stereo(self.get(name, sample_rate))

    def valid_names(self) -> str:
        """The names that can be used in the text (sounds, then sound files), for error messages."""
        return f"{_valid_values(self._sounds)} or {_valid_values(self._files)}"

    def __len__(self) -> int:
        return len(self._sounds)

    def files_as_dict(self) -> dict[str, str]:
        return dict(self._files)

    def sounds_as_dict(self) -> dict[str, str]:
        return {name: f"{mnemonic} ({loudness:+g} dB)" for name, (mnemonic, loudness) in self._sounds.items()}

    def get(self, name: str, sample_rate: int, loudness: float = 0.0) -> np.ndarray:
        """Returns the sound as a float32 waveform at *sample_rate*, with its base loudness and *loudness* applied:
        one dimension for a mono sound, shape ``(samples, 2)`` for a stereo one."""
        mnemonic, base_loudness = self._resolve(name)
        key = (mnemonic, sample_rate)
        if key not in self._cache:
            import soundfile as sf
            path = self._files[mnemonic]
            audio, sr = sf.read(path, dtype="float32", always_2d=True)
            audio = audio if audio.shape[1] == 2 else audio.mean(axis=1)      # stereo is kept, anything else is mono
            if sr != sample_rate:
                import librosa
                audio = librosa.resample(y=audio, orig_sr=sr, target_sr=sample_rate, res_type="soxr_hq", axis=0)
            debug(f"Sound '{mnemonic}' loaded from '{path}': {len(audio) / sample_rate:.1f} sec, "
                  f"{'stereo' if is_stereo(audio) else 'mono'}")
            self._cache[key] = audio.astype(np.float32)
        gain = base_loudness + loudness
        return self._cache[key] * np.float32(10 ** (gain / 20))


def is_stereo(audio: np.ndarray) -> bool:
    return audio.ndim == 2


def as_stereo(audio: np.ndarray) -> np.ndarray:
    """Returns *audio* as stereo, with the same signal in both channels if it is mono."""
    return audio if is_stereo(audio) else np.column_stack((audio, audio))


def _ramp(start: float, stop: float, n: int, like: np.ndarray) -> np.ndarray:
    """A linear ramp of *n* samples, shaped to multiply *like* (mono or stereo)."""
    ramp = np.linspace(start, stop, n, dtype=np.float32)
    return ramp[:, None] if is_stereo(like) else ramp


def trimmed(sound: np.ndarray, skip: float, cut: float, duration: float | None, sample_rate: int) -> np.ndarray:
    """Returns *sound* without its first *skip* and its last *cut* seconds, and at most *duration* seconds long."""
    start = int(skip * sample_rate)
    end = len(sound) - int(cut * sample_rate)
    if duration is not None:
        end = min(end, start + int(duration * sample_rate))
    return sound[start:max(start, end)]


def check_sound(library: SoundLibrary, name: str, skip: float, cut: float, context: str) -> None:
    """Raises ValueError if the file of the sound doesn't exist or can't be read, or if *skip* and *cut* leave nothing of it."""
    try:
        length = library.duration(name)
    except ValueError as e:
        raise ValueError(f"{context}: {e}") from None
    if skip or cut:
        if skip + cut >= length:
            raise ValueError(f"{context}: skip={skip:g} and cut={cut:g} leave nothing of sound '{name}' ({length:.2f} sec)")


def delayed(sound: np.ndarray, delay: float, sample_rate: int) -> np.ndarray:
    """Returns *sound* preceded by *delay* seconds of silence."""
    n = int(delay * sample_rate)
    return np.concatenate((np.zeros((n,) + sound.shape[1:], dtype=np.float32), sound)) if n > 0 else sound


def faded(sound: np.ndarray, fade: float, sample_rate: int) -> np.ndarray:
    """Returns *sound* with a linear fade-in and fade-out of *fade* seconds each (at most half the sound)."""
    n = min(int(fade * sample_rate), len(sound) // 2)
    if n <= 0:
        return sound
    out = sound.copy()
    out[:n] *= _ramp(0.0, 1.0, n, out)
    out[-n:] *= _ramp(1.0, 0.0, n, out)
    return out


def _valid_values(values) -> str:
    return ",".join(sorted(values)) or "none"


def _as_list(files: str | list[str] | None) -> list[str]:
    """As with ``read_dict``, several config files are read in sorted order and a later definition wins."""
    return [] if not files else [files] if isinstance(files, str) else sorted(files)


def _looped(sound: np.ndarray, length: int, sample_rate: int) -> np.ndarray:
    """Repeats *sound* to *length* samples, with a short crossfade at each seam so the loop doesn't click."""
    if len(sound) == 0:
        return np.zeros((length,) + sound.shape[1:], dtype=np.float32)
    if len(sound) >= length:
        return sound[:length].copy()
    xfade = min(int(_LOOP_CROSSFADE * sample_rate), len(sound) // 4)
    ramp_in = _ramp(0.0, 1.0, xfade, sound)
    pieces = [sound[:len(sound) - xfade]]
    joint = sound[len(sound) - xfade:]                      # the tail, still to be crossfaded with the next copy
    produced = len(pieces[0])
    while produced < length:
        pieces.append(joint * ramp_in[::-1] + sound[:xfade] * ramp_in)
        pieces.append(sound[xfade:len(sound) - xfade])
        produced += xfade + len(sound) - 2 * xfade
    return np.concatenate(pieces)[:length].astype(np.float32)


def mix_ambience(audio: np.ndarray, events: list[Ambient], library: SoundLibrary, sample_rate: int) -> np.ndarray:
    """Mixes the ambiences under *audio*.

    Each ambience fades in with its own fade and lasts until the next change, crossfading with it
    over the fade of the next change; the last one lasts until the end of the audio. An ambience
    with ``repeat=off`` is played only once, so it may end earlier.
    """
    if not events:
        return audio
    events = sorted(events, key=lambda e: e.position)     # a delayed change can come after a later one
    stereo = is_stereo(audio) or any(library.is_stereo(e.name, sample_rate) for e in events if e.name)
    out = (as_stereo(audio) if stereo else audio).astype(np.float32, copy=True)
    total = len(out)
    for i, event in enumerate(events):
        if event.name is None or event.position >= total:
            continue
        following = events[i + 1] if i + 1 < len(events) else None
        fade_in = int(event.fade * sample_rate)
        fade_out = int(following.fade * sample_rate) if following else 0
        end = min(total, (following.position if following else total) + fade_out)
        length = end - event.position
        if length <= 0:
            continue
        sound = trimmed(library.get(event.name, sample_rate, event.loudness),
                        event.skip, event.cut, event.duration, sample_rate)
        if stereo:
            sound = as_stereo(sound)
        if event.repeat:
            bed = _looped(sound, length, sample_rate)
        else:                                           # played once: silence after its end
            bed = np.zeros((length,) + sound.shape[1:], dtype=np.float32)
            bed[:min(length, len(sound))] = sound[:length]
        envelope = np.ones(length, dtype=np.float32)
        if fade_in:
            n = min(fade_in, length)
            envelope[:n] = np.linspace(0.0, 1.0, n, dtype=np.float32)
        if following and fade_out:
            n = min(fade_out, length)
            envelope[-n:] *= np.linspace(1.0, 0.0, n, dtype=np.float32)
        out[event.position:end] += bed * (envelope[:, None] if stereo else envelope)
    peak = float(np.max(np.abs(out))) if total else 0.0
    if peak > 1.0:
        debug(f"Ambience mix clipped (peak {20 * math.log10(peak):+.1f} dBFS)")
        out = np.clip(out, -1.0, 1.0)
    return out
