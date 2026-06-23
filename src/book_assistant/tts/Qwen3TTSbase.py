#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import gc
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from .AbstractTTS import AbstractTTS
from book_assistant.Commons import warning

CLONE_PROMPT  = 'clone'
DESIGN_PROMPT = 'design'
_SAMPLE_RATE = 24000
_VOICE_NAMES = ['', 'aiden', 'dylan', 'eric', 'ono_anna', 'ryan', 'serena', 'sohee', 'uncle_fu', 'vivian']

_BASE_MODEL_MLX      = {'Lite': 'mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit',
                        'Pro':  'mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit'}
_CUSTOM_VOICE_MODEL_MLX = {'Lite': 'mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit',
                           'Pro':  'mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit'}
_BASE_MODEL_PT       = {'Lite': 'Qwen/Qwen3-TTS-12Hz-0.6B-Base',
                        'Pro':  'Qwen/Qwen3-TTS-12Hz-1.7B-Base'}
_CUSTOM_VOICE_MODEL_PT = {'Lite': 'Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice',
                          'Pro':  'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'}

# VoiceDesign only ships as a 1.7B checkpoint - no 'Lite' variant.
_VOICE_DESIGN_MODEL_MLX = {'Pro': 'mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit'}
_VOICE_DESIGN_MODEL_PT  = {'Pro': 'Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign'}


@dataclass
class Qwen3Params:
    """Generation parameters for Qwen3-TTS.

    Both backends (MLX and PyTorch) accept the same set.  Unset fields
    (None) fall through to each backend's own defaults so that callers
    only need to specify what they want to override.

    Talker controls the semantic-token stage (text → prosody).
    Subtalker controls the acoustic-token stage (prosody → audio).
    When subtalker_* fields are None they mirror the talker values.
    """
    # ── Talker ────────────────────────────────────────────────────────────
    temperature:          Optional[float] = None   # 0.9 recommended
    top_p:                Optional[float] = None   # 1.0 recommended
    top_k:                Optional[int]   = None   # 50  recommended
    repetition_penalty:   Optional[float] = None   # 1.05 recommended
    max_tokens:           Optional[int]   = None   # 2048 default

    # ── SubTalker (acoustic stage) ─────────────────────────────────────
    # When None, the backend reuses the talker values above.
    subtalker_temperature:        Optional[float] = None
    subtalker_top_p:              Optional[float] = None
    subtalker_top_k:              Optional[int]   = None

    # ── Speed (MLX only — PT backend ignores this field) ──────────────
    speed: float = 1.0

    def do_sample(self) -> bool:
        """True when any sampling parameter is set."""
        return any(v is not None for v in (
            self.temperature, self.top_p, self.top_k, self.repetition_penalty))

    def talker_kwargs(self) -> dict:
        """Returns a dict of non-None talker kwargs for the PT backend."""
        out = {}
        if self.temperature        is not None: out['temperature']        = self.temperature
        if self.top_p              is not None: out['top_p']              = self.top_p
        if self.top_k              is not None: out['top_k']              = self.top_k
        if self.repetition_penalty is not None: out['repetition_penalty'] = self.repetition_penalty
        if self.max_tokens         is not None: out['max_new_tokens']     = self.max_tokens
        return out

    def subtalker_kwargs(self) -> dict:
        """Returns a dict of non-None subtalker kwargs for the PT backend.
        Falls back to the talker value when the subtalker field is None."""
        def _pick(sub, talker):
            return sub if sub is not None else talker
        out = {}
        t = _pick(self.subtalker_temperature, self.temperature)
        p = _pick(self.subtalker_top_p,       self.top_p)
        k = _pick(self.subtalker_top_k,       self.top_k)
        if t is not None: out['subtalker_temperature'] = t
        if p is not None: out['subtalker_top_p']       = p
        if k is not None: out['subtalker_top_k']       = k
        if t is not None or p is not None or k is not None:
            out['subtalker_dosample'] = True
        return out


def register_custom_voice_model(key: str, pt_repo: str = None, mlx_repo: str = None) -> None:
    """Registers an extra CustomVoice-compatible checkpoint under *key*.

    Lets callers plug in fine-tuned checkpoints (e.g. an Italian-expressive
    fine-tune of Qwen3-TTS-CustomVoice) without touching this module, by
    passing ``model_size=key`` to :func:`Qwen3TTS`. At least one of
    *pt_repo*/*mlx_repo* must be given; the other backend simply won't be
    available for that key.

    Note: this assumes the checkpoint exposes the same
    ``generate_custom_voice`` / ``generate_voice_clone`` API as the official
    Qwen3-TTS-CustomVoice models. Fine-tunes with a different inference API
    (e.g. a bespoke ``.inference()`` method) need a dedicated backend branch
    instead of this registration mechanism.
    """
    if pt_repo:
        _CUSTOM_VOICE_MODEL_PT[key] = pt_repo
    if mlx_repo:
        _CUSTOM_VOICE_MODEL_MLX[key] = mlx_repo


# Sensible preset for audiobook narration (community-tested values).
AUDIOBOOK_PARAMS = Qwen3Params(
    temperature=0.9,
    top_p=1.0,
    top_k=50,
    repetition_penalty=1.05,
)


class _Qwen3TTSBase(AbstractTTS):
    """Shared interface for both backends. Not instantiated directly."""

    def __init__(self, voice_name: str, language: str, model_size: str,
                 params: Qwen3Params = None):
        super().__init__("Qwen3", voice_name, language, _SAMPLE_RATE, max_words=250)
        self._model_size = model_size
        self._params = params or Qwen3Params()

    def close(self):
        warning(f"Unloading Qwen3-MLX ({self._model_size}) from '{self._model_name}'")

        if hasattr(self, '_initialized') and self._initialized:
            del self._model
            self._extra_close()
            gc.collect()
            self._initialized = False

    def _extra_close(self):
        pass

    @abstractmethod
    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray: ...

    @abstractmethod
    def clone_voice(self, audio: str, text: str, pkl_file: str): ...