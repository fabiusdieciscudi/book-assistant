#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import os
import numpy as np
import torch
from abc import ABC, abstractmethod
from Commons import log

device = ""

def _find_device() -> str:
    global device

    if not device:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        log(f"Selected device: {device.upper()}")

    return device

class AbstractTTS(ABC):
    def __init__(self, prefix: str, voice_name: str, language: str, sample_rate: int, max_words: int = 99999, pause_after_new_line: float = 0):
        self._prefix = prefix.strip()
        self._voice_name = voice_name.strip()
        self._language = language.strip()
        self._sample_rate = sample_rate
        self._max_words = max_words
        self._pause_after_new_line = pause_after_new_line
        self._device = _find_device()
        self.__initialized = False


    def prefix(self) -> str:
        return self._prefix


    def max_words(self) -> int:
        return self._max_words


    def sample_rate(self) -> int:
        return self._sample_rate


    def pause_after_new_line(self) -> float:
        return self._pause_after_new_line


    def _ensure_initialized(self):
        if not self.__initialized:
            self._deferred_init()
            self.__initialized = True


    def _deferred_init(self):
        pass


    def _local_path(self, name: str) -> str:
        return f"{os.path.expanduser('~')}/.local/share/{name}"


    @abstractmethod
    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        pass
