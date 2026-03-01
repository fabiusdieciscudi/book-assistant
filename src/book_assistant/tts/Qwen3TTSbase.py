#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import gc
from abc import abstractmethod
import numpy as np

from .AbstractTTS import AbstractTTS
from book_assistant.Commons import warning

CLONE_PROMPT = 'clone'
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

class _Qwen3TTSBase(AbstractTTS):
    """Shared interface for both backends. Not instantiated directly."""

    def __init__(self, voice_name: str, language: str, model_size: str):
        super().__init__("Qwen3", voice_name, language, _SAMPLE_RATE, max_words=250)
        self._model_size = model_size

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