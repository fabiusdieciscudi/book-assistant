"""Builds an ID3v2.3 tag with chapters, following the "ID3v2 Chapter Frame Addendum" (CHAP and CTOC frames).

The tag is meant to be prepended to an MP3 stream that has no ID3v2 tag of its own.
"""
import struct


def chapters_tag(chapters: list[tuple[float, float, str]], toc_title: str = "") -> bytes:
    """Returns an ID3v2.3 tag with one CHAP frame per chapter and a top-level, ordered CTOC listing them.

    :param chapters:                the chapters, as (start seconds, end seconds, title), in order
    :param toc_title:               the title of the table of contents (optional)
    :return:                        the tag, ready to be prepended to the MP3 data
    """
    ids = [f"ch{i}" for i in range(len(chapters))]
    frames = [_chap(element_id, start, end, title) for element_id, (start, end, title) in zip(ids, chapters)]
    frames.append(_ctoc("toc", ids, toc_title))
    body = b"".join(frames)
    return b"ID3\x03\x00\x00" + _syncsafe(len(body)) + body


def _frame(frame_id: str, body: bytes) -> bytes:
    return frame_id.encode("ascii") + struct.pack(">I", len(body)) + b"\x00\x00" + body


def _text_frame(frame_id: str, text: str) -> bytes:
    return _frame(frame_id, b"\x01" + text.encode("utf-16"))      # encoding 1: UTF-16 with BOM


def _chap(element_id: str, start: float, end: float, title: str) -> bytes:
    body = (element_id.encode("ascii") + b"\x00"
            + struct.pack(">IIII", round(start * 1000), round(end * 1000), 0xFFFFFFFF, 0xFFFFFFFF)
            + _text_frame("TIT2", title))
    return _frame("CHAP", body)


def _ctoc(element_id: str, children: list[str], title: str) -> bytes:
    if len(children) > 255:
        raise ValueError(f"Too many chapters: {len(children)} (ID3 allows at most 255 per table of contents)")
    body = (element_id.encode("ascii") + b"\x00"
            + bytes([0x03, len(children)])                          # top-level, ordered
            + b"".join(child.encode("ascii") + b"\x00" for child in children)
            + (_text_frame("TIT2", title) if title else b""))
    return _frame("CTOC", body)


def _syncsafe(n: int) -> bytes:
    if n >= 1 << 28:
        raise ValueError("ID3 tag too large")
    return bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])
