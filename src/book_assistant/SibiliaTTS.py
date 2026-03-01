#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

from CSMTTS import CSMTTS

MODEL_REPO = "DeepMount00/Sibilia-TTS"
MAX_WORDS = 60

class SibiliaTTS(CSMTTS):
    def __init__(self):
        super().__init__("Sibilia", "Sibilia", "italian", MODEL_REPO, "sibilia-tts", max_words=MAX_WORDS)


    def _conversation(self, text: str, instruct: str):
        return [{"role": "0", "content": [{"type": "text", "text": text.strip()}]}]