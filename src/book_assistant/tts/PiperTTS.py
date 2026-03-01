#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

from pathlib import Path
import numpy as np
from huggingface_hub import snapshot_download
from piper.voice import PiperVoice
from .AbstractTTS import AbstractTTS
from book_assistant.Commons import log, debug

class PiperTTS(AbstractTTS):

    def __init__(self, voice_name: str, language: str, model_repo: str, path: str, sample_rate: int, revision: str = "main"):
        super().__init__("Piper", voice_name, language, sample_rate)
        self._model_repo = model_repo
        self._path = path
        self._revision = revision
        self._local_dir = self._local_path("piper/voices")


    def _deferred_init(self):
        log(f"Initializing PiperVoice {self._voice_name}...")
        self._ensure_model_files()
        self._piper_voice = PiperVoice.load(f"{self._local_dir}/{self._model_repo}/{self._path}/{self._voice_name}.onnx")


    def _ensure_model_files(self):
        onnx_filename = f"{self._voice_name}.onnx"
        onnx = Path(self._local_dir) / self._model_repo / self._path / onnx_filename
        onnx_json = onnx.with_suffix(".onnx.json")
        json = onnx.with_suffix(".json")
        debug(f"Checking {onnx}")

        if not onnx.is_file() or not onnx_json.is_file():
            debug(f"File {onnx} or {onnx_json} not found")
            allow_patterns = [f"{self._path}/{onnx_filename}", f"{self._path}/{self._voice_name}.*json"]
            debug(f"Creating {self._local_dir}")
            Path(self._local_dir).mkdir(parents=True, exist_ok=True)
            debug(f"Loading files {allow_patterns} ...")
            snapshot_download(
                repo_id=self._model_repo,
                allow_patterns=allow_patterns,
                local_dir=f"{self._local_dir}/{self._model_repo}",
                revision=self._revision)
            debug(f"{onnx_filename} downloaded")

        if not onnx_json.exists() and json.exists():
            debug(f"Linking {onnx_json} to {json}...")
            onnx_json.symlink_to(json)


    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self.ensure_initialized()
        if not text.strip():
            return np.array([], dtype=np.float32)
        float_arrays = []
        for chunk in self._piper_voice.synthesize(text):
            float_array = chunk.audio_float_array
            if float_array.size > 0:
                float_arrays.append(float_array)

        if not float_arrays:
            return np.array([], dtype=np.float32)

        return np.concatenate(float_arrays)
