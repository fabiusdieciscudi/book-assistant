#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import pickle
import torch
import numpy as np
from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel
from book_assistant.Commons import debug
from .Qwen3TTSbase import _Qwen3TTSBase, CLONE_PROMPT, _BASE_MODEL_PT, _CUSTOM_VOICE_MODEL_PT, _VOICE_NAMES

_TYPE_PT = {'Lite': torch.float32, 'Pro': torch.float16}

class Qwen3TTSpt(_Qwen3TTSBase):

    def __init__(self, voice_name: str, language: str, model_size: str,
                 ref_text: str = None):
        super().__init__(voice_name, language, model_size)
        self._voice_clone_prompt = None

        if voice_name == CLONE_PROMPT or voice_name.endswith(".pkl"):
            self._model_name = _BASE_MODEL_PT[model_size]
            if voice_name.endswith(".pkl"):
                with open(voice_name, "rb") as f:
                    self._voice_clone_prompt = pickle.load(f)
        else:
            if voice_name not in _VOICE_NAMES:
                raise ValueError(f"Unsupported voice: {voice_name}")
            self._model_name = _CUSTOM_VOICE_MODEL_PT[model_size]

    def _deferred_init(self):
        debug(f"Loading Qwen3-PT ({self._model_size}) from '{self._model_name}'")
        self._model = Qwen3TTSModel.from_pretrained(
            self._model_name,
            device_map=self._device,
            dtype=_TYPE_PT[self._model_size],
            attn_implementation="sdpa",
            local_files_only=True)

    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self.ensure_initialized()
        if self._voice_clone_prompt is None:
            wavs, _ = self._model.generate_custom_voice(
                text=text, language=self._language,
                speaker=self._voice_name.lower(),
                instruct=instruct,
                do_sample=False, top_p=1.0)
        else:
            wavs, _ = self._model.generate_voice_clone(
                text=text, language=self._language,
                voice_clone_prompt=self._voice_clone_prompt,
                instruct=instruct,
                temperature=0.65, top_p=0.90, speed=1.0)
        return np.asarray(wavs)

    def clone_voice(self, audio: str, text: str, pkl_file: str):
        self.ensure_initialized()
        debug(f"clone_voice('{audio}', '{text}', '{pkl_file}')")
        prompt = self._model.create_voice_clone_prompt(
            ref_audio=audio, ref_text=text, x_vector_only_mode=False)
        with open(pkl_file, "wb") as f:
            pickle.dump(prompt, f)