#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import os
from abc import abstractmethod
import numpy as np
from .AbstractTTS import AbstractTTS
from book_assistant.Commons import debug

SAMPLE_RATE = 24000

class CSMTTS(AbstractTTS):

    def __init__(self, prefix: str, voice_name: str, language: str, model_repo: str, local_path: str, max_words: int = 99999):
        super().__init__(prefix, voice_name, language, SAMPLE_RATE, max_words=max_words)
        self._local_dir = self._local_path(local_path)
        self._model_repo = model_repo


    def _deferred_init(self):
        import torch
        from transformers import CsmForConditionalGeneration, AutoProcessor, logging

        debug(f"Initializing {self._prefix} ...")
        logging.set_verbosity_error()   # FIXME: should be warning
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        local_dir = self._ensure_hf_model(self._model_repo, local_dir=self._local_dir)
        debug("Loading processor...")
        self.processor = AutoProcessor.from_pretrained(local_dir, local_files_only=True)
        debug("Loading model...")
        self.model = CsmForConditionalGeneration.from_pretrained(local_dir, local_files_only=True).to(self._device)
        debug(f"Model successfully loaded on {self._device}")


    @abstractmethod
    def _conversation(self, text: str, instruct: str):
        pass


    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        import torch
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