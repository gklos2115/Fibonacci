"""Prosty bufor RGB z wypełnianiem trójkątów metodą scanline."""
from __future__ import annotations

import math

from .color import RGB

Point = tuple[float, float]


class Canvas:
    """Bufor pikseli RGB (3 bajty na piksel, wiersze od góry)."""

    def __init__(self, width: int, height: int, background: RGB) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("wymiary muszą być dodatnie")
        self.width = width
        self.height = height
        self.stride = width * 3
        # bytearray * n tworzy jeden bufor (bytes * n, a potem bytearray(...),
        # chwilowo trzymałoby w pamięci dwie pełne kopie obrazu).
        self.pixels = bytearray(bytes(background)) * (width * height)
        # Wiersz wypełniony danym kolorem, tniemy z niego plastry -> szybkie
        # przypisanie całego odcinka zamiast pętli po pikselach.
        self._row_cache: dict[RGB, bytes] = {}

    def _row(self, rgb: RGB) -> bytes:
        row = self._row_cache.get(rgb)
        if row is None:
            row = bytes(rgb) * self.width
            self._row_cache[rgb] = row
        return row

    def get_pixel(self, x: int, y: int) -> RGB:
        i = y * self.stride + x * 3
        return self.pixels[i], self.pixels[i + 1], self.pixels[i + 2]

    def fill_triangle(self, a: Point, b: Point, c: Point, rgb: RGB) -> None:
        """Wypełnia trójkąt; piksel należy do trójkąta, gdy jego środek leży w środku.

        Krawędzie traktowane są jako przedziały półotwarte, więc sąsiednie
        trójkąty nie zachodzą na siebie ani nie zostawiają szczelin.
        """
        y_min = min(a[1], b[1], c[1])
        y_max = max(a[1], b[1], c[1])
        row_from = max(0, math.ceil(y_min - 0.5))
        row_to = min(self.height - 1, math.ceil(y_max - 0.5) - 1)
        if row_to < row_from:
            return

        edges = ((a, b), (b, c), (c, a))
        pattern = self._row(rgb)
        pixels = self.pixels
        stride = self.stride
        width = self.width

        for y in range(row_from, row_to + 1):
            py = y + 0.5
            x_left = math.inf
            x_right = -math.inf
            for p, q in edges:
                if (p[1] <= py < q[1]) or (q[1] <= py < p[1]):
                    x = p[0] + (py - p[1]) * (q[0] - p[0]) / (q[1] - p[1])
                    if x < x_left:
                        x_left = x
                    if x > x_right:
                        x_right = x
            if x_right <= x_left:
                continue
            col_from = max(0, math.ceil(x_left - 0.5))
            col_to = min(width - 1, math.ceil(x_right - 0.5) - 1)
            if col_to < col_from:
                continue
            start = y * stride + col_from * 3
            length = (col_to - col_from + 1) * 3
            pixels[start:start + length] = pattern[:length]

    def fill_flat_triangle(self, apex: Point, base_y: float, base_left: float,
                           base_right: float, rgb: RGB) -> None:
        """Szybka ścieżka dla trójkąta z poziomą podstawą (wierzchołek nad nią lub pod nią).

        Daje piksele identyczne z ``fill_triangle`` (ta sama reguła środka piksela),
        ale bez szukania przecięć z 3 krawędziami w każdym wierszu: lewa i prawa
        krawędź są znane z góry, więc x liczymy jednym mnożeniem.
        """
        ax, ay = apex
        dy = base_y - ay
        if dy == 0 or base_right <= base_left:
            return
        row_from = max(0, math.ceil(min(ay, base_y) - 0.5))
        row_to = min(self.height - 1, math.ceil(max(ay, base_y) - 0.5) - 1)
        if row_to < row_from:
            return

        slope_l = (base_left - ax) / dy
        slope_r = (base_right - ax) / dy
        pattern = self._row(rgb)
        pixels = self.pixels
        stride = self.stride
        last_col = self.width - 1
        ceil = math.ceil

        for y in range(row_from, row_to + 1):
            t = y + 0.5 - ay
            col_from = ceil(ax + t * slope_l - 0.5)
            col_to = ceil(ax + t * slope_r - 0.5) - 1
            if col_from < 0:
                col_from = 0
            if col_to > last_col:
                col_to = last_col
            if col_to < col_from:
                continue
            start = y * stride + col_from * 3
            length = (col_to - col_from + 1) * 3
            pixels[start:start + length] = pattern[:length]
