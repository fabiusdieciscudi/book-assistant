#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import pickle
import numpy as np
from book_assistant.Commons import debug
from .Qwen3TTSbase import _Qwen3TTSBase, Qwen3Params, CLONE_PROMPT, DESIGN_PROMPT, \
    _BASE_MODEL_PT, _CUSTOM_VOICE_MODEL_PT, _VOICE_DESIGN_MODEL_PT, _VOICE_NAMES

class Qwen3TTSpt(_Qwen3TTSBase):

    def __init__(self, voice_name: str, language: str, model_size: str,
                 ref_text: str = None, params: Qwen3Params = None):
        super().__init__(voice_name, language, model_size, params)
        self._voice_clone_prompt = None
        self._is_voice_design = (voice_name == DESIGN_PROMPT)

        if self._is_voice_design:
            self._model_name = _VOICE_DESIGN_MODEL_PT[model_size]
        elif voice_name == CLONE_PROMPT or voice_name.endswith(".pkl"):
            self._model_name = _BASE_MODEL_PT[model_size]
            if voice_name.endswith(".pkl"):
                with open(voice_name, "rb") as f:
                    self._voice_clone_prompt = pickle.load(f)
        else:
            if voice_name not in _VOICE_NAMES:
                raise ValueError(f"Unsupported voice: {voice_name}")
            self._model_name = _CUSTOM_VOICE_MODEL_PT[model_size]

    def _deferred_init(self):
        import torch
        from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel

        _TYPE_PT = {'Lite': torch.float32, 'Pro': torch.float16}
        debug(f"Loading Qwen3-PT ({self._model_size}) from '{self._model_name}'")
        local_path = self._ensure_hf_model(repo_id=self._model_name)
        self._model = Qwen3TTSModel.from_pretrained(
            local_path,
            device_map=self._device,
            dtype=_TYPE_PT[self._model_size],
            attn_implementation="sdpa",
            local_files_only=True)

    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self.ensure_initialized()

        p = self._params
        do_sample = p.do_sample()
        talker_kw    = p.talker_kwargs()
        subtalker_kw = p.subtalker_kwargs()

        if self._is_voice_design:
            wavs, _ = self._model.generate_voice_design(
                text=text, language=self._language,
                instruct=instruct,
                do_sample=do_sample,
                **talker_kw,
                **subtalker_kw)
        elif self._voice_clone_prompt is None:
            wavs, _ = self._model.generate_custom_voice(
                text=text, language=self._language,
                speaker=self._voice_name.lower(),
                instruct=instruct,
                do_sample=do_sample,
                **talker_kw,
                **subtalker_kw)
        else:
            wavs, _ = self._model.generate_voice_clone(
                text=text, language=self._language,
                voice_clone_prompt=self._voice_clone_prompt,
                instruct=instruct,
                do_sample=do_sample,
                **talker_kw,
                **subtalker_kw)
        return np.asarray(wavs)

    def clone_voice(self, audio: str, text: str, pkl_file: str):
        self.ensure_initialized()
        debug(f"clone_voice('{audio}', '{text}', '{pkl_file}')")
        prompt = self._model.create_voice_clone_prompt(
            ref_audio=audio, ref_text=text, x_vector_only_mode=False)
        with open(pkl_file, "wb") as f:
            pickle.dump(prompt, f)