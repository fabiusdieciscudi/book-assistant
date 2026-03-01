#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

from CSMTTS import CSMTTS

MODEL_REPO = "cartesia/azzurra-voice"
MAX_WORDS = 25

class AzzurraVoiceTTS(CSMTTS):

    def __init__(self):
        super().__init__("AzzurraVoice", "Azzurra", "italian", MODEL_REPO, "azzurra-voice", max_words=MAX_WORDS)

    def _conversation(self, text: str, instruct: str):
        return [#{"role": "system", "content": instruct.strip()},
                {"role": "user", "content": [{"type": "text", "text": text.strip()}]}]