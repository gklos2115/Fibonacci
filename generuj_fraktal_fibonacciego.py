"""Generate a Fibonacci square tiling with a blue-violet spiral."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
IMAGE_SIZE = 3000
MARGIN = 180
FIBONACCI_SIDES = (1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89)
BACKGROUND = (255, 255, 255)
OUTLINE = (65, 73, 112)
SQUARE_COLORS = (
    (229, 239, 252),
    (238, 232, 250),
    (216, 231, 250),
    (229, 220, 247),
)
SPIRAL_COLORS = (
    (45, 114, 204),
    (113, 75, 181),
    (57, 139, 218),
    (139, 91, 196),
)


def fibonacci_squares():
    squares = [(0, 0, FIBONACCI_SIDES[0])]
    for index, side in enumerate(FIBONACCI_SIDES[1:]):
        min_x = min(x for x, _, _ in squares)
        min_y = min(y for _, y, _ in squares)
        max_x = max(x + size for x, _, size in squares)
        max_y = max(y + size for _, y, size in squares)
        direction = index % 4
        if direction == 0:
            x, y = max_x, min_y
        elif direction == 1:
            x, y = min_x, min_y - side
        elif direction == 2:
            x, y = min_x - side, min_y
        else:
            x, y = min_x, max_y
        squares.append((x, y, side))
    return squares


def generate():
    squares = fibonacci_squares()
    min_x = min(x for x, _, _ in squares)
    min_y = min(y for _, y, _ in squares)
    max_x = max(x + side for x, _, side in squares)
    max_y = max(y + side for _, y, side in squares)
    scale = min(
        (IMAGE_SIZE - 2 * MARGIN) / (max_x - min_x),
        (IMAGE_SIZE - 2 * MARGIN) / (max_y - min_y),
    )
    pattern_width = (max_x - min_x) * scale
    pattern_height = (max_y - min_y) * scale
    left = (IMAGE_SIZE - pattern_width) / 2
    top = (IMAGE_SIZE - pattern_height) / 2
    line_width = max(3, round(scale * 0.045))
    arc_width = max(5, round(scale * 0.12))
    pixel_squares = []
    previous_exit = None
    previous_center = None

    image = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), BACKGROUND)
    draw = ImageDraw.Draw(image)
    for index, (x, y, side) in enumerate(squares):
        x0 = round(left + (x - min_x) * scale)
        y0 = round(top + (y - min_y) * scale)
        x1 = round(left + (x + side - min_x) * scale)
        y1 = round(top + (y + side - min_y) * scale)
        pixel_squares.append((x0, y0, x1, y1, index))
        draw.rectangle(
            (x0, y0, x1, y1),
            fill=SQUARE_COLORS[index % len(SQUARE_COLORS)],
        )

    for x0, y0, x1, y1, index in pixel_squares:
        draw.rectangle(
            (x0, y0, x1, y1),
            outline=OUTLINE,
            width=line_width,
        )
        corners = {
            "top_left": (x0, y0),
            "top_right": (x1, y0),
            "bottom_right": (x1, y1),
            "bottom_left": (x0, y1),
        }
        opposite = {
            "top_left": "bottom_right",
            "top_right": "bottom_left",
            "bottom_right": "top_left",
            "bottom_left": "top_right",
        }
        if previous_exit is None:
            entry_name = "top_left"
            center_name = "top_right"
        else:
            entry_name = next(
                name for name, point in corners.items() if point == previous_exit
            )
            exit_name = opposite[entry_name]
            centers = [
                name
                for name in corners
                if name not in (entry_name, exit_name)
            ]
            prev_radius = (
                previous_exit[0] - previous_center[0],
                previous_exit[1] - previous_center[1],
            )

            def tangent_alignment(name):
                radius = (
                    corners[entry_name][0] - corners[name][0],
                    corners[entry_name][1] - corners[name][1],
                )
                dot = prev_radius[0] * radius[0] + prev_radius[1] * radius[1]
                lengths = (
                    (prev_radius[0] ** 2 + prev_radius[1] ** 2)
                    * (radius[0] ** 2 + radius[1] ** 2)
                ) ** 0.5
                return abs(dot) / lengths

            center_name = max(centers, key=tangent_alignment)

        cx, cy = corners[center_name]
        exit_name = opposite[entry_name]
        previous_exit = corners[exit_name]
        previous_center = (cx, cy)
        arc_angles = {
            "top_left": (0, 90),
            "top_right": (90, 180),
            "bottom_right": (180, 270),
            "bottom_left": (270, 360),
        }
        start, end = arc_angles[center_name]
        side_px = min(x1 - x0, y1 - y0)
        draw.arc(
            (cx - side_px, cy - side_px, cx + side_px, cy + side_px),
            start=start,
            end=end,
            fill=SPIRAL_COLORS[index % len(SPIRAL_COLORS)],
            width=arc_width,
        )

    image.save(OUT / "fraktal_fibonacciego.png", dpi=(300, 300), optimize=True)
    return len(squares), FIBONACCI_SIDES


def write_description(count, sides):
    description = f"""FRAKTAL FIBONACCIEGO — KWADRATY I SPIRALA

Grafika przedstawia mozaikę złożoną z {count} kwadratów. Długości boków
odpowiadają kolejnym liczbom Fibonacciego:
{", ".join(map(str, sides))}.
Kwadraty są układane kolejno wokół poprzedniego wzoru, dzięki czemu
zachowane są ich proporcje i powstaje charakterystyczny spiralny układ.

W każdym kwadracie znajduje się ćwierćokrąg dopasowany do jego boku.
Połączone łuki tworzą spiralę Fibonacciego. Jasne niebieskie i fioletowe
wypełnienia, ciemne obrysy oraz nasycone łuki ułatwiają odczytanie
geometrycznej konstrukcji.

Tło jest białe. Obraz PNG ma rozdzielczość 3000 x 3000 pikseli i 300 dpi.

PLIKI
fraktal_fibonacciego.png — gotowa grafika.
fraktal_fibonacciego_opis.txt — opis obrazu.
generuj_fraktal_fibonacciego.py — skrypt źródłowy.
Uruchomienie: python generuj_fraktal_fibonacciego.py
Wymagana biblioteka: Pillow.
"""
    (OUT / "fraktal_fibonacciego_opis.txt").write_text(
        description, encoding="utf-8"
    )


if __name__ == "__main__":
    square_count, sides = generate()
    write_description(square_count, sides)
    print(f"Zapisano grafikę; kwadraty: {', '.join(map(str, sides))}")
