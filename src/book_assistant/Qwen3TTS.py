#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import pickle
import numpy as np
import torch
from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel
from AbstractTTS import AbstractTTS
from Commons import debug

CLONE_PROMPT = 'clone'

_SAMPLE_RATE = 24000
_VOICE_NAMES = ['', 'aiden', 'dylan', 'eric', 'ono_anna', 'ryan', 'serena', 'sohee', 'uncle_fu', 'vivian']

class Qwen3TTS(AbstractTTS):


    def __init__(self, voice_name: str, language: str):
        super().__init__("Qwen3", voice_name, language, _SAMPLE_RATE)
        self._voice_name = voice_name
        if voice_name == CLONE_PROMPT or voice_name.endswith(".pkl"):
            self._model_name = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

            if voice_name != CLONE_PROMPT:
                with open(voice_name, "rb") as f:
                    self._voice_clone_prompt = pickle.load(f)
        else:
            self._model_name = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
            self._voice_clone_prompt = None
            if not voice_name in _VOICE_NAMES:
                raise ValueError(f"Unsupported voice: {voice_name} is not in {_VOICE_NAMES}")


    def _deferred_init(self):
        debug(f"Initializing Qwen3 {self._voice_name} with '{self._model_name}')")
        self._model = Qwen3TTSModel.from_pretrained(
            self._model_name,
            device_map = self._device,
            dtype = torch.float16,
            attn_implementation = "sdpa",  # obbligatorio su MPS (no flash_attention)
            local_files_only=True)


    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self._ensure_initialized()
        debug(f"generate_single_chunk('{text}', '{instruct}')")

        if not self._voice_clone_prompt:
            wavs, sr = self._model.generate_custom_voice(text=text,
                                                         language=self._language,
                                                         speaker=self._voice_name,
                                                         instruct=instruct,
                                                         do_sample=False,          # Deterministic
                                                         top_p=1.0)                # Disable sampling
        else:
            wavs, sr = self._model.generate_voice_clone(text=text,
                                                        language=self._language,
                                                        voice_clone_prompt=self._voice_clone_prompt,
                                                        instruct=instruct,
                                                        temperature=0.65,
                                                        top_p=0.90,
                                                        speed=1.0)
        return np.asarray(wavs)
