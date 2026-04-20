#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import os
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path
from book_assistant.Commons import debug, is_debug, log
from .Qwen3TTSbase import _Qwen3TTSBase, Qwen3Params, CLONE_PROMPT, DESIGN_PROMPT, _VOICE_NAMES, \
    _BASE_MODEL_MLX, _CUSTOM_VOICE_MODEL_MLX, _VOICE_DESIGN_MODEL_MLX

class Qwen3TTSmlx(_Qwen3TTSBase):

    def __init__(self, voice_name: str, language: str, model_size: str,
                 ref_text: str = None, params: Qwen3Params = None):
        super().__init__(voice_name, language, model_size, params)

        self._is_voice_design = (voice_name == DESIGN_PROMPT)
        is_clone = (voice_name == CLONE_PROMPT or voice_name.endswith(".mp3") or voice_name.endswith(".wav"))

        if self._is_voice_design:
            self._model_name  = _VOICE_DESIGN_MODEL_MLX[model_size]
            self._voice_name  = None
            self._ref_audio   = None
            self._ref_text    = None
        elif is_clone:
            self._model_name  = _BASE_MODEL_MLX[model_size]
            self._voice_name  = None
            self._ref_audio   = voice_name
            self._ref_text    = ref_text
        else:
            if voice_name not in _VOICE_NAMES:
                raise ValueError(f"Unsupported voice: {voice_name}")
            self._model_name  = _CUSTOM_VOICE_MODEL_MLX[model_size]
            self._voice_name  = voice_name
            self._ref_audio   = None
            self._ref_text    = None

    def _deferred_init(self):
        from mlx_audio.tts.utils import load_model
        import mlx.core as mx
        from transformers import logging as hf_logging, AutoTokenizer

        debug(f"Loading Qwen3-MLX ({self._model_size}) from '{self._model_name}'")
        local_path = self._ensure_hf_model(
            repo_id=self._model_name,
            allow_patterns=["*.safetensors", "config.json", "*.json", "*.txt", "*.model"])
        # mlx_audio calls transformers internally and triggers two spurious warnings:
        #   1. "model of type qwen3_tts to instantiate a model of type" — the custom
        #      Qwen3TTSModel type isn't registered in the transformers hub, but loads fine.
        #   2. "incorrect regex pattern … fix_mistral_regex=True" — the tokenizer carries
        #      a Mistral-inherited lookahead regex; harmless for TTS inference.
        # Both are WARNING-level noise; suppress them for the duration of the load.
        prev_verbosity = hf_logging.get_verbosity()
        hf_logging.set_verbosity_error()
        try:
            self._model = load_model(Path(local_path))
            self._tokenizer = AutoTokenizer.from_pretrained(local_path, local_files_only=True)
        finally:
            hf_logging.set_verbosity(prev_verbosity)

    def _extra_close(self):
        import mlx.core as mx
        mx.metal.clear_cache()

    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self.ensure_initialized()

        if self._is_voice_design:
            # Call the model's own method directly rather than the generic
            # generate_audio() wrapper: this is the officially documented
            # API for VoiceDesign and avoids relying on generate_audio's
            # (undocumented) mode-detection logic. 'instruct' here carries
            # the natural-language voice description, not a delivery style.
            results = list(self._model.generate_voice_design(
                text=text, language=self._language, instruct=instruct))
            return np.asarray(results[0].audio, dtype=np.float32)

        from mlx_audio.tts.generate import generate_audio

        p = self._params
        extra = {}
        if p.temperature        is not None: extra['temperature']        = p.temperature
        if p.top_p              is not None: extra['top_p']              = p.top_p
        if p.top_k              is not None: extra['top_k']              = p.top_k
        if p.repetition_penalty is not None: extra['repetition_penalty'] = p.repetition_penalty
        if p.max_tokens         is not None: extra['max_tokens']         = p.max_tokens

        ids = self._tokenizer.encode(text)
        tokens = [self._tokenizer.decode([id]) for id in ids]
        log(f"tokenize: {' | '.join(t for t in tokens)}")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            generate_audio(
                text=text,
                speed=p.speed,
                model=self._model,
                voice=self._voice_name,
                ref_audio=self._ref_audio,
                ref_text=self._ref_text,
                lang_code=self._language,
                language=self._language.upper(),
                speaker=self._voice_name,
                voice_prompt=self._ref_audio,
                instruct=instruct,
                output_path=os.path.dirname(tmp_path),
                file_prefix=os.path.basename(tmp_path).replace(".wav", ""),
                audio_format="wav",
                join_audio=True,
                play=False,
                verbose=is_debug(),
                **extra)

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise RuntimeError(f"generate_audio silently failed: '{tmp_path}' empty or missing")

            audio_np, _ = sf.read(tmp_path)
            if audio_np.ndim == 2:
                audio_np = np.mean(audio_np, axis=1)
            return audio_np.astype(np.float32)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def clone_voice(self, audio: str, text: str, pkl_file: str):
        # MLX doesn't support voice cloning via pkl
        raise NotImplementedError("Voice cloning to .pkl is only supported on the PyTorch backend")