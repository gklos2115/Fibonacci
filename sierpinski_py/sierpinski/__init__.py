"""Trójkąt Sierpińskiego w odcieniach fioletu.

Przykład:
    >>> from sierpinski import RenderConfig, render, save_png
    >>> result = render(RenderConfig(iterations=100))
    >>> save_png(result.canvas, "sierpinski_n100.png")
"""
from .color import DepthPalette, hsl_to_rgb
from .config import RenderConfig
from .fractal import RenderResult, effective_depth, render
from .png import encode_png, save_png
from .raster import Canvas
from .supersample import SUPPORTED_FACTORS, box_filter_row

__all__ = [
    "SUPPORTED_FACTORS",
    "box_filter_row",
    "Canvas",
    "DepthPalette",
    "RenderConfig",
    "RenderResult",
    "effective_depth",
    "encode_png",
    "hsl_to_rgb",
    "render",
    "save_png",
]
__version__ = "1.0.0"
