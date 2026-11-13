#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import os
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path
from book_assistant.Commons import debug, is_debug, log, warning
from .Qwen3TTSbase import _Qwen3TTSBase, _SharedModel, Qwen3Params, CLONE_PROMPT, DESIGN_PROMPT, _VOICE_NAMES, \
    _BASE_MODEL_MLX, _CUSTOM_VOICE_MODEL_MLX, _VOICE_DESIGN_MODEL_MLX

_FRAMES_PER_SECOND = 12.5      # Qwen3-TTS codec: one token per 80 ms of audio


class Qwen3TTSmlx(_Qwen3TTSBase):

    def __init__(self, voice_name: str, language: str, model_size: str,
                 ref_text: str = None, params: Qwen3Params = None):
        super().__init__(voice_name, language, model_size, params)

        self._is_voice_design = (voice_name == DESIGN_PROMPT)
        is_clone = (voice_name == CLONE_PROMPT or
                    voice_name.lower().endswith((".mp3", ".wav", ".flac", ".m4a", ".mp4", ".aac")))

        if self._is_voice_design:
            self._model_name  = _VOICE_DESIGN_MODEL_MLX[model_size]
            self._voice_name  = None
            self._ref_audio   = None
            self._ref_text    = None
        elif is_clone:
            self._model_name  = _BASE_MODEL_MLX[model_size]
            self._voice_name  = None
            self._ref_audio   = voice_name
            self._ref_text    = ref_text
        else:
            if voice_name not in _VOICE_NAMES:
                raise ValueError(f"Unsupported voice: {voice_name}")
            self._model_name  = _CUSTOM_VOICE_MODEL_MLX[model_size]
            self._voice_name  = voice_name
            self._ref_audio   = None
            self._ref_text    = None

    def _deferred_init(self):
        from mlx_audio.tts.utils import load_model
        import mlx.core as mx
        from transformers import logging as hf_logging, AutoTokenizer

        def load() -> _SharedModel:
            local_path = self._ensure_hf_model(
                repo_id=self._model_name,
                allow_patterns=["*.safetensors", "config.json", "*.json", "*.txt", "*.model"])
            # mlx_audio calls transformers internally and triggers two spurious warnings:
            #   1. "model of type qwen3_tts to instantiate a model of type" — the custom
            #      Qwen3TTSModel type isn't registered in the transformers hub, but loads fine.
            #   2. "incorrect regex pattern … fix_mistral_regex=True" — the tokenizer carries
            #      a Mistral-inherited lookahead regex; harmless for TTS inference.
            # Both are WARNING-level noise; suppress them for the duration of the load.
            prev_verbosity = hf_logging.get_verbosity()
            hf_logging.set_verbosity_error()
            try:
                return _SharedModel(load_model(Path(local_path)),
                                    AutoTokenizer.from_pretrained(local_path, local_files_only=True))
            finally:
                hf_logging.set_verbosity(prev_verbosity)

        shared = self._use_shared_model(("mlx", self._model_name),
                                        f"Qwen3-MLX ({self._model_size}) from '{self._model_name}'", load)
        self._tokenizer = shared.tokenizer

    def _extra_close(self):
        import mlx.core as mx
        mx.metal.clear_cache()

    def samples(self) -> bool:
        """mlx-audio samples by default (temperature 0.9 from the generation_config.json of the model)."""
        return self.params().temperature != 0

    def reference_audio(self) -> tuple[np.ndarray, int] | None:
        if self._ref_audio is None:
            return None
        from mlx_audio.utils import load_audio
        return np.asarray(load_audio(self._ref_audio, sample_rate=24000), dtype=np.float32), 24000

    def speaker_embedding(self, audio: np.ndarray, sample_rate: int) -> np.ndarray | None:
        """Uses the speaker encoder of the Base model (the one cloning voices), which works at 24 kHz."""
        self.ensure_initialized()
        if getattr(self._model, "speaker_encoder", None) is None:
            return None
        import mlx.core as mx
        if sample_rate != 24000:
            import librosa
            audio = librosa.resample(y=audio, orig_sr=sample_rate, target_sr=24000, res_type="soxr_hq")
        embedding = self._model.extract_speaker_embedding(mx.array(audio.astype(np.float32)), sr=24000)
        result = np.asarray(embedding, dtype=np.float32).reshape(-1)
        del embedding
        mx.clear_cache()            # MLX keeps the freed buffers, of a different size for each segment: release them
        return result

    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        self.ensure_initialized()
        text += f" {self.end_mark}" if self.end_mark else ""

        if self._is_voice_design:
            # Call the model's own method directly rather than the generic
            # generate_audio() wrapper: this is the officially documented
            # API for VoiceDesign and avoids relying on generate_audio's
            # (undocumented) mode-detection logic. 'instruct' here carries
            # the natural-language voice description, not a delivery style.
            p = self._params
            sampling = {}
            if p.temperature        is not None: sampling['temperature']        = p.temperature
            if p.top_p              is not None: sampling['top_p']              = p.top_p
            if p.top_k              is not None: sampling['top_k']              = p.top_k
            if p.repetition_penalty is not None: sampling['repetition_penalty'] = p.repetition_penalty
            if p.max_tokens         is not None: sampling['max_tokens']         = p.max_tokens
            debug(f"Qwen3-MLX design params: {sampling or 'library defaults'}")
            results = list(self._model.generate_voice_design(
                text=text, language=self._language, instruct=instruct, **sampling))
            self._check_token_limit(text, [r.token_count for r in results], p.max_tokens)
            return np.asarray(results[0].audio, dtype=np.float32)

        from mlx_audio.tts.generate import generate_audio

        p = self._params
        extra = {}
        if p.temperature        is not None: extra['temperature']        = p.temperature
        if p.top_p              is not None: extra['top_p']              = p.top_p
        if p.top_k              is not None: extra['top_k']              = p.top_k
        if p.repetition_penalty is not None: extra['repetition_penalty'] = p.repetition_penalty
        if p.max_tokens         is not None: extra['max_tokens']         = p.max_tokens

        mode = 'clone' if self._ref_audio else 'custom'
        debug(f"Qwen3-MLX {mode} params: {extra or 'library defaults'}")

        ids = self._tokenizer.encode(text)
        tokens = [self._tokenizer.decode([id]) for id in ids]
        debug(f"tokenize: {' | '.join(t for t in tokens)}")

        # generate_audio() doesn't return the results, so the model's generate() is wrapped for the duration
        # of the call to see how many tokens each segment took, and the limit it was given.
        token_counts: list[int] = []
        requested_limit: list[int | None] = []
        model_generate = self._model.generate

        def observed_generate(*args, **kwargs):
            requested_limit.append(kwargs.get("max_tokens"))
            for result in model_generate(*args, **kwargs):
                token_counts.append(result.token_count)
                yield result

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        self._model.generate = observed_generate
        try:
            generate_audio(
                text=text,
                # Speed is applied by TTSCommand after generation: the Qwen3 model ignores it
                # ("not directly supported yet" in mlx-audio), so passing it here would be a no-op
                # today and a double application if a future mlx-audio supported it.
                speed=1.0,
                model=self._model,
                voice=self._voice_name,
                ref_audio=self._ref_audio,
                ref_text=self._ref_text,
                lang_code=self._language,
                language=self._language.upper(),
                speaker=self._voice_name,
                voice_prompt=self._ref_audio,
                instruct=instruct,
                output_path=os.path.dirname(tmp_path),
                file_prefix=os.path.basename(tmp_path).replace(".wav", ""),
                audio_format="wav",
                join_audio=True,
                play=False,
                verbose=is_debug(),
                **extra)

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise RuntimeError(f"generate_audio silently failed: '{tmp_path}' empty or missing")
            self._check_token_limit(text, token_counts, requested_limit[0] if requested_limit else p.max_tokens)

            audio_np, _ = sf.read(tmp_path)
            if audio_np.ndim == 2:
                audio_np = np.mean(audio_np, axis=1)
            return audio_np.astype(np.float32)
        finally:
            del self._model.generate                    # back to the method of the class
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _check_token_limit(self, text: str, token_counts: list[int], requested: int | None) -> None:
        """Warns if a segment used all the tokens it was allowed: generation stopped there, not at the end
        of the text, so the audio is truncated."""
        resolve = getattr(self._model, "_resolve_generation_options", None)       # mlx-audio >= 0.6
        if resolve:
            limit = resolve(None, requested, None, None, None)["max_tokens"]
        else:                                                                   # older: the default of generate()
            limit = requested if requested is not None else 4096
        for count in token_counts:
            if count >= limit:
                excerpt = text if len(text) <= 80 else text[:40] + " … " + text[-40:]
                warning(f"Qwen3: the audio reached the limit of {limit} tokens ({limit / _FRAMES_PER_SECOND:.0f} sec)"
                        f" and is probably truncated; split the text or raise max_tokens: '{excerpt}'")

    def clone_voice(self, audio: str, text: str, pkl_file: str):
        # MLX doesn't support voice cloning via pkl
        raise NotImplementedError("Voice cloning to .pkl is only supported on the PyTorch backend")
