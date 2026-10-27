import colorsys
import hashlib
import random
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from sierpinski import (
    Canvas, DepthPalette, RenderConfig, box_filter_row, effective_depth, encode_png, hsl_to_rgb,
    render, save_png,
)
from sierpinski.__main__ import main


class HslTests(unittest.TestCase):
    def test_matches_colorsys(self):
        for h in range(0, 360, 15):
            for s in (0.0, 0.5, 1.0):
                for l in (0.0, 0.2, 0.5, 0.8, 1.0):
                    r, g, b = colorsys.hls_to_rgb(h / 360, l, s)
                    expected = tuple(round(v * 255) for v in (r, g, b))
                    got = hsl_to_rgb(h, s, l)
                    for e, v in zip(expected, got):
                        self.assertLessEqual(abs(e - v), 1, (h, s, l))


class PaletteTests(unittest.TestCase):
    def test_lightness_grows_linearly_and_stays_purple(self):
        cfg = RenderConfig()
        pal = DepthPalette(cfg, 12)
        lights = []
        for d in range(13):
            r, g, b = pal(d)
            h, l, _ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            self.assertTrue(255 <= h * 360 <= 300, f"odcień poza fioletem: {h * 360}")
            self.assertGreater(b, g)
            lights.append(l)
        diffs = [b - a for a, b in zip(lights, lights[1:])]
        self.assertTrue(all(d > 0 for d in diffs))
        self.assertAlmostEqual(max(diffs), min(diffs), delta=0.01)

    def test_clamps_depth(self):
        pal = DepthPalette(RenderConfig(), 3)
        self.assertEqual(pal(-1), pal(0))
        self.assertEqual(pal(99), pal(3))

    def test_zero_depth(self):
        self.assertEqual(len(DepthPalette(RenderConfig(), 0)), 1)


class ConfigTests(unittest.TestCase):
    def test_invalid_values(self):
        for kwargs in ({"iterations": -1}, {"iterations": True}, {"iterations": 2.5},{"width": 8}, {"margin": 5000},
                       {"min_px": 0}, {"saturation": 2}, {"background": (0, 0, 300)}):
            with self.assertRaises(ValueError, msg=kwargs):
                RenderConfig(**kwargs)

    def test_height_fits_triangle(self):
        cfg = RenderConfig(width=4096, margin=68)
        self.assertEqual(cfg.height, 3430 + 136)  # ceil(3960 * sqrt(3)/2) + 2 * 68


class DepthTests(unittest.TestCase):
    def test_effective_depth(self):
        self.assertEqual(effective_depth(3960, 100, 1.0), 12)
        self.assertEqual(effective_depth(3960, 3, 1.0), 3)
        self.assertEqual(effective_depth(3960, 0, 1.0), 0)
        self.assertEqual(effective_depth(0.5, 100, 1.0), 0)


class RasterTests(unittest.TestCase):
    def test_adjacent_triangles_cover_square_without_overlap(self):
        c = Canvas(10, 10, (0, 0, 0))
        c.fill_triangle((0, 0), (10, 0), (0, 10), (1, 1, 1))
        c.fill_triangle((10, 0), (10, 10), (0, 10), (2, 2, 2))
        values = {c.get_pixel(x, y) for x in range(10) for y in range(10)}
        self.assertEqual(values, {(1, 1, 1), (2, 2, 2)})

    def test_flat_fast_path_matches_general_fill(self):
        rng = random.Random(1234)
        for _ in range(300):
            ax, ay = rng.uniform(-20, 80), rng.uniform(-20, 80)
            base_y = rng.uniform(-20, 80)
            half = rng.uniform(0.1, 40)
            base_l, base_r = ax - half, ax + half
            a = Canvas(64, 64, (0, 0, 0))
            b = Canvas(64, 64, (0, 0, 0))
            a.fill_triangle((ax, ay), (base_l, base_y), (base_r, base_y), (5, 6, 7))
            b.fill_flat_triangle((ax, ay), base_y, base_l, base_r, (5, 6, 7))
            self.assertEqual(a.pixels, b.pixels, (ax, ay, base_y, half))

    def test_clipping_outside_canvas(self):
        c = Canvas(4, 4, (0, 0, 0))
        c.fill_triangle((-10, -10), (20, -10), (5, 30), (9, 9, 9))
        self.assertEqual(c.get_pixel(0, 0), (9, 9, 9))
        self.assertEqual(len(c.pixels), 4 * 4 * 3)


class RenderTests(unittest.TestCase):
    def test_hole_counts(self):
        for n, expected in ((0, 0), (1, 1), (2, 4), (3, 13)):
            res = render(RenderConfig(iterations=n, width=256, margin=8))
            self.assertEqual(res.holes, expected)
            self.assertEqual(res.effective_depth, n)

    def test_n100_is_truncated_to_pixel_resolution(self):
        res = render(RenderConfig(iterations=100, width=256, margin=8))
        self.assertEqual(res.effective_depth, 8)
        self.assertEqual(res.holes, (3 ** 8 - 1) // 2)
        self.assertTrue(res.truncated)

    def test_image_regression_hash(self):
        # Hash pikseli z wersji sprzed optymalizacji R4: każda zmiana
        # rasteryzacji lub palety, która zmienia obraz, zostanie wykryta.
        res = render(RenderConfig(iterations=100, width=256, margin=8))
        self.assertEqual(
            hashlib.sha256(res.canvas.pixels).hexdigest(),
            "76273e3de38f22ac11f61bdb0b58f9165119798ad202b6e2064858c2d2eca255",
        )

    def test_center_of_main_hole_has_depth1_color(self):
        cfg = RenderConfig(iterations=100, width=512, margin=16)
        res = render(cfg)
        pal = DepthPalette(cfg, res.effective_depth)
        cx = cfg.width // 2
        cy = int(cfg.margin + cfg.side * 0.866 * 0.70)
        self.assertEqual(res.canvas.get_pixel(cx, cy), pal(1))
        self.assertEqual(res.canvas.get_pixel(0, 0), cfg.background)


class PngTests(unittest.TestCase):
    def test_valid_png_structure(self):
        c = Canvas(7, 3, (10, 20, 30))
        data = encode_png(c)
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        pos, chunks = 8, {}
        while pos < len(data):
            (length,) = struct.unpack(">I", data[pos:pos + 4])
            kind = data[pos + 4:pos + 8]
            body = data[pos + 8:pos + 8 + length]
            (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
            self.assertEqual(crc, zlib.crc32(kind + body) & 0xFFFFFFFF)
            chunks[kind] = body
            pos += 12 + length
        w, h = struct.unpack(">II", chunks[b"IHDR"][:8])
        self.assertEqual((w, h), (7, 3))
        raw = zlib.decompress(chunks[b"IDAT"])
        self.assertEqual(len(raw), 3 * (1 + 7 * 3))
        self.assertEqual(raw[1:4], bytes((10, 20, 30)))

    def test_streamed_idat_roundtrip(self):
        res = render(RenderConfig(iterations=100, width=200, margin=4))
        c = res.canvas
        data = encode_png(c)
        (length,) = struct.unpack(">I", data[33:37])
        raw = zlib.decompress(data[41:41 + length])
        rows = [raw[y * (c.stride + 1):(y + 1) * (c.stride + 1)] for y in range(c.height)]
        self.assertTrue(all(r[0] == 0 for r in rows))
        self.assertEqual(b"".join(r[1:] for r in rows), bytes(c.pixels))

    def test_bad_compression(self):
        with self.assertRaises(ValueError):
            encode_png(Canvas(1, 1, (0, 0, 0)), compression=10)


def _reference_box_filter(rows, k):
    """Wolna, oczywista implementacja średniej k×k (do porównań)."""
    width = len(rows[0]) // 3 // k
    out = bytearray()
    for p in range(width):
        for c in range(3):
            s = sum(row[(p * k + dx) * 3 + c] for row in rows for dx in range(k))
            out.append((s + (k * k) // 2) // (k * k))
    return bytes(out)


class SupersampleTests(unittest.TestCase):
    def test_box_filter_matches_reference(self):
        rng = random.Random(7)
        for k in (1, 2, 4):
            for width in (1, 3, 17, 64):
                rows = [bytes(rng.randrange(256) for _ in range(width * k * 3)) for _ in range(k)]
                self.assertEqual(box_filter_row(rows, k), _reference_box_filter(rows, k), (k, width))

    def test_box_filter_extremes_do_not_overflow(self):
        for k in (2, 4):
            rows = [b"\xff" * (5 * k * 3)] * k
            self.assertEqual(box_filter_row(rows, k), b"\xff" * 15)
            rows = [b"\x00" * (5 * k * 3)] * k
            self.assertEqual(box_filter_row(rows, k), b"\x00" * 15)

    def test_box_filter_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            box_filter_row([b"\x00" * 6] * 3, 3)
        with self.assertRaises(ValueError):
            box_filter_row([b"\x00" * 6], 2)
        with self.assertRaises(ValueError):
            box_filter_row([b"\x00" * 6, b"\x00" * 12], 2)

    def test_config_rejects_unsupported_factor(self):
        for k in (0, 3, 8, True):
            with self.assertRaises(ValueError):
                RenderConfig(supersample=k)

    def test_banded_render_equals_downsampled_full_resolution(self):
        # Render pasami (z małym BAND_ROWS, żeby było ich wiele) musi dać to samo,
        # co narysowanie całości w 2x większej rozdzielczości i uśrednienie.
        import sierpinski.fractal as fractal
        k, width, margin = 2, 150, 5
        saved = fractal.BAND_ROWS
        fractal.BAND_ROWS = 7
        try:
            aa = render(RenderConfig(iterations=100, width=width, margin=margin, supersample=k))
        finally:
            fractal.BAND_ROWS = saved
        # Referencja: cały obraz w rozdzielczości próbek, na jednym płótnie,
        # z tą samą paletą (skalowaną do głębokości w pikselach wyjściowych).
        cfg = RenderConfig(iterations=100, width=width, margin=margin)
        side = cfg.side * k
        depth = effective_depth(side, 100, 1.0)
        self.assertEqual(aa.effective_depth, depth)
        pal = DepthPalette(cfg, effective_depth(cfg.side, 100, 1.0))
        hi = Canvas(width * k, cfg.height * k, cfg.background)
        fractal._draw_band(hi, (margin + cfg.side / 2) * k, float(margin * k), side, 0,
                           [pal(d) for d in range(depth + 1)], 100, 1.0)
        bg_row = bytes(RenderConfig().background) * hi.width
        out = bytearray()
        for y in range(aa.canvas.height):
            rows = []
            for i in range(k):
                hy = y * k + i
                rows.append(hi.pixels[hy * hi.stride:(hy + 1) * hi.stride] if hy < hi.height else bg_row)
            out += _reference_box_filter(rows, k)
        self.assertEqual(bytes(aa.canvas.pixels), bytes(out))

    def test_antialiasing_creates_intermediate_edge_colors(self):
        plain = render(RenderConfig(iterations=100, width=128, margin=4))
        smooth = render(RenderConfig(iterations=100, width=128, margin=4, supersample=4))
        self.assertEqual((smooth.canvas.width, smooth.canvas.height),
                         (plain.canvas.width, plain.canvas.height))
        count = lambda c: len({bytes(c.pixels[i:i + 3]) for i in range(0, len(c.pixels), 3)})
        self.assertLessEqual(count(plain.canvas), plain.effective_depth + 2)
        self.assertGreater(count(smooth.canvas), 10 * count(plain.canvas))

    def test_antialiasing_keeps_hole_colors(self):
        # Środek dużego wgłębienia ma ten sam kolor z antyaliasingiem i bez.
        plain = render(RenderConfig(iterations=100, width=512, margin=16))
        for k in (2, 4):
            smooth = render(RenderConfig(iterations=100, width=512, margin=16, supersample=k))
            for x, y in ((256, 300), (256, 120), (150, 400)):
                self.assertEqual(smooth.canvas.get_pixel(x, y), plain.canvas.get_pixel(x, y), (k, x, y))

    def test_holes_formula_matches_counting(self):
        for n in (0, 1, 2, 5, 100):
            res = render(RenderConfig(iterations=n, width=200, margin=4, supersample=2))
            self.assertEqual(res.holes, (3 ** res.effective_depth - 1) // 2)


class CliTests(unittest.TestCase):
    def test_cli_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "x.png"
            self.assertEqual(main(["-n", "100", "--width", "128", "--margin", "4", "-o", str(out)]), 0)
            self.assertTrue(out.read_bytes().startswith(b"\x89PNG"))

    def test_cli_rejects_bad_args(self):
        self.assertEqual(main(["-n", "-5"]), 2)


if __name__ == "__main__":
    unittest.main()
