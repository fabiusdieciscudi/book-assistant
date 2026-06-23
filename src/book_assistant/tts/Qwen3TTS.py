#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import platform

from .Qwen3TTSmlx import Qwen3TTSmlx
from .Qwen3TTSpt import Qwen3TTSpt
from .Qwen3TTSbase import Qwen3Params

def Qwen3TTS(voice_name: str, language: str, model_size: str = "Pro",
             ref_text: str = None, params: Qwen3Params = None):
    """Returns the right backend for the current platform."""
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return Qwen3TTSmlx(voice_name, language, model_size, ref_text, params)
    return Qwen3TTSpt(voice_name, language, model_size, ref_text, params)