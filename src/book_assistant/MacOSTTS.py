#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import numpy as np
import subprocess
import tempfile
import os
import soundfile as sf
from AbstractTTS import AbstractTTS
from Commons import debug

SAMPLE_RATE = 22050

class MacOSTTS(AbstractTTS):

    def __init__(self, voice_name: str, language: str):
        super().__init__("MacOS", voice_name, language, SAMPLE_RATE, pause_after_new_line=0.3)
        self._validate_voice()


    def _validate_voice(self):
        pass
        # try:
        #     result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, check=True)
        #     voices = [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
        #     if self.voice not in voices:
        #         raise ValueError(f"Voice '{self.voice}' not found. Available voices: {', '.join(voices[:10])}")
        # except subprocess.CalledProcessError as e:
        #     raise RuntimeError(f"Couldn't verify available voices: {e}")


    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self._ensure_initialized()
        debug(f"generate_single_chunk('{text}', '{instruct}'")

        if not text.strip():
            return np.array([], dtype=np.float32)

        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            args = ["say", "-v", self._voice_name, "-o", tmp_path, text] if self._voice_name else ["say", "-o", tmp_path, text]
            subprocess.run(args, check=True, capture_output=True, text=True)
            data, sr = sf.read(tmp_path, dtype="float32")

            if len(data.shape) > 1 and data.shape[1] > 1:
                data = np.mean(data, axis=1)

            return data.flatten()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"While running 'say': {e.stderr or str(e)}")
        except Exception as e:
            raise RuntimeError(f"While reading the temporary file: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
