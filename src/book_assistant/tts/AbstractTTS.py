#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

import os
import numpy as np
import torch
from abc import ABC, abstractmethod
from pathlib import Path
from book_assistant.Commons import log, debug

device = ""

def _find_device() -> str:
    global device

    if not device:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        log(f"Selected device: {device.upper()}")

    return device


def _hf_cache_dir() -> Path:
    """Returns the HuggingFace hub cache root (~/.cache/huggingface/hub)."""
    return Path(os.environ.get("HF_HOME",
                               os.environ.get("HUGGINGFACE_HUB_CACHE",
                                              Path.home() / ".cache" / "huggingface" / "hub")))


def _hf_snapshot_path(repo_id: str, revision: str = "main") -> Path | None:
    """Returns the local snapshot path for *repo_id* if it already exists in the
    HF cache, or None if it has never been downloaded.

    Works for the standard layout created by ``snapshot_download()``:
        <cache_root>/models--<org>--<name>/snapshots/<commit-hash>/

    The ``refs/<revision>`` file maps a branch/tag name to a commit hash.
    """
    safe_name = "models--" + repo_id.replace("/", "--")
    repo_cache = _hf_cache_dir() / safe_name
    refs_file = repo_cache / "refs" / revision
    if refs_file.is_file():
        commit = refs_file.read_text().strip()
        snapshot = repo_cache / "snapshots" / commit
        if snapshot.is_dir():
            return snapshot
    return None


class AbstractTTS(ABC):
    def __init__(self, prefix: str, voice_name: str, language: str, sample_rate: int, max_words: int = 99999, pause_after_new_line: float = 0):
        self._prefix = prefix.strip()
        self._voice_name = voice_name.strip()
        self._language = language.strip()
        self._sample_rate = sample_rate
        self._max_words = max_words
        self._pause_after_new_line = pause_after_new_line
        self._device = _find_device()
        self._initialized = False


    def prefix(self) -> str:
        return self._prefix


    def max_words(self) -> int:
        return self._max_words


    def sample_rate(self) -> int:
        return self._sample_rate


    def pause_after_new_line(self) -> float:
        return self._pause_after_new_line


    def ensure_initialized(self):
        if not self._initialized:
            self._deferred_init()
            self._initialized = True


    def _deferred_init(self):
        pass


    def _local_path(self, name: str) -> str:
        return f"{os.path.expanduser('~')}/.local/share/{name}"


    def _ensure_hf_model(self,
                         repo_id: str,
                         local_dir: str | None = None,
                         allow_patterns: list[str] | None = None,
                         revision: str = "main") -> str:
        """Ensures the HuggingFace model *repo_id* is available locally.

        Resolution order
        ----------------
        1. If *local_dir* is given and contains at least one file, use it as-is.
        2. If the model is already present in the standard HF cache
           (``~/.cache/huggingface/hub/``), return that snapshot path.
        3. Otherwise download via ``snapshot_download()`` and return the path.

        :param repo_id:         HuggingFace repository id, e.g. ``"Qwen/Qwen3-TTS-12Hz-1.7B-Base"``.
        :param local_dir:       explicit local directory (used by Piper / CSMTTS).
                                When provided, the HF cache lookup is skipped.
        :param allow_patterns:  optional ``snapshot_download`` allow-patterns filter.
        :param revision:        git revision / branch (default ``"main"``).
        :return:                string path to the local model directory.
        """
        from huggingface_hub import snapshot_download  # lazy import

        # ── 1. explicit local_dir ──────────────────────────────────────────────
        if local_dir is not None:
            p = Path(local_dir)
            if p.is_dir() and any(p.iterdir()):
                debug(f"Model '{repo_id}' found at explicit path: {local_dir}")
                return local_dir
            debug(f"Model '{repo_id}' not found at explicit path ({local_dir}) - downloading...")
            kwargs = dict(repo_id=repo_id, local_dir=local_dir, revision=revision)
            if allow_patterns:
                kwargs["allow_patterns"] = allow_patterns
            snapshot_download(**kwargs)
            debug("Download completed")
            return local_dir

        # ── 2. standard HF cache ──────────────────────────────────────────────
        cached = _hf_snapshot_path(repo_id, revision)
        if cached is not None:
            debug(f"Model '{repo_id}' found in HF cache: {cached}")
            return str(cached)

        # ── 3. download ───────────────────────────────────────────────────────
        debug(f"Model '{repo_id}' not in cache - downloading...")
        kwargs = dict(repo_id=repo_id, revision=revision)
        if allow_patterns:
            kwargs["allow_patterns"] = allow_patterns
        path = snapshot_download(**kwargs)
        debug("Download completed")
        return path


    @abstractmethod
    def generate_single_chunk(self, text: str, instruct: str = "") -> np.ndarray:
        pass

    def close(self):
        pass