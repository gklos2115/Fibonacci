# Code review: moduł `sierpinski` (Python)

**Zakres:** pakiet `sierpinski/` (6 plików), `tests/test_sierpinski.py`, `pyproject.toml`
**Środowisko:** Python 3.15.0, Windows 11, tylko biblioteka standardowa (brak Pillow i numpy)
**Data:** 2026-10-13

---

## 1. Podsumowanie

| Kryterium | Ocena |
|---|---|
| Zgodność z wymaganiami (n = 100, fiolety, odcień per wgłębienie, jasność ∝ głębokość) | ✅ spełnione |
| Poprawność | ✅ 27/27 testów przechodzi |
| Czytelność i struktura | ✅ dobra |
| Wydajność | ✅ render 2.2 s (było 3.8 s), cały program ~4.6 s (było ~5.9 s) po R4 |
| Zużycie pamięci | ✅ kodowanie PNG: szczyt 1.1 MB (było ~88 MB) po R3; płótno bez podwójnej kopii (R10) |
| Jakość obrazu | ✅ opcjonalny antyaliasing 2×2 / 4×4 (R5) |
| Gotowość produkcyjna | ✅ instalowalny pakiet, CLI, walidacja wejścia |

**Werdykt:** kod nadaje się do użycia. Nie znalazłem błędów, które zmieniałyby obraz. Uwagi w sekcji 4 dotyczą wydajności i jakości krawędzi, nie poprawności.

---

## 2. Wymagania i to, jak są spełnione

| Wymaganie | Realizacja | Gdzie |
|---|---|---|
| n = 100 iteracji | `RenderConfig.iterations = 100` (domyślnie). Pętla dzieli trójkąty do `depth < iterations` | `config.py`, `fractal.py` |
| Fioletowe odcienie | HSL z odcieniem od 262° do 292° i stałym nasyceniem 70%. Test sprawdza, że każdy kolor ma odcień w zakresie 255–300° i B > G | `color.py`, `PaletteTests` |
| Odcień odpowiadający wgłębieniu | każde wgłębienie dostaje kolor swojego poziomu `palette(depth + 1)` | `fractal.py` |
| Proporcjonalna zmiana jasności | `L = 15% + 70% · d / D_eff`, czyli liniowo. Test sprawdza, że różnice jasności między poziomami są stałe (±0.01) | `DepthPalette._compute`, `test_lightness_grows_linearly…` |

### Uwaga merytoryczna o n = 100

Pełne 100 poziomów to 3¹⁰⁰ ≈ 5·10⁴⁷ trójkątów, czego nie da się policzyć. Kod przycina gałąź, gdy bok spada poniżej `min_px` (1 px). Przy szerokości 4096 px daje to **12 narysowanych poziomów** i **265 720 wgłębień**. Poziomy od 13 do 100 mieściłyby się wewnątrz pojedynczych pikseli, więc obraz wygląda tak samo, jak przy dosłownym n = 100. Program nie przemilcza tego: `RenderResult.truncated` przechowuje tę informację, a CLI wypisuje ostrzeżenie.

Pomiar liczby pikseli na każdy poziom (próbkowanie co 7. piksel) potwierdza, że **wszystkie 12 poziomów jest widocznych** i każdy kolejny zajmuje około ¾ powierzchni poprzedniego, czyli tyle, ile wynika z geometrii fraktala:

```
d=1  242433   d=4  102425   d=7  43195   d=10 18253
d=2  181963   d=5   76662   d=8  32464   d=11 13615
d=3  136397   d=6   57418   d=9  24368   d=12 10031
```

---

## 3. Architektura

```
sierpinski/
├── config.py   RenderConfig: niemutowalna konfiguracja i walidacja
├── color.py    hsl_to_rgb, DepthPalette: kolor dla głębokości (kolory liczone raz)
├── raster.py   Canvas: bufor RGB i fill_triangle (scanline)
├── fractal.py  render(), effective_depth(), RenderResult
├── png.py      encode_png / save_png: PNG z zlib i struct
├── supersample.py box_filter_row: średnia bloków k×k (antyaliasing)
├── __main__.py CLI (argparse), kod wyjścia 2 przy złych argumentach
└── __init__.py publiczne API (__all__)
```

**Mocne strony**
- Jedna odpowiedzialność na moduł. Rasteryzacja, paleta i koder PNG nie wiedzą nic o fraktalu, więc można je użyć osobno.
- `RenderConfig` jest `frozen` i walidowany w `__post_init__`. Błędne dane zatrzymują się na wejściu, a nie w połowie renderowania.
- Pętla na jawnym stosie zamiast rekurencji. Nie ma ryzyka `RecursionError` nawet przy `iterations=10**9`, bo przycinanie zatrzymuje podział na `min_px`. Stos ma najwyżej około 2·D + 1 elementów.
- `effective_depth()` liczy pętlą, a nie przez `log2`, więc daje dokładnie ten sam warunek co `render()`. Nie ma rozjazdu przez zaokrąglenia zmiennoprzecinkowe.
- Wypełnianie używa reguły środka piksela z krawędziami półotwartymi, więc sąsiednie trójkąty nie zachodzą na siebie i nie zostawiają szczelin. Sprawdza to `test_adjacent_triangles_cover_square_without_overlap`.
- Wypełnianie odcinka to jedno przypisanie plastra `bytearray` z buforowanego wzorca wiersza, a nie pętla po pikselach. To kluczowe dla wydajności w czystym Pythonie.
- `hsl_to_rgb` jest sprawdzane względem `colorsys` (stdlib) na siatce 360 kombinacji.

---

## 4. Znalezione problemy

Legenda: 🔴 błąd · 🟠 istotne · 🟡 drobne · 🔵 sugestia · ✅ poprawione w trakcie review

### ✅ R1. `iterations=True` przechodziło walidację (`config.py`)
`bool` dziedziczy po `int`, więc `RenderConfig(iterations=True)` było akceptowane jako n = 1.
**Poprawka:** dodano jawne `isinstance(self.iterations, bool)` i przypadek w `test_invalid_values`.

### ✅ R2. Brak metadanych pakietu
Bez `pyproject.toml` modułu nie dało się zainstalować przez `pip`.
**Poprawka:** dodano `pyproject.toml` z `dependencies = []` i skryptem konsolowym `sierpinski`.

### ✅ R3. Szczyt pamięci przy kodowaniu PNG (`png.py:encode_png`)
`b"".join(...)` budowało całe surowe dane (~44 MB), które razem z buforem obrazu dawały **~88 MB** szczytu w `encode_png` (pomiar `tracemalloc`).
**Poprawka:** kompresja strumieniowa przez `zlib.compressobj()`. Każdy wiersz trafia do kompresora bezpośrednio jako `memoryview`, bez kopii i bez sklejania nieskompresowanych danych. W pamięci zostaje tylko skompresowany wynik (~0.24 MB).

| | przed | po |
|---|---|---|
| szczyt pamięci `encode_png` (4096×3566) | ~88 MB | **1.1 MB** |
| czas kodowania | 1.8 s | **1.3 s** |

Test `test_streamed_idat_roundtrip` dekompresuje IDAT i sprawdza, że każdy wiersz ma bajt filtra 0, a dane po rozpakowaniu są identyczne z buforem.

### ✅ R4. Wydajność rasteryzacji (`raster.py`, `fractal.py`)
Pętla w `fill_triangle` szukała w każdym wierszu przecięć z 3 krawędziami, choć w tym fraktalu wszystkie trójkąty mają poziomą podstawę.
**Poprawka (trzy części):**
1. Nowa metoda `Canvas.fill_flat_triangle(apex, base_y, base_left, base_right, rgb)`. Nachylenia lewej i prawej krawędzi są liczone raz, a w wierszu zostaje jedno mnożenie na krawędź. Ogólne `fill_triangle` zostało bez zmian, dla innych zastosowań.
2. `render()` trzyma na stosie tylko `(x, y, depth, side)` wierzchołka, a nie trzy krotki punktów. Współrzędne wgłębienia i dzieci wynikają z boku (`h = s·√3/2`), więc znika `_midpoint` i tworzenie krotek.
3. Warunek przycinania jest sprawdzany **przed** `push`. Liście drzewa (~530 tys. operacji push/pop) nie trafiają już na stos.

| | przed | po |
|---|---|---|
| `render()` 4096 px (mediana z 3) | 3.78 s | **2.18 s** (1.7×) |
| cały CLI (render + PNG + zapis) | 5.87 s | **4.61 s** |

Szacowane w review „2–3×” okazało się zbyt optymistyczne. Przy 265 tys. małych trójkątów dominuje teraz koszt samego wywołania funkcji i przypisania plastra, a nie liczenie przecięć. Dalszy zysk wymagałby rezygnacji z czystego Pythona (numpy lub rozszerzenie w C).

**Brak zmian w obrazie:** SHA-256 bufora pikseli jest identyczny przed i po zmianie dla 4096 px (`30c952d3…`) i 256 px (`76273e3d…`). Pilnują tego dwa nowe testy:
- `test_flat_fast_path_matches_general_fill`: 300 losowych trójkątów (także wychodzących poza płótno i mniejszych od piksela), bajt w bajt zgodnych z `fill_triangle`;
- `test_image_regression_hash`: hash obrazu 256 px.

### ✅ R5. Brak antyaliasingu
Krawędzie były „schodkowe”, a w strefach najmniejszych wgłębień (bok ~1 px) próbka w środku piksela trafiała raz w wgłębienie, raz w ciemne tło trójkąta. Przy powiększeniu dawało to ciemny szum (zob. `porownanie_aa.png`, lewa połowa).

**Poprawka:** nowy parametr `RenderConfig.supersample` ∈ {1, 2, 4} (CLI: `-s/--supersample`). Domyślnie 1, czyli zachowanie bez zmian i identyczny hash obrazu.
1. **Render w k× większej rozdzielczości, w pasach** (`fractal._draw_band`, `BAND_ROWS = 128` wierszy wyjściowych). Pełny obraz 16384×14264 przy k = 4 zająłby ~700 MB, a pas zajmuje ~25 MB. Poddrzewa leżące poza pasem są pomijane, więc narzut powtórnego przechodzenia drzewa to ~1% (805 518 zamiast 797 161 wywołań wypełniania przy k = 2).
2. **Uśrednianie bloków k×k** (`supersample.box_filter_row`) przez arytmetykę dużych `int`: każdy bajt kanału dostaje 16-bitowy tor, więc suma k wierszy, suma k sąsiednich pikseli (przesunięcie o 48 bitów) i dzielenie przez k² z zaokrągleniem (przesunięcie bitowe) liczą się w C dla całego wiersza naraz. Piksel po pikselu w Pythonie trwałoby to ~1 min dla k = 2, a tak trwa ~1.3 s. Ograniczenie k do potęg dwójki pozwala dzielić przesunięciem, a maks. wartość toru (255·16 + 8) mieści się w 16 bitach.
3. **Paleta liczona w pikselach wyjściowych, nie w próbkach.** Pierwsza wersja skalowała jasność do liczby poziomów w próbkach (14 przy k = 4 zamiast 12), przez co to samo wgłębienie miało inny kolor z antyaliasingiem i bez. Teraz antyaliasing tylko wygładza, a poziomy mniejsze od piksela dostają najjaśniejszy kolor (`DepthPalette` przycina głębokość).

| k | narysowane poziomy | wgłębień | czas CLI (4096 px) | szczyt pamięci renderu |
|---|---|---|---|---|
| 1 | 12 | 265 720 | ~2.2 s | 44 MB |
| 2 | 13 | 797 161 | ~6–10 s | 51 MB |
| 4 | 14 | 2 391 484 | ~29 s | 70 MB |

Czas k = 4 jest wysoki, ale to opcja dla obrazu końcowego, nie domyślna. Koszt rośnie ~3× na każde podwojenie k (o jeden poziom więcej).

**Testy (7 nowych):** `box_filter_row` zgodne bajt w bajt z wolną implementacją wzorcową dla k = 1, 2, 4; brak przepełnienia torów dla wartości 0 i 255; odrzucanie złych danych; render w pasach (wymuszone 7-wierszowe pasy) **identyczny** z uśrednieniem obrazu narysowanego w całości w 2× rozdzielczości; antyaliasing daje >10× więcej odcieni na krawędziach przy tych samych wymiarach; kolory wnętrz wgłębień identyczne dla k = 1, 2, 4; liczba wgłębień zgodna ze wzorem (3^D − 1)/2.

### ✅ R10. Podwójna kopia obrazu przy tworzeniu `Canvas` (`raster.py`), znalezione przy R5
`bytearray(bytes(bg) * n)` najpierw budowało 44 MB `bytes`, a potem kopiowało je do `bytearray`, więc chwilowo w pamięci były 2 pełne kopie. Do tego przy pasach poprzedni pas żył jeszcze w trakcie tworzenia następnego.
**Poprawka:** `bytearray(bytes(bg)) * n` (jeden bufor) i jawne `del` pasa na końcu pętli. Szczyt renderu przy k = 2 spadł z 88 MB do 51 MB, a przy k = 4 ze 120 MB do 70 MB. Obraz bez zmian (hash).

### 🟡 R6. Kolor tła trójkąta (d = 0) łączy się wizualnie z tłem obrazka
`palette(0)` = `(31, 11, 65)` i `background` = `(12, 8, 17)` mają mały kontrast. To kwestia estetyki, nie poprawności.
**Rekomendacja:** podnieść `lightness_start` do ~0.20 albo dodać obrys głównego trójkąta.

### 🔵 R7. `# type: ignore` w `hsl_to_rgb` (`color.py`)
Generator w `tuple(...)` sprawia, że mypy nie widzi typu `tuple[int, int, int]`. Czytelniej będzie zwrócić krotkę jawnie, `return (r8, g8, b8)`, i usunąć wyciszenie.

### 🔵 R8. Uruchamianie testów wymaga `tests/__init__.py`
`unittest discover -s tests -t .` wymaga pakietu, więc plik został dodany. Warto opisać polecenie testowe w README albo w `pyproject.toml` (`[tool.pytest.ini_options]`, jeśli w przyszłości dojdzie pytest).

### 🔵 R9. Duplikacja warunku przycinania
Warunek przycinania występuje w `render()` (dwukrotnie: dla korzenia i przed `push`) i w `effective_depth()`. Teraz są spójne, co potwierdzają testy liczby wgłębień, ale przy zmianie jednego łatwo zapomnieć o pozostałych. Rekomendacja: wydzielić `_should_subdivide(depth, side, cfg)`. Kosztem jest jedno wywołanie funkcji więcej na trójkąt (~5% czasu renderu).

---

## 5. Testy

```
Ran 27 tests in 1.38s
OK
```

| Obszar | Co sprawdzają |
|---|---|
| `HslTests` | zgodność `hsl_to_rgb` z `colorsys` (±1) |
| `PaletteTests` | fiolet w każdym kolorze, liniowość jasności, ograniczanie głębokości do zakresu, `max_depth = 0` |
| `ConfigTests` | odrzucanie złych danych (w tym `bool` i `float`), wysokość obrazu |
| `DepthTests` | `effective_depth` dla n = 100, 3 i 0 oraz trójkąta mniejszego niż piksel |
| `RasterTests` | brak nakładania i szczelin między sąsiednimi trójkątami, przycinanie do płótna, zgodność `fill_flat_triangle` z `fill_triangle` (300 losowych przypadków) |
| `RenderTests` | liczba wgłębień 0, 1, 4, 13 dla n = 0..3; przycinanie dla n = 100; kolor środka głównego wgłębienia; **hash regresji obrazu** |
| `PngTests` | sygnatura, poprawne CRC wszystkich chunków, wymiary IHDR, dekompresja IDAT, zła kompresja, **strumieniowy IDAT = bufor** |
| `SupersampleTests` | filtr k×k = implementacja wzorcowa, brak przepełnień, render w pasach = pełny obraz 2× uśredniony, gładkie krawędzie, niezmienione kolory wgłębień, wzór liczby wgłębień |
| `CliTests` | zapis pliku, kod wyjścia 2 przy błędnym `-n` |

Dodany został też brakujący wcześniej test regresji obrazu (`test_image_regression_hash`).

---

## 6. Użycie

```bash
python -m sierpinski                       # n=100, 4096 px -> sierpinski_n100.png
python -m sierpinski -n 100 --width 8192 -o duzy.png
python -m sierpinski -s 4 -o sierpinski_n100_aa.png   # antyaliasing 4x4
python -m unittest discover -s tests -t .
```

```python
from sierpinski import RenderConfig, render, save_png

result = render(RenderConfig(iterations=100, hue_start=260, hue_end=300))
save_png(result.canvas, "fiolet.png")
print(result.effective_depth, result.holes, result.truncated)
```

---

## 7. Priorytety dalszych prac

1. ~~**R3**: strumieniowa kompresja PNG~~ ✅ zrobione
2. ~~**R4**: szybka ścieżka dla trójkątów z poziomą podstawą~~ ✅ zrobione (1.7×)
3. ~~Test regresji obrazu (hash)~~ ✅ zrobione
4. ~~**R5**: opcjonalny supersampling~~ ✅ zrobione (+ R10 przy okazji)
5. **R6, R7, R9**: kosmetyka
