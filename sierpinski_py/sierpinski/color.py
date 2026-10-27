"""Paleta fioletów zależna od głębokości wgłębienia."""
from __future__ import annotations

from .config import RenderConfig

RGB = tuple[int, int, int]


def hsl_to_rgb(h: float, s: float, l: float) -> RGB:
    """Konwersja HSL (h w stopniach, s i l w 0..1) na RGB 0..255."""
    h = h % 360.0
    c = (1.0 - abs(2.0 * l - 1.0)) * s
    hp = h / 60.0
    x = c * (1.0 - abs(hp % 2.0 - 1.0))
    if hp < 1:
        r, g, b = c, x, 0.0
    elif hp < 2:
        r, g, b = x, c, 0.0
    elif hp < 3:
        r, g, b = 0.0, c, x
    elif hp < 4:
        r, g, b = 0.0, x, c
    elif hp < 5:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    m = l - c / 2.0
    return tuple(min(255, max(0, round((v + m) * 255))) for v in (r, g, b))  # type: ignore[return-value]


class DepthPalette:
    """Kolor dla głębokości d = 0..max_depth.

    Jasność i odcień zmieniają się liniowo (proporcjonalnie) z głębokością:
    d = 0 to najciemniejszy fiolet (tło trójkąta), d = max_depth najjaśniejszy.
    Kolory są liczone raz i trzymane w tablicy.
    """

    def __init__(self, config: RenderConfig, max_depth: int) -> None:
        if max_depth < 0:
            raise ValueError("max_depth musi być >= 0")
        self.max_depth = max_depth
        self._colors: list[RGB] = [self._compute(config, d) for d in range(max_depth + 1)]

    def _compute(self, cfg: RenderConfig, d: int) -> RGB:
        t = d / self.max_depth if self.max_depth else 0.0
        hue = cfg.hue_start + (cfg.hue_end - cfg.hue_start) * t
        light = cfg.lightness_start + (cfg.lightness_end - cfg.lightness_start) * t
        return hsl_to_rgb(hue, cfg.saturation, light)

    def __call__(self, depth: int) -> RGB:
        return self._colors[min(max(depth, 0), self.max_depth)]

    def __len__(self) -> int:
        return len(self._colors)
