"""Generowanie trójkąta Sierpińskiego z kolorowaniem wgłębień wg głębokości."""
from __future__ import annotations

from dataclasses import dataclass

from .color import RGB, DepthPalette
from .config import SQRT3_2, RenderConfig
from .raster import Canvas
from .supersample import box_filter_row

# Wysokość pasa (w pikselach wyjściowych) przy supersamplingu. Pas w wysokiej
# rozdzielczości ma width·k × BAND_ROWS·k próbek, więc pamięć nie rośnie z k².
BAND_ROWS = 128


@dataclass(frozen=True)
class RenderResult:
    canvas: Canvas
    iterations: int        # zadane n
    effective_depth: int   # liczba poziomów faktycznie narysowanych
    holes: int             # liczba narysowanych wgłębień
    supersample: int = 1   # liczba próbek na piksel w każdej osi

    @property
    def truncated(self) -> bool:
        """True, gdy część iteracji pominięto, bo trójkąty byłyby mniejsze od min_px."""
        return self.effective_depth < self.iterations


def effective_depth(side: float, iterations: int, min_px: float) -> int:
    """Ile poziomów wgłębień zostanie narysowanych.

    Poziom d+1 powstaje z trójkąta o boku side / 2**d, o ile ten bok >= min_px.
    Liczone pętlą (nie log2), żeby wynik był identyczny z warunkiem w ``render``.
    """
    depth = 0
    while depth < iterations and side >= min_px:
        side /= 2.0
        depth += 1
    return depth


def _draw_band(canvas: Canvas, top_x: float, top_y: float, side: float, offset_y: int,
               colors: list[RGB], iterations: int, min_px: float) -> None:
    """Rysuje fragment fraktala w pasie zaczynającym się na wierszu ``offset_y``.

    Wszystkie trójkąty do podziału są „pionowe” (wierzchołek u góry, pozioma
    podstawa), więc wystarczy trzymać wierzchołek (x, y) i bok s:
      lewy = (x - s/2, y + h), prawy = (x + s/2, y + h), h = s·√3/2.
    Wgłębienie to odwrócony trójkąt: wierzchołek (x, y + h), podstawa na y + h/2.
    Poddrzewa leżące w całości poza pasem są pomijane (dzieci mieszczą się
    w rodzicu). Przy offset_y = 0 i pasie równym obrazowi współrzędne
    są dokładnie takie, jak bez podziału na pasy.
    """
    band_top = offset_y
    band_bottom = offset_y + canvas.height
    tri_h = side * SQRT3_2
    canvas.fill_triangle((top_x, top_y - offset_y),
                         (top_x - side / 2.0, top_y + tri_h - offset_y),
                         (top_x + side / 2.0, top_y + tri_h - offset_y),
                         colors[0])

    fill = canvas.fill_flat_triangle
    # Na stos trafiają tylko trójkąty, które faktycznie zostaną podzielone
    # (warunek sprawdzany przed push), więc liście drzewa nie kosztują nic.
    stack: list[tuple[float, float, int, float]] = []
    if iterations > 0 and side >= min_px:
        stack.append((top_x, top_y, 0, side))
    pop, push = stack.pop, stack.append
    while stack:
        x, y, depth, s = pop()
        h = s * SQRT3_2
        if y >= band_bottom or y + h <= band_top:
            continue
        half = s / 2.0
        quarter = s / 4.0
        mid_y = y + h / 2.0
        nd = depth + 1
        fill((x, y + h - offset_y), mid_y - offset_y, x - quarter, x + quarter, colors[nd])
        if nd < iterations and half >= min_px:
            push((x, y, nd, half))
            push((x - quarter, mid_y, nd, half))
            push((x + quarter, mid_y, nd, half))


def render(config: RenderConfig | None = None) -> RenderResult:
    """Rysuje trójkąt Sierpińskiego i zwraca bufor ze statystykami.

    Algorytm (iteracyjny, z jawnym stosem, więc bez limitu rekurencji):
      1. cały trójkąt wypełniany jest kolorem głębokości 0,
      2. dla każdego trójkąta na stosie rysowany jest środkowy, odwrócony
         trójkąt (wgłębienie) w kolorze głębokości d+1,
      3. trzy narożne trójkąty trafiają na stos z głębokością d+1,
         o ile same będą jeszcze dzielone.
    Gałąź jest przycinana, gdy d >= n albo bok < min_px. Głębsze poziomy
    zmieściłyby się w jednej próbce, więc obraz jest identyczny z pełnym n.

    Przy ``supersample = k > 1`` obraz jest rysowany w rozdzielczości k razy
    większej, pasami po BAND_ROWS wierszy wyjściowych, a każdy piksel wyniku
    jest średnią bloku k×k próbek (antyaliasing krawędzi i najmniejszych wgłębień).
    """
    cfg = config or RenderConfig()
    k = cfg.supersample
    side = cfg.side * k
    depth_limit = effective_depth(side, cfg.iterations, cfg.min_px)
    # Skala jasności liczona jest w pikselach wyjściowych, a nie w próbkach:
    # dzięki temu antyaliasing tylko wygładza obraz i nie zmienia kolorów wgłębień.
    # Poziomy mniejsze od piksela (widoczne tylko przy k > 1) dostają najjaśniejszy kolor.
    palette = DepthPalette(cfg, effective_depth(cfg.side, cfg.iterations, cfg.min_px))
    colors = [palette(d) for d in range(depth_limit + 1)]
    # Przycinanie zależy tylko od głębokości, więc drzewo jest pełne:
    # 1 + 3 + 9 + ... + 3^(D-1) = (3^D - 1) / 2 wgłębień.
    holes = (3 ** depth_limit - 1) // 2

    top_x = (cfg.margin + cfg.side / 2.0) * k
    top_y = float(cfg.margin * k)
    draw = (top_x, top_y, side)

    if k == 1:
        canvas = Canvas(cfg.width, cfg.height, cfg.background)
        _draw_band(canvas, *draw, 0, colors, cfg.iterations, cfg.min_px)
        return RenderResult(canvas, cfg.iterations, depth_limit, holes, k)

    out = Canvas(cfg.width, cfg.height, cfg.background)
    hi_stride = cfg.width * k * 3
    for out_y0 in range(0, cfg.height, BAND_ROWS):
        rows = min(BAND_ROWS, cfg.height - out_y0)
        band = Canvas(cfg.width * k, rows * k, cfg.background)
        _draw_band(band, *draw, out_y0 * k, colors, cfg.iterations, cfg.min_px)
        view = memoryview(band.pixels)
        for r in range(rows):
            block = [view[(r * k + i) * hi_stride:(r * k + i + 1) * hi_stride] for i in range(k)]
            start = (out_y0 + r) * out.stride
            out.pixels[start:start + out.stride] = box_filter_row(block, k)
        # Zwolnij pas przed utworzeniem następnego (inaczej w pamięci byłyby dwa).
        del block, view, band
    return RenderResult(out, cfg.iterations, depth_limit, holes, k)
