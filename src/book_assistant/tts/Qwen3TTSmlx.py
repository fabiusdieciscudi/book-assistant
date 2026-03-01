#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import os, tempfile
import numpy as np
import soundfile as sf
from pathlib import Path
from huggingface_hub import snapshot_download
from mlx_audio.tts.utils import load_model
from mlx_audio.tts.generate import generate_audio
import mlx.core as mx
from book_assistant.Commons import debug, is_debug
from .Qwen3TTSbase import _Qwen3TTSBase, CLONE_PROMPT, _VOICE_NAMES, _BASE_MODEL_MLX, _CUSTOM_VOICE_MODEL_MLX

class Qwen3TTSmlx(_Qwen3TTSBase):

    def __init__(self, voice_name: str, language: str, model_size: str,
                 ref_text: str = None):
        super().__init__(voice_name, language, model_size)

        is_clone = (voice_name == CLONE_PROMPT or voice_name.endswith(".mp3") or voice_name.endswith(".wav"))

        if is_clone:
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
        debug(f"Loading Qwen3-MLX ({self._model_size}) from '{self._model_name}'")
        try:
            self._model = load_model(Path(self._model_name))
        except Exception as e:
            debug(f"Load failed: {e}. Trying snapshot_download...")
            local_path = snapshot_download(
                repo_id=self._model_name,
                allow_patterns=["*.safetensors", "config.json", "*.json"])
            self._model = load_model(Path(local_path))

        # if hasattr(self._model, 'post_load_hook'):
        #     self._model.post_load_hook(self._model, Path(self._model_name))
        # else:
        #     debug("Warning: No post_load_hook found")

    def _extra_close(self):
        mx.metal.clear_cache()

    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self.ensure_initialized()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            generate_audio(
                text=text,
                speed=1.0,
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
                verbose=is_debug())

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