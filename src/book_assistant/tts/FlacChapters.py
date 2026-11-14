#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

"""Adds chapters to a FLAC stream, as Vorbis comments following the "Chapter Extension" convention
(CHAPTER001=HH:MM:SS.mmm, CHAPTER001NAME=title).

ffmpeg reads them as chapters, so they are preserved when the file is converted, e.g. to MP3 with ID3 chapters.

Also adds the text of the lines, with their start times, as subtitles in the LRC format ([mm:ss.xx]text) in the LYRICS
Vorbis comment, the one used by the players that show synced lyrics.
"""
import struct

_STREAMINFO = 0
_VORBIS_COMMENT = 4
_LAST = 0x80


def with_chapters(flac: bytes, chapters: list[tuple[float, float, str]]) -> bytes:
    """Returns *flac* with the chapters added to its Vorbis comment block (created if missing).

    :param flac:                    the FLAC stream
    :param chapters:                the chapters, as (start seconds, end seconds, title), in order
    :return:                        the FLAC stream with the chapters
    """
    added = []
    for i, (start, _, title) in enumerate(chapters, 1):
        added.append(f"CHAPTER{i:03d}={_time(start)}".encode())
        added.append(f"CHAPTER{i:03d}NAME={title}".encode())
    return _with_comments(flac, b"CHAPTER", added)


def with_lyrics(flac: bytes, lines: list[tuple[float, float, str]]) -> bytes:
    """Returns *flac* with the lines, as LRC, in the LYRICS Vorbis comment (the block is created if missing).

    Each line is shown from its start until the next one; an empty line at the end of the last one clears it.

    :param flac:                    the FLAC stream
    :param lines:                   the lines, as (start seconds, end seconds, text), in order
    :return:                        the FLAC stream with the lines
    """
    lrc = [f"[{_lrc_time(start)}]{' '.join(text.split())}" for start, _, text in lines]
    if lines:
        lrc.append(f"[{_lrc_time(lines[-1][1])}]")
    return _with_comments(flac, b"LYRICS=", [("LYRICS=" + "\n".join(lrc)).encode()])


def _with_comments(flac: bytes, prefix: bytes, added: list[bytes]) -> bytes:
    """Returns *flac* with the Vorbis comments starting with *prefix* (case insensitive) replaced by *added*."""
    if flac[:4] != b"fLaC":
        raise ValueError("Not a FLAC stream")
    blocks, audio = _blocks(flac)
    vendor, comments = b"BookAssistant", []
    for kind, body in blocks:
        if kind == _VORBIS_COMMENT:
            vendor, comments = _parse_comments(body)
    comments = [c for c in comments if not c.upper().startswith(prefix)] + added
    comment_block = (_VORBIS_COMMENT, _comments_body(vendor, comments))
    others = [b for b in blocks if b[0] != _VORBIS_COMMENT]
    blocks = others[:1] + [comment_block] + others[1:]        # STREAMINFO must stay the first block
    out = [b"fLaC"]
    for i, (kind, body) in enumerate(blocks):
        out.append(bytes([(_LAST if i == len(blocks) - 1 else 0) | kind]) + len(body).to_bytes(3, "big") + body)
    return b"".join(out) + audio


def _blocks(flac: bytes) -> tuple[list[tuple[int, bytes]], bytes]:
    """Splits a FLAC stream into its metadata blocks (type, body) and the audio frames."""
    blocks, i = [], 4
    while True:
        header = flac[i]
        length = int.from_bytes(flac[i + 1:i + 4], "big")
        blocks.append((header & 0x7F, flac[i + 4:i + 4 + length]))
        i += 4 + length
        if header & _LAST:
            break
    if not blocks or blocks[0][0] != _STREAMINFO:
        raise ValueError("Invalid FLAC stream: STREAMINFO is not the first block")
    return blocks, flac[i:]


def _parse_comments(body: bytes) -> tuple[bytes, list[bytes]]:
    """Parses a Vorbis comment block (little-endian lengths) into the vendor string and the comments."""
    length = struct.unpack_from("<I", body, 0)[0]
    vendor, i = body[4:4 + length], 4 + length
    count = struct.unpack_from("<I", body, i)[0]
    i += 4
    comments = []
    for _ in range(count):
        length = struct.unpack_from("<I", body, i)[0]
        comments.append(body[i + 4:i + 4 + length])
        i += 4 + length
    return vendor, comments


def _comments_body(vendor: bytes, comments: list[bytes]) -> bytes:
    return (struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", len(comments))
            + b"".join(struct.pack("<I", len(c)) + c for c in comments))


def _lrc_time(seconds: float) -> str:
    """Formats a time as LRC: minutes (also beyond 59), seconds and hundredths."""
    hundredths = round(seconds * 100)
    return f"{hundredths // 6000:02d}:{hundredths // 100 % 60:02d}.{hundredths % 100:02d}"


def _time(seconds: float) -> str:
    millis = round(seconds * 1000)
    return f"{millis // 3_600_000:02d}:{millis // 60_000 % 60:02d}:{millis // 1000 % 60:02d}.{millis % 1000:03d}"
