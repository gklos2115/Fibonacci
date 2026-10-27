"""Konfiguracja renderowania trójkąta Sierpińskiego."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .supersample import SUPPORTED_FACTORS

SQRT3_2 = math.sqrt(3) / 2


@dataclass(frozen=True)
class RenderConfig:
    """Parametry obrazu i palety.

    iterations   -- zadana liczba iteracji (n). Podział jest dodatkowo
                    przycinany, gdy bok trójkąta spada poniżej ``min_px``.
    width        -- szerokość obrazu w pikselach; wysokość liczona jest
                    automatycznie tak, by trójkąt równoboczny się zmieścił.
    margin       -- margines wokół trójkąta (px).
    min_px       -- najmniejszy bok trójkąta (w próbkach), który jeszcze dzielimy.
    supersample  -- antyaliasing: 1 (wyłączony), 2 lub 4 próbki na piksel
                    w każdej osi. Każdy piksel to średnia bloku k×k próbek.
    hue_start/end         -- zakres odcienia (stopnie HSL) od płytkich do głębokich wgłębień.
    lightness_start/end   -- zakres jasności (0..1), zmieniany liniowo z głębokością.
    saturation            -- stałe nasycenie (0..1).
    background            -- kolor tła RGB.
    """

    iterations: int = 100
    width: int = 4096
    margin: int = 68
    min_px: float = 1.0
    supersample: int = 1
    hue_start: float = 262.0
    hue_end: float = 292.0
    saturation: float = 0.70
    lightness_start: float = 0.15
    lightness_end: float = 0.85
    background: tuple[int, int, int] = (12, 8, 17)

    def __post_init__(self) -> None:
        if (not isinstance(self.iterations, int) or isinstance(self.iterations, bool)
                or self.iterations < 0):
            raise ValueError("iterations musi być nieujemną liczbą całkowitą")
        if self.width < 16:
            raise ValueError("width musi wynosić co najmniej 16 px")
        if self.margin < 0 or 2 * self.margin >= self.width:
            raise ValueError("margin musi być >= 0 i mniejszy niż połowa szerokości")
        if self.min_px <= 0:
            raise ValueError("min_px musi być dodatnie")
        if self.supersample not in SUPPORTED_FACTORS or isinstance(self.supersample, bool):
            raise ValueError(f"supersample musi być jednym z {SUPPORTED_FACTORS}")
        for name in ("saturation", "lightness_start", "lightness_end"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name} musi być w zakresie 0..1")
        if len(self.background) != 3 or not all(0 <= c <= 255 for c in self.background):
            raise ValueError("background musi być krotką RGB 0..255")

    @property
    def side(self) -> float:
        """Długość boku głównego trójkąta."""
        return float(self.width - 2 * self.margin)

    @property
    def height(self) -> int:
        """Wysokość obrazu dopasowana do trójkąta równobocznego."""
        return math.ceil(self.side * SQRT3_2) + 2 * self.margin
