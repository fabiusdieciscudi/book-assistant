#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

"""
FixTransparencyCommand.py — Cleans up near-transparent alpha residue in PNG
illustrations that otherwise renders as a faint grey halo when the image is
composited over a non-black background (e.g. when included in a LaTeX PDF).

Some image editors (Affinity Photo among them) can export PNGs where pixels
that look fully transparent in the canvas actually carry a small non-zero
alpha value (e.g. 1-50 out of 255) over black RGB data. That residual alpha
is invisible against a typical dark editor background, but once composited
over a white/light page it blends in just enough black to produce a visible
grey tint across the whole "empty" area of the illustration.

This command thresholds the alpha channel: any alpha value below a given
cutoff is forced to 0 (fully transparent), removing the residual tint while
leaving clearly-opaque pixels untouched.
"""

from argparse import ArgumentParser
from logging import info
from pathlib import Path
import numpy as np
from PIL import Image
from book_assistant.CommandBase import CommandBase
from book_assistant.Commons import log, warning, debug, error

_FIX_TRANSPARENCY_COMMAND = "fix-transparency"
_DEFAULT_THRESHOLD = 30


class FixTransparencyCommand(CommandBase):

    def __init__(self):
        super().__init__(_FIX_TRANSPARENCY_COMMAND)
        self._fixed_count = 0
        self._unchanged_count = 0
        self._skipped_count = 0
        self._dry_run = False

    def process_args(self, parser: ArgumentParser) -> None:
        parser.add_argument("--threshold", type=int, default=_DEFAULT_THRESHOLD,
                            help=f"Alpha values (0-255) below this are forced to 0 (default: {_DEFAULT_THRESHOLD}).")
#        parser.add_argument("--output", default=None,
#                            help="Output file (default: overwrite the input file). Only valid when <path> is a single file.")

    def run(self, args) -> None:
        """Override CommandBase.run() to walk *.png files instead of *.txt,
        and to validate --output against single-file vs. folder input
        before any processing starts.

        :param args:    parsed command-line arguments
        """
        path = args.path
        resolved = Path(path).resolve()
        if not resolved.exists():
            error(f"Doesn't exist: {path}")
            return

        if args.output is not None and resolved.is_dir():
            error("--output cannot be used when <path> is a folder (it would overwrite a single file with results from many).")
            return

        self._dry_run = args.dry_run

        try:
            self._prepare()
            if resolved.is_file():
                self._run(args, resolved)
            elif resolved.is_dir():
                for png_path in sorted(resolved.rglob("*.png")):
                    self._run(args, png_path)
        finally:
            self._finish()

    def _run(self, args, path: Path) -> None:
        output_path = Path(args.output).resolve() if args.output else path
        self._fix_alpha(path, output_path, args.threshold, args.dry_run)

    def _finish(self) -> None:
        super()._finish()
        log(f"{'Would fix' if self._dry_run else 'Fixed'} {self._fixed_count} image(s), "
            f"{self._unchanged_count} already clean, skipped {self._skipped_count} (no alpha channel).")

    def _fix_alpha(self, input_path: Path, output_path: Path, threshold: int, dry_run: bool) -> None:
        """Threshold the alpha channel of a single PNG, forcing low residual
        values to 0 to remove grey-halo artefacts in transparent areas.

        :param input_path:      the PNG file to read
        :param output_path:     where to write the result (may equal input_path)
        :param threshold:       alpha values strictly below this become 0
        :param dry_run:         if True, report what would change without writing the file
        """
        log(f"{'Validating' if dry_run else 'Processing'}: {input_path}")

        image = Image.open(input_path)
        if image.mode != "RGBA":
            log(f"{input_path.name}: no alpha channel (mode={image.mode}) - skipped.")
            self._skipped_count += 1
            return

        pixels = np.array(image)
        alpha = pixels[:, :, 3]

        before = int((alpha == 0).sum())
        alpha[alpha < threshold] = 0
        after = int((alpha == 0).sum())
        pixels[:, :, 3] = alpha

        total = alpha.size
        log(f"{input_path.name}: fully-transparent pixels {before} ({100 * before / total:.1f}%) -> {after} ({100 * after / total:.1f}%), threshold={threshold}")

        if before == after:
            log(f"Already clean, no changes needed: {input_path.name}")
            self._unchanged_count += 1
            return
        elif dry_run:
            log(f"Would {'overwrite' if output_path == input_path else f'write to {output_path}'}: {input_path.name}")
        else:
            Image.fromarray(pixels, mode="RGBA").save(output_path)
            log(f"{'Overwritten' if output_path == input_path else f'Written to {output_path}'}: {input_path.name}")
        self._fixed_count += 1
