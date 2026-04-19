#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT
import os

import numpy as np
import espeakng_loader
from phonemizer.backend.espeak.wrapper import EspeakWrapper
from kittentts import KittenTTS as _KittenTTS
from .AbstractTTS import AbstractTTS
from ..Commons import log, debug

# KittenTTS always outputs at 24 kHz.
SAMPLE_RATE = 24000

# Default model; can be overridden per instance.
DEFAULT_MODEL = "KittenML/kitten-tts-mini-0.8"


class KittenTTS(AbstractTTS):
    """TTS backend backed by KittenML/KittenTTS (ONNX, CPU-only).

    KittenTTS is an ultra-lightweight model (25–80 MB) that runs without a
    GPU and exposes a simple ``generate(text, voice=...)`` API returning a
    numpy float32 array at 24 kHz.

    Available built-in voices (mini-0.8):
        'Bella', 'Jasper', 'Luna', 'Bruno', 'Rosie', 'Hugo', 'Kiki', 'Leo'
    """

    def __init__(self,
                 voice_name: str,
                 language: str,
                 model_repo: str = DEFAULT_MODEL):
        """Create a KittenTTS instance.

        :param voice_name:  one of the voices bundled with the model
                            (e.g. 'Bella', 'Jasper', …)
        :param language:    human-readable language name (e.g. 'english')
        :param model_repo:  HuggingFace repo id for the model weights;
                            defaults to ``KittenML/kitten-tts-mini-0.8``
        """
        super().__init__("Kitten", voice_name, language, SAMPLE_RATE)
        self._model_repo = model_repo
        self._model: _KittenTTS | None = None

    def _deferred_init(self) -> None:
        log(f"Initializing KittenTTS model '{self._model_repo}' (voice: {self._voice_name})...")
        # TRICK to reuse the espeak-ng binary lib from the Piper wheel
        os.environ['ESPEAK_DATA_PATH'] = str(espeakng_loader.get_data_path())
        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        # END TRICK
        self._model = _KittenTTS(self._model_repo)
        debug(f"KittenTTS model loaded: {self._model_repo}")

    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        """Synthesise *text* and return a mono float32 waveform.

        The *instruct* parameter is accepted for interface compatibility but
        is not used, as KittenTTS does not support voice instructions.

        :param text:        the sentence to synthesise
        :param instruct:    ignored
        :return:            float32 numpy array at SAMPLE_RATE Hz
        """
        self.ensure_initialized()
        debug(f"KittenTTS.generate_single_chunk('{text}')")

        if not text.strip():
            return np.array([], dtype=np.float32)

        audio = self._model.generate(text, voice=self._voice_name)
        return np.asarray(audio, dtype=np.float32).flatten()