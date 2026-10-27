"""Antyaliasing przez supersampling: uśrednianie bloków k×k próbek.

Uśrednianie w czystym Pythonie piksel po pikselu byłoby bardzo wolne
(~30 mln próbek dla 4096 px i k = 2), dlatego używamy arytmetyki dużych liczb
całkowitych jako „SIMD”. Każdy bajt kanału zajmuje 16-bitowy tor w jednej
liczbie ``int``, więc dodawanie, przesunięcia i dzielenie przez 2^m są
wykonywane w C dla całego wiersza naraz.
"""
from __future__ import annotations

from functools import lru_cache

SUPPORTED_FACTORS = (1, 2, 4)

_LANE_BITS = 16          # tor na jeden bajt kanału; mieści 255·16 + zaokrąglenie
_PIXEL_SHIFT = 3 * _LANE_BITS  # przesunięcie o jeden piksel RGB


@lru_cache(maxsize=8)
def _rounding_constant(lanes: int, k: int) -> int:
    """Liczba z wartością k²/2 w każdym torze (zaokrąglenie do najbliższej)."""
    half = (k * k) // 2
    return int.from_bytes(bytes((0, half)) * lanes, "big")


def box_filter_row(rows: list[memoryview | bytes], k: int) -> bytes:
    """Zwraca jeden wiersz RGB będący średnią bloków k×k z ``k`` wierszy wejścia.

    Każdy wiersz wejściowy ma długość ``out_width · k · 3`` bajtów.
    Wynik jest zaokrąglany do najbliższej liczby całkowitej.
    """
    if k not in SUPPORTED_FACTORS:
        raise ValueError(f"k musi być jednym z {SUPPORTED_FACTORS}")
    if len(rows) != k:
        raise ValueError("potrzeba dokładnie k wierszy")
    n = len(rows[0])
    if n % (3 * k):
        raise ValueError("długość wiersza musi być wielokrotnością 3·k")
    if k == 1:
        return bytes(rows[0])

    # 1. Suma k wierszy: każdy bajt rozszerzony do 16 bitów (bajt starszy = 0).
    wide = bytearray(2 * n)
    total = 0
    for row in rows:
        if len(row) != n:
            raise ValueError("wiersze muszą mieć równą długość")
        wide[1::2] = row
        total += int.from_bytes(wide, "big")

    # 2. Suma k sąsiednich pikseli w poziomie: przesunięcie o tor piksela
    #    dodaje do każdego toru wartość z piksela po lewej.
    acc = total
    for i in range(1, k):
        acc += total >> (_PIXEL_SHIFT * i)

    # 3. Dzielenie przez k² (potęga dwójki) z zaokrągleniem. Bity „wyciekające”
    #    z toru wyżej trafiają tylko do starszego bajtu toru, który odrzucamy.
    acc += _rounding_constant(n, k)
    acc >>= (k * k).bit_length() - 1
    low = acc.to_bytes(2 * n, "big")[1::2]

    # 4. Wynik dla piksela p leży w torach ostatniej próbki bloku (k·p + k - 1).
    out = bytearray(n // k)
    step = 3 * k
    first = 3 * (k - 1)
    for c in range(3):
        out[c::3] = low[first + c::step]
    return bytes(out)
