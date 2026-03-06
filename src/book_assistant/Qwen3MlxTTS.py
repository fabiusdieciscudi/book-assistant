#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import os
import platform
import tempfile
import numpy as np
from pathlib import Path
from mlx_audio.tts.utils import load_model
from mlx_audio.tts.generate import generate_audio
from AbstractTTS import AbstractTTS
from Commons import debug, is_debug
import soundfile as sf
from huggingface_hub import snapshot_download
import pickle
import torch
from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel

CLONE_PROMPT = 'clone'

_BASE_MODEL_MLX = {
    'Lite': 'mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit',
    'Pro': 'mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit'}

_CUSTOM_VOICE_MODEL_MLX = {
    'Lite': 'mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit',
    'Pro': 'mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit'}

_BASE_MODEL_PT = {
    'Lite': 'Qwen/Qwen3-TTS-12Hz-0.6B-Base',
    'Pro':  'Qwen/Qwen3-TTS-12Hz-1.7B-Base'}

_CUSTOM_VOICE_MODEL_PT = {
    'Lite': 'Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice',
    'Pro':  'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'}

_TYPE_PT = {
    'Lite': torch.float32,
    'Pro':  torch.float16}

_VOICE_NAMES = ['', 'aiden', 'dylan', 'eric', 'ono_anna', 'ryan', 'serena', 'sohee', 'uncle_fu', 'vivian']
_SAMPLE_RATE = 24000

class Qwen3MlxTTS(AbstractTTS):
    def __init__(self, voice_name: str, language: str, model_size: str = "Pro", ref_text: str = None):
        super().__init__("Qwen3", voice_name, language, _SAMPLE_RATE, max_words=250)
        self._mlx = platform.system() == "Darwin" and platform.machine() == "arm64"
        self._voice_name = voice_name
        self._model_size = model_size

        if self._mlx:
            if voice_name == CLONE_PROMPT or voice_name.endswith(".mp3") or voice_name.endswith(".wav"):
                self._model_name = _BASE_MODEL_MLX[model_size]
                self._voice_name = None
                self._ref_audio = voice_name
                self._ref_text = ref_text
            else:
                self._model_name = _CUSTOM_VOICE_MODEL_MLX[model_size]
                self._ref_audio = None
                self._ref_text = None
                if self._voice_name not in _VOICE_NAMES:
                    raise ValueError(f"Unsupported voice: {voice_name} not in {_VOICE_NAMES}")
        else:
            if voice_name == CLONE_PROMPT or voice_name.endswith(".pkl"):
                self._model_name = _BASE_MODEL_PT[model_size]

                if voice_name != CLONE_PROMPT:
                    with open(voice_name, "rb") as f:
                        self._voice_clone_prompt = pickle.load(f)
            else:
                self._model_name = _CUSTOM_VOICE_MODEL_PT[model_size]
                self._voice_clone_prompt = None
                if not self._voice_name in _VOICE_NAMES:
                    raise ValueError(f"Unsupported voice: {voice_name} is not in {_VOICE_NAMES}")

    def _deferred_init(self):
        if self._mlx:
            debug(f"Loading Qwen3-MLX {self._voice_name} ({self._model_size}) from '{self._model_name}'")
            try:
                self._model = load_model(Path(self._model_name))
                debug("MLX model loaded OK")
            except Exception as e:
                debug(f"Load failed: {e}")
                debug("Trying to force download or check path...")
                local_path = snapshot_download(repo_id=self._model_name, allow_patterns=["*.safetensors", "config.json", "*.json"])
                self._model = load_model(Path(local_path))

            if hasattr(self._model, 'post_load_hook'):
                self._model.post_load_hook(self._model, Path(self._model_name))
                debug("post_load_hook called – tokenizer and components initialized")
            else:
                debug("Warning: No post_load_hook found on model – may cause issues")
        else:
            self._model = Qwen3TTSModel.from_pretrained(
                self._model_name,
                device_map = self._device,
                dtype = _TYPE_PT[self._model_size],
                attn_implementation = "sdpa",  # obbligatorio su MPS (no flash_attention)
                local_files_only=True)

    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self._ensure_initialized()
        debug(f"generate_single_chunk('{text}', {instruct}, {self._voice_name}, {self._ref_audio}, {self._ref_text})")

        if self._mlx:
            gen_kwargs = {
                "language": self._language.upper(),
                # "instruct": instruct or None,
            }

            if not self._ref_audio:
                gen_kwargs["speaker"] = self._voice_name
            else:
                gen_kwargs["voice_prompt"] = self._ref_audio

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp_file:
                tmp_path = tmp_file.name

            try:
                generate_audio(
                    **gen_kwargs,
                    text=text,
                    speed=1.0,
                    model=self._model,
                    voice=self._voice_name,
                    ref_audio=self._ref_audio,
                    ref_text=self._ref_text,
                    lang_code=self._language,
                    instruct=instruct,
                    output_path=os.path.dirname(tmp_path),
                    file_prefix=os.path.basename(tmp_path).replace(".wav", ""),
                    audio_format="wav",
                    join_audio=True,
                    play=False,
                    verbose=is_debug())

                audio_np, sr = sf.read(tmp_path)

                if audio_np.ndim == 2:
                    audio_np = np.mean(audio_np, axis=1)  # stereo → mono
                return audio_np.astype(np.float32)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            if not self._voice_clone_prompt:
                wavs, sr = self._model.generate_custom_voice(text=text,
                                                             language=self._language,
                                                             speaker=self._voice_name.lower(),
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

    def clone_voice(self, audio: str, text: str, pkl_file: str):
        if not self._mlx:
            self._ensure_initialized()
        debug(f"clone_voice('{audio}', '{text}', '{pkl_file})")
        voice_prompt = self._model.create_voice_clone_prompt(ref_audio=audio, ref_text=text, x_vector_only_mode=False)
        with open(pkl_file, "wb") as f:
            pickle.dump(voice_prompt, f)
