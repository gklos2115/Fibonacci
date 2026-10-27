"""Minimalny koder PNG (RGB, 8 bit) oparty wyłącznie na bibliotece standardowej."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .raster import Canvas

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def encode_png(canvas: Canvas, compression: int = 9) -> bytes:
    """Zwraca zawartość pliku PNG dla podanego bufora."""
    if not 0 <= compression <= 9:
        raise ValueError("compression musi być w zakresie 0..9")
    ihdr = struct.pack(">IIBBBBB", canvas.width, canvas.height, 8, 2, 0, 0, 0)
    stride = canvas.stride
    view = memoryview(canvas.pixels)
    # Kompresja strumieniowa: każdy wiersz (poprzedzony bajtem filtra 0) trafia
    # prosto do kompresora, więc nie powstaje druga, nieskompresowana kopia obrazu.
    comp = zlib.compressobj(compression)
    filter_byte = b"\x00"
    parts = []
    for y in range(canvas.height):
        parts.append(comp.compress(filter_byte))
        parts.append(comp.compress(view[y * stride:(y + 1) * stride]))
    parts.append(comp.flush())
    return b"".join((
        PNG_SIGNATURE,
        _chunk(b"IHDR", ihdr),
        _chunk(b"IDAT", b"".join(parts)),
        _chunk(b"IEND", b""),
    ))


def save_png(canvas: Canvas, path: str | Path, compression: int = 9) -> Path:
    """Zapisuje bufor do pliku PNG i zwraca ścieżkę."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_png(canvas, compression))
    return path
