"""CLI: python -m sierpinski [-n 100] [--width 4096] [-o plik.png]"""
from __future__ import annotations

import argparse
import sys
import time

from .config import RenderConfig
from .fractal import render
from .png import save_png
from .supersample import SUPPORTED_FACTORS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m sierpinski",
        description="Rysuje trójkąt Sierpińskiego w odcieniach fioletu i zapisuje PNG.",
    )
    p.add_argument("-n", "--iterations", type=int, default=100, help="liczba iteracji (domyślnie 100)")
    p.add_argument("--width", type=int, default=4096, help="szerokość obrazu w px (domyślnie 4096)")
    p.add_argument("--margin", type=int, default=68, help="margines w px (domyślnie 68)")
    p.add_argument("--min-px", type=float, default=1.0, help="najmniejszy dzielony bok w px (domyślnie 1)")
    p.add_argument("-s", "--supersample", type=int, choices=SUPPORTED_FACTORS, default=1,
                   help="antyaliasing: próbek na piksel w każdej osi (1 = wyłączony)")
    p.add_argument("-o", "--output", default="sierpinski_n100.png", help="ścieżka pliku PNG")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = RenderConfig(
            iterations=args.iterations,
            width=args.width,
            margin=args.margin,
            min_px=args.min_px,
            supersample=args.supersample,
        )
    except ValueError as exc:
        print(f"błąd: {exc}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    result = render(cfg)
    path = save_png(result.canvas, args.output)
    elapsed = time.perf_counter() - started

    print(f"n = {result.iterations}, narysowane poziomy: {result.effective_depth}, "
          f"wgłębień: {result.holes}, {cfg.width}x{cfg.height} px, "
          f"antyaliasing {cfg.supersample}x{cfg.supersample}, {elapsed:.2f} s")
    if result.truncated:
        unit = "px" if cfg.supersample == 1 else "próbki"
        print(f"uwaga: poziomy {result.effective_depth + 1}..{result.iterations} są mniejsze "
              f"niż {cfg.min_px} {unit}, więc pominięto je bez zmiany obrazu")
    print(f"zapisano: {path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
