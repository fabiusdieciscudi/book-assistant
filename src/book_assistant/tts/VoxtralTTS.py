#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

# NOTE ON VOICE CLONING
# Voxtral upstream supports zero-shot voice cloning from arbitrary reference audio,
# but mlx-audio's port (added in PR #606) currently only exposes the 20 pre-computed
# voice presets that ship with the model. Custom cloning is tracked in issue #694.
# Until that is resolved, only preset voices are available here.

import numpy as np
import mlx.core as mx
from transformers import logging as hf_logging
from .AbstractTTS import AbstractTTS
from book_assistant.Commons import debug, is_debug

_SAMPLE_RATE = 24000

# Available preset voices per language.
# The voice name passed to generate() must be one of these strings.
VOICES = {
    "english":    ["casual_male", "casual_female", "cheerful_female", "neutral_male", "neutral_female"],
    "french":     ["fr_male",  "fr_female"],
    "spanish":    ["es_male",  "es_female"],
    "german":     ["de_male",  "de_female"],
    "italian":    ["it_male",  "it_female"],
    "portuguese": ["pt_male",  "pt_female"],
    "dutch":      ["nl_male",  "nl_female"],
    "arabic":     ["ar_male"],
    "hindi":      ["hi_male",  "hi_female"],
}

# Flat set for validation
_ALL_VOICES = {v for vs in VOICES.values() for v in vs}

# Available quantizations on mlx-community (size on disk):
#   Voxtral-4B-TTS-2603-mlx-4bit  ~2.5 GB  (fastest, >real-time on M1 Pro 16 GB)
#   Voxtral-4B-TTS-2603-mlx-6bit  ~3.5 GB  (slightly better quality)
#   Voxtral-4B-TTS-2603-mlx-bf16  ~8.0 GB  (full quality, 6x slower)
_MODEL_REPO = {
    "4bit":  "mlx-community/Voxtral-4B-TTS-2603-mlx-4bit",
    "6bit":  "mlx-community/Voxtral-4B-TTS-2603-mlx-6bit",
    "bf16":  "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16",
}
_DEFAULT_QUANTIZATION = "6bit"


class VoxtralTTS(AbstractTTS):
    """Voxtral-4B-TTS-2603 backend (MLX, Apple Silicon only).

    Usage::

        tts = VoxtralTTS("it_male", "italian")
        tts = VoxtralTTS("fr_female", "french", quantization="4bit")

    All 20 Mistral preset voices are available (see VOICES dict above).
    Cross-lingual generation is possible: pass a French voice with Italian text
    to get Italian spoken with a French accent — useful for foreign place names.
    """

    def __init__(self, voice_name: str, language: str,
                 quantization: str = _DEFAULT_QUANTIZATION,
                 max_words: int = 99999):
        if voice_name not in _ALL_VOICES:
            raise ValueError(
                f"Unknown Voxtral voice '{voice_name}'. "
                f"Available: {sorted(_ALL_VOICES)}")
        if quantization not in _MODEL_REPO:
            raise ValueError(
                f"Unknown quantization '{quantization}'. "
                f"Available: {sorted(_MODEL_REPO)}")

        super().__init__("Voxtral", voice_name, language, _SAMPLE_RATE, max_words=max_words)
        self._model_repo = _MODEL_REPO[quantization]
        self._quantization = quantization

    def _deferred_init(self):
        from mlx_audio.tts.utils import load as mlx_load

        debug(f"Loading Voxtral ({self._quantization}) from '{self._model_repo}'")

        # Ensure the model is cached locally first (no-op if already present).
        # Then pass the *repo id* — not the local path — to mlx_load, because
        # mlx_audio's load() runs post_load_hook internally only when given a
        # repo id string; passing a local path skips that hook and leaves the
        # tokenizer uninitialised (RuntimeError: Tokenizer not loaded).
        self._ensure_hf_model(repo_id=self._model_repo)

        prev_verbosity = hf_logging.get_verbosity()
        hf_logging.set_verbosity_error()
        try:
            self._model = mlx_load(self._model_repo)
        finally:
            hf_logging.set_verbosity(prev_verbosity)

    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self.ensure_initialized()

        if not text.strip():
            return np.array([], dtype=np.float32)

        chunks: list[np.ndarray] = []
        for result in self._model.generate(
                text=text,
                voice=self._voice_name):
            audio = result.audio          # mx.array, 24 kHz
            chunks.append(np.array(audio, dtype=np.float32))

        if not chunks:
            return np.array([], dtype=np.float32)

        return np.concatenate(chunks)

    def close(self):
        if self._initialized:
            del self._model
            mx.metal.clear_cache()
            self._initialized = False