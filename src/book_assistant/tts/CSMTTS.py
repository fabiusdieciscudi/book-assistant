#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import os
from abc import abstractmethod
import torch
import numpy as np
from transformers import CsmForConditionalGeneration, AutoProcessor, logging
from huggingface_hub import snapshot_download
from .AbstractTTS import AbstractTTS
from book_assistant.Commons import debug

SAMPLE_RATE = 24000

class CSMTTS(AbstractTTS):

    def __init__(self, prefix: str, voice_name: str, language: str, model_repo: str, local_path: str, max_words: int = 99999):
        super().__init__(prefix, voice_name, language, SAMPLE_RATE, max_words=max_words)
        self._local_dir = self._local_path(local_path)
        self._model_repo = model_repo


    def _deferred_init(self):
        debug(f"Initializing {self._prefix} ...")
        logging.set_verbosity_error()   # FIXME: should be warning
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        self._ensure_model_files()
        debug("Loading processor...")
        self.processor = AutoProcessor.from_pretrained(self._local_dir, local_files_only=True)
        debug("Loading model...")
        self.model = CsmForConditionalGeneration.from_pretrained(self._local_dir, local_files_only=True).to(self._device)
        debug(f"Model successfully loaded on {self._device}")


    def _ensure_model_files(self):
        config_path = os.path.join(self._local_dir, "preprocessor_config.json")
        if not os.path.exists(config_path):
            debug(f"Model not found locally ({config_path}) - downloading...")
            snapshot_download(self._model_repo, local_dir=self._local_dir)
            debug("Download completed")


    @abstractmethod
    def _conversation(self, text: str, instruct: str):
        pass


    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self.ensure_initialized()
        debug(f"generate_single_chunk('{text}', '{instruct}'")
        if not text.strip():
            return np.array([], dtype=np.float32)

        inputs = self.processor.apply_chat_template(self._conversation(text, instruct), tokenize=True, return_dict=True).to(self._device)

        with torch.inference_mode():
            output = self.model.generate(**inputs, output_audio=True)

        # From model card: output[0] is the waveform tensor
        if isinstance(output, (list, tuple)):
            waveform_tensor = output[0]
        elif hasattr(output, "audio"):
            waveform_tensor = output.audio[0] if output.audio.dim() > 1 else output.audio
        else:
            waveform_tensor = output

        return waveform_tensor.cpu().numpy().flatten()
