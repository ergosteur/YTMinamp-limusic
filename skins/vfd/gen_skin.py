#!/usr/bin/python3
"""VFD: classic Winamp 2.x skins in the style of a vacuum fluorescent display head unit.

Two themes from one procedural generator: "vfd", a black gloss faceplate in a silver surround
with one wide VFD window, and "vfd-silver", a satin silver faceplate with the keys on the silver
and only the displays as VFD glass. Teal phosphor segments (unlit ones showing as dim ghosts)
with amber-orange caps, lozenges and indicators, dot-matrix time digits, spectrum-analyzer
bars for the volume, balance and EQ, rubber and translucent aqua keys, a lit rotary knob in the
About spot. Everything is drawn here from code: gradients, anti-aliased masks, hand-made pixel
fonts, and a system bold italic sans (Liberation Sans, else DejaVu Sans) for the faceplate print.
Layouts follow skins/ember/gen_skin.py.

    /usr/bin/python3 -I gen_skin.py [vfd|vfd-silver ...]   (no theme builds both)
    /usr/bin/python3 -I gen_skin.py --list
    options: --title TEXT   main titlebar print (default "YTMinamp")
             --name NAME    .wsz base name (default "YTMinamp-VFD"; the silver one adds "-Silver")
             --out DIR      where the .wsz files and previews go (default: beside this file);
                            the sheets go in DIR/out/<theme>/

Per theme: the bitmaps and text files in out/<theme>/, zipped flat into <NAME>[-Silver].wsz, and
preview-<theme>.png (the windows assembled from the sprites the way the app does, 2x).
Deterministic: fixed seeds and fixed zip dates.
"""

import argparse
import os
import sys
import zipfile
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # skins/genex_wacup.py, which finishes each .wsz
import genex_wacup  # noqa: E402

OPT = SimpleNamespace(title="YTMinamp", name="YTMinamp-VFD", out=HERE)
OUT = None          # <out>/out/<theme>, set by use_theme
T = None            # the theme in use

SEP = (255, 0, 255)  # gen.bmp letter separators (never shown)

ITALIC_FONTS = ["/usr/share/fonts/liberation-sans-fonts/LiberationSans-BoldItalic.ttf",
                "/usr/share/fonts/liberation-sans/LiberationSans-BoldItalic.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
                "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-BoldOblique.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
                "LiberationSans-BoldItalic.ttf", "DejaVuSans-BoldOblique.ttf"]
LIST_FONTS = ["/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf",
              "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              "LiberationSans-Regular.ttf", "DejaVuSans.ttf"]

# ------------------------------------------------------------------------------------------
# Themes
# ------------------------------------------------------------------------------------------

_COMMON = dict(
    disp=(4, 10, 11), ink=(96, 248, 222), accent=(255, 138, 30),
    pledit=dict(Normal="#3CF2D2", Current="#FF8A1E", NormalBG="#040A0B", SelectedBG="#0E3E39"),
    vis=[(255, 186, 76), (60, 242, 210), (24, 150, 132)],
    vis_rows=[(255, 186, 76), (255, 160, 50), (255, 138, 30), (150, 255, 236), (128, 254, 232),
              (108, 252, 228), (92, 250, 224), (78, 246, 218), (66, 242, 212), (60, 236, 206),
              (54, 226, 198), (48, 214, 188), (42, 202, 178), (38, 190, 168), (34, 178, 158), (30, 166, 148)],
    vis_dots=(16, 44, 41), vis_peak=(255, 138, 30), font="Arial",
)

THEMES = {
    "vfd": SimpleNamespace(name="vfd", suffix="", look="black gloss faceplate", **_COMMON),
    "vfd-silver": SimpleNamespace(name="vfd-silver", suffix="-Silver", look="satin silver faceplate",
                                  **_COMMON),
}


def use_theme(name):
    global T, OUT
    T = THEMES[name]
    OUT = os.path.join(OPT.out, "out", name)
    os.makedirs(OUT, exist_ok=True)


def wsz_name():
    return OPT.name + T.suffix


# ------------------------------------------------------------------------------------------
# Colour and canvas helpers (numpy, H x W x 3, int)
# ------------------------------------------------------------------------------------------


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ramp(stops, t):
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    i = min(n - 1, int(t * n))
    return lerp(stops[i], stops[i + 1], t * n - i)


def hexc(c):
    return "#%02X%02X%02X" % c


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def new(w, h, col=(0, 0, 0)):
    a = np.zeros((h, w, 3), dtype=np.int32)
    a[:, :] = col
    return a


def rect(a, x, y, w, h, col):
    if w > 0 and h > 0:
        y0, x0 = max(0, y), max(0, x)
        a[y0:y + h, x0:x + w] = col


def px(a, x, y, col):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        a[y, x] = col


def vfill(a, x, y, w, h, stops):
    for r in range(h):
        rect(a, x, y + r, w, 1, ramp(stops, r / max(1, h - 1)))


def hline(a, x, y, w, col):
    rect(a, x, y, w, 1, col)


# anti-aliased coverage masks (4x supersampled), painted with paint()

def _grid(w, h, ss=4):
    ys, xs = np.mgrid[0:h * ss, 0:w * ss]
    return (xs + 0.5) / ss, (ys + 0.5) / ss


def _down(m, w, h, ss=4):
    return m.reshape(h, ss, w, ss).mean(axis=(1, 3))


def circle_m(w, h, cx, cy, r):
    X, Y = _grid(w, h)
    return _down(((X - cx) ** 2 + (Y - cy) ** 2 <= r * r).astype(np.float32), w, h)


def ring_m(w, h, cx, cy, r0, r1):
    X, Y = _grid(w, h)
    d2 = (X - cx) ** 2 + (Y - cy) ** 2
    return _down(((d2 <= r1 * r1) & (d2 >= r0 * r0)).astype(np.float32), w, h)


def rr_m(w, h, x0, y0, x1, y1, r):
    """Rounded rectangle [x0, x1) x [y0, y1) with corner radius r."""
    X, Y = _grid(w, h)
    cx = np.clip(X, x0 + r, x1 - r)
    cy = np.clip(Y, y0 + r, y1 - r)
    inside = (X >= x0) & (X < x1) & (Y >= y0) & (Y < y1) & ((X - cx) ** 2 + (Y - cy) ** 2 <= r * r)
    return _down(inside.astype(np.float32), w, h)


def poly_m(w, h, pts):
    img = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(img).polygon([(x * 4, y * 4) for x, y in pts], fill=255)
    return np.asarray(img.resize((w, h), Image.BOX), dtype=np.float32) / 255


def paint(a, x, y, m, col, alpha=1.0):
    """Blend colour (or an H x W x 3 array) into a at (x, y) through coverage mask m."""
    h, w = m.shape
    y0, x0 = max(0, y), max(0, x)
    y1, x1 = min(a.shape[0], y + h), min(a.shape[1], x + w)
    if y1 <= y0 or x1 <= x0:
        return
    mm = m[y0 - y:y1 - y, x0 - x:x1 - x][:, :, None] * alpha
    src = np.asarray(col, dtype=np.float32)
    if src.ndim == 3:
        src = src[y0 - y:y1 - y, x0 - x:x1 - x]
    reg = a[y0:y1, x0:x1].astype(np.float32)
    a[y0:y1, x0:x1] = np.round(reg * (1 - mm) + src * mm).astype(np.int32)


def vgrad_arr(w, h, stops):
    g = np.array([ramp(stops, r / max(1, h - 1)) for r in range(h)], dtype=np.float32)
    return np.repeat(g[:, None, :], w, axis=1)


def rgrad_arr(w, h, cx, cy, r, stops):
    """Radial gradient, stops from the centre out to r."""
    X, Y = np.mgrid[0:h, 0:w][1] + 0.5, np.mgrid[0:h, 0:w][0] + 0.5
    t = np.clip(np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / r, 0, 1)
    out = np.zeros((h, w, 3), dtype=np.float32)
    for yy in range(h):
        for xx in range(w):
            out[yy, xx] = ramp(stops, t[yy, xx])
    return out

def G(*rows):
    return list(rows)


# 5-row font for text.bmp, titles and gen.bmp's letters.
FONT5 = {
    "A": G(".##.", "#..#", "####", "#..#", "#..#"),
    "B": G("###.", "#..#", "###.", "#..#", "###."),
    "C": G(".###", "#...", "#...", "#...", ".###"),
    "D": G("###.", "#..#", "#..#", "#..#", "###."),
    "E": G("####", "#...", "###.", "#...", "####"),
    "F": G("####", "#...", "###.", "#...", "#..."),
    "G": G(".###", "#...", "#.##", "#..#", ".###"),
    "H": G("#..#", "#..#", "####", "#..#", "#..#"),
    "I": G("###", ".#.", ".#.", ".#.", "###"),
    "J": G("...#", "...#", "...#", "#..#", ".##."),
    "K": G("#..#", "#.#.", "##..", "#.#.", "#..#"),
    "L": G("#...", "#...", "#...", "#...", "####"),
    "M": G("#..#", "####", "####", "#..#", "#..#"),
    "N": G("#..#", "##.#", "#.##", "#..#", "#..#"),
    "O": G(".##.", "#..#", "#..#", "#..#", ".##."),
    "P": G("###.", "#..#", "###.", "#...", "#..."),
    "Q": G(".##.", "#..#", "#..#", "#.#.", ".#.#"),
    "R": G("###.", "#..#", "###.", "#.#.", "#..#"),
    "S": G(".###", "#...", ".##.", "...#", "###."),
    "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#..#", "#..#", "#..#", "#..#", ".##."),
    "V": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": G("#..#", "#..#", "####", "####", "#..#"),
    "X": G("#..#", "#..#", ".##.", "#..#", "#..#"),
    "Y": G("#.#", "#.#", ".#.", ".#.", ".#."),
    "Z": G("####", "...#", ".##.", "#...", "####"),
    "0": G("###", "#.#", "#.#", "#.#", "###"),
    "1": G(".#.", "##.", ".#.", ".#.", "###"),
    "2": G("###", "..#", "###", "#..", "###"),
    "3": G("###", "..#", ".##", "..#", "###"),
    "4": G("#.#", "#.#", "###", "..#", "..#"),
    "5": G("###", "#..", "###", "..#", "###"),
    "6": G("###", "#..", "###", "#.#", "###"),
    "7": G("###", "..#", ".#.", ".#.", ".#."),
    "8": G("###", "#.#", "###", "#.#", "###"),
    "9": G("###", "#.#", "###", "..#", "###"),
    '"': G("#.#", "#.#", "...", "...", "..."),
    "@": G(".##.", "#.##", "#.##", "#...", ".###"),
    "…": G(".....", ".....", ".....", ".....", "#.#.#"),
    ".": G(".", ".", ".", ".", "#"),
    ":": G(".", "#", ".", "#", "."),
    "(": G(".#", "#.", "#.", "#.", ".#"),
    ")": G("#.", ".#", ".#", ".#", "#."),
    "-": G("...", "...", "###", "...", "..."),
    "'": G("#", "#", ".", ".", "."),
    "!": G("#", "#", "#", ".", "#"),
    "_": G("....", "....", "....", "....", "####"),
    "+": G("...", ".#.", "###", ".#.", "..."),
    "\\": G("#..", "#..", ".#.", "..#", "..#"),
    "/": G("..#", "..#", ".#.", "#..", "#.."),
    "[": G("##", "#.", "#.", "#.", "##"),
    "]": G("##", ".#", ".#", ".#", "##"),
    "^": G(".#.", "#.#", "...", "...", "..."),
    "&": G(".#..", "#.#.", ".#..", "#.#.", ".#.#"),
    "%": G("#.#", "..#", ".#.", "#..", "#.#"),
    ",": G("..", "..", "..", ".#", "#."),
    "=": G("...", "###", "...", "###", "..."),
    "$": G(".###", "#.#.", ".##.", ".#.#", "###."),
    "#": G(".#.#", "####", ".#.#", "####", ".#.#"),
    "å": G(".##.", ".##.", "#..#", "####", "#..#"),
    "ö": G("#..#", ".##.", "#..#", "#..#", ".##."),
    "ä": G("#..#", ".##.", "#..#", "####", "#..#"),
    "?": G("###.", "...#", ".##.", "....", ".#.."),
    "*": G("#.#", ".#.", "###", ".#.", "#.#"),
    " ": G("...", "...", "...", "...", "..."),
}

# 3x5 font for small labels.
TINY = {
    "A": G(".#.", "#.#", "###", "#.#", "#.#"),
    "B": G("##.", "#.#", "##.", "#.#", "##."),
    "C": G(".##", "#..", "#..", "#..", ".##"),
    "D": G("##.", "#.#", "#.#", "#.#", "##."),
    "E": G("###", "#..", "##.", "#..", "###"),
    "F": G("###", "#..", "##.", "#..", "#.."),
    "G": G(".##", "#..", "#.#", "#.#", ".##"),
    "H": G("#.#", "#.#", "###", "#.#", "#.#"),
    "I": G("###", ".#.", ".#.", ".#.", "###"),
    "K": G("#.#", "#.#", "##.", "#.#", "#.#"),
    "L": G("#..", "#..", "#..", "#..", "###"),
    "M": G("#.#", "###", "###", "#.#", "#.#"),
    "N": G("##.", "#.#", "#.#", "#.#", "#.#"),
    "O": G(".#.", "#.#", "#.#", "#.#", ".#."),
    "P": G("##.", "#.#", "##.", "#..", "#.."),
    "Q": G(".#.", "#.#", "#.#", "##.", ".##"),
    "R": G("##.", "#.#", "##.", "#.#", "#.#"),
    "S": G(".##", "#..", ".#.", "..#", "##."),
    "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#.#", "#.#", "#.#", "#.#", "###"),
    "V": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": G("#.#", "#.#", "###", "###", "#.#"),
    "X": G("#.#", "#.#", ".#.", "#.#", "#.#"),
    "Y": G("#.#", "#.#", ".#.", ".#.", ".#."),
    "Z": G("###", "..#", ".#.", "#..", "###"),
    " ": G("..", "..", "..", "..", ".."),
}
for _c in "0123456789+-.":
    TINY[_c] = FONT5[_c]

def glyph_w(font, c):
    return len(font[c][0])


def text_w(font, s, gap=1):
    s = [c for c in s if c in font]
    return sum(glyph_w(font, c) for c in s) + gap * max(0, len(s) - 1)


def draw_text(a, font, s, x, y, col, gap=1, shadow=None):
    for c in s:
        if c not in font:
            continue
        g = font[c]
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    if shadow is not None:
                        px(a, x + k + 1, y + r + 1, shadow)
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    px(a, x + k, y + r, col(r) if callable(col) else col)
        x += len(g[0]) + gap
    return x


def text_center(a, font, s, cx, y, col, gap=1, shadow=None):
    draw_text(a, font, s, cx - text_w(font, s, gap) // 2, y, col, gap, shadow)


for _c, _g in {
    "J": G("..#", "..#", "..#", "#.#", ".#."),
    "/": G("..#", "..#", ".#.", "#..", "#.."),
    ":": G(".", "#", ".", "#", "."),
    "·": G(".", ".", "#", ".", "."),
}.items():
    TINY[_c] = _g


# ------------------------------------------------------------------------------------------
# Icons
# ------------------------------------------------------------------------------------------


def tri_right(a, x, y, h, col):
    half = h // 2
    for r in range(h):
        rect(a, x, y + r, half - abs(r - half) + 1, 1, col)


def tri_left(a, x, y, h, col):
    half = h // 2
    for r in range(h):
        n = half - abs(r - half) + 1
        rect(a, x + half + 1 - n, y + r, n, 1, col)


def transport_icon(a, kind, cx, cy, col):
    if kind == "previous":
        rect(a, cx - 5, cy - 3, 2, 7, col)
        tri_left(a, cx - 3, cy - 3, 7, col)
        tri_left(a, cx + 1, cy - 3, 7, col)
    elif kind == "play":
        tri_right(a, cx - 2, cy - 4, 9, col)
    elif kind == "pause":
        rect(a, cx - 3, cy - 3, 2, 7, col)
        rect(a, cx + 1, cy - 3, 2, 7, col)
    elif kind == "stop":
        rect(a, cx - 3, cy - 3, 7, 7, col)
    elif kind == "next":
        tri_right(a, cx - 5, cy - 3, 7, col)
        tri_right(a, cx - 1, cy - 3, 7, col)
        rect(a, cx + 3, cy - 3, 2, 7, col)
    elif kind == "eject":
        for r in range(4):
            rect(a, cx - r, cy - 4 + r, 2 * r + 1, 1, col)
        rect(a, cx - 3, cy + 1, 7, 2, col)


def mini_transport_icon(a, kind, x, y, col):
    cx, cy = x + 5, y + 5
    if kind == "previous":
        rect(a, cx - 3, cy - 2, 1, 5, col)
        tri_left(a, cx - 2, cy - 2, 5, col)
        tri_left(a, cx + 1, cy - 2, 5, col)
    elif kind == "play":
        tri_right(a, cx - 1, cy - 3, 7, col)
    elif kind == "pause":
        rect(a, cx - 2, cy - 2, 2, 5, col)
        rect(a, cx + 1, cy - 2, 2, 5, col)
    elif kind == "stop":
        rect(a, cx - 2, cy - 2, 5, 5, col)
    elif kind == "next":
        tri_right(a, cx - 3, cy - 2, 5, col)
        tri_right(a, cx, cy - 2, 5, col)
        rect(a, cx + 3, cy - 2, 1, 5, col)
    elif kind == "eject":
        for r in range(3):
            rect(a, cx - r, cy - 3 + r, 2 * r + 1, 1, col)
        rect(a, cx - 2, cy + 1, 5, 1, col)


def caption_glyph(a, kind, x, y, col):
    """Glyph for a 9x9 titlebar button whose top-left is (x, y)."""
    if kind == "options":
        rect(a, x + 2, y + 3, 5, 1, col)
        rect(a, x + 3, y + 4, 3, 1, col)
        px(a, x + 4, y + 5, col)
    elif kind == "minimize":
        rect(a, x + 2, y + 6, 5, 1, col)
    elif kind == "shade":
        rect(a, x + 2, y + 2, 5, 1, col)
        rect(a, x + 2, y + 4, 5, 1, col)
    elif kind == "close":
        for i in range(5):
            px(a, x + 2 + i, y + 2 + i, col)
            px(a, x + 6 - i, y + 2 + i, col)

CLUTTER_SLOTS = [("O", 3, 8), ("A", 11, 7), ("I", 18, 7), ("D", 25, 8), ("V", 33, 7)]
CB = [("previous", 0, 23, 18, 16, 88), ("play", 23, 23, 18, 39, 88), ("pause", 46, 23, 18, 62, 88),
      ("stop", 69, 23, 18, 85, 88), ("next", 92, 22, 18, 108, 88)]
FONT_GRID = [
    list("abcdefghijklmnopqrstuvwxyz\"@") + [None, None, " "],
    list("0123456789") + ["…", ".", ":", "(", ")", "-", "'", "!", "_", "+", "\\", "/", "[", "]", "^", "&", "%",
                          ",", "=", "$", "#"],
    ["å", "ö", "ä", "?", "*"] + [None] * 26,
]
EQ_BANDS = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]
EQ_SLIDER_X = [21] + [78 + 18 * i for i in range(10)]
GEN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GEN_PLATE_Y = 2
def line_m(w, h, pts, width):
    img = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(img).line([(px_ * 4, py_ * 4) for px_, py_ in pts], fill=255, width=int(width * 4),
                             joint="curve")
    return np.asarray(img.resize((w, h), Image.BOX), dtype=np.float32) / 255


# ------------------------------------------------------------------------------------------
# Dot-matrix digits (9 x 13 cells): a 5x7 matrix on a 2px pitch, unlit dots showing as ghosts
# ------------------------------------------------------------------------------------------

DOT57 = {
    "0": G(".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": G("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": G(".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": G("#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."),
    "4": G("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": G("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": G("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": G("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": G(".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": G(".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    "-": G(".....", ".....", ".....", "#####", ".....", ".....", "....."),
    " ": G(".....", ".....", ".....", ".....", ".....", ".....", "....."),
}


def dot_char(a, ch, x, y, col=None):
    """A digit cell: lit dots in phosphor with half-lit bridges between lit neighbours (so it
    reads at 1x like a glowing matrix), every other dot a ghost. col=None draws only ghosts."""
    rect(a, x, y, 9, 13, VF_VFD)
    g = DOT57[ch]
    on = [[col is not None and g[r][c] == "#" for c in range(5)] for r in range(7)]
    half = lerp(VF_VFD, col, 0.45) if col else None
    for r in range(7):
        for c in range(5):
            if not on[r][c]:
                px(a, x + 2 * c, y + 2 * r, VF_GHOST_DIGIT)
                continue
            px(a, x + 2 * c, y + 2 * r, col)
            if c < 4 and on[r][c + 1]:
                px(a, x + 2 * c + 1, y + 2 * r, half)
            if r < 6 and on[r + 1][c]:
                px(a, x + 2 * c, y + 2 * r + 1, half)


# ------------------------------------------------------------------------------------------
# vfd: black gloss faceplate in a sculpted silver surround, one wide VFD window, teal segment
# bars capped in orange, a dot-matrix readout, orange outlined lozenges, translucent aqua keys,
# grey rubber keys and a lit rotary knob.
# ------------------------------------------------------------------------------------------

VF_VFD = (4, 10, 11)                 # the black glass
VF_TINY = dict(TINY, N=G("#..#", "##.#", "#.##", "#..#", "#..#"))
VF_GHOST = (16, 44, 41)              # unlit segments showing through the glass
VF_GHOST_DIGIT = (13, 36, 34)        # the time digits' unlit segments
VF_LABEL = (38, 134, 120)            # dim legends in the glass
VF_TEAL = (60, 242, 210)             # lit phosphor
VF_TEXT = (96, 248, 222)             # lit text (a touch whiter, for small dot-matrix sizes)
VF_ORANGE = (255, 138, 30)           # the amber-orange phosphor: caps, lozenges, indicators
VF_AMBER = (255, 186, 76)
VF_SEG = [(30, 186, 164), (60, 242, 210), (150, 255, 236)]   # bar segments, bottom to top
VF_GLOSS = [(34, 36, 38), (14, 15, 16), (6, 6, 7), (12, 13, 14)]
VF_SILVER = [(232, 234, 238), (176, 180, 186), (118, 122, 128), (162, 166, 172)]
VF_PALE = [(204, 242, 234), (142, 214, 200), (86, 170, 156)]  # translucent aqua key caps
VF_PALE_ON = [(232, 255, 250), (176, 242, 228), (116, 206, 188)]
VF_PALE_INK = (6, 44, 40)
VF_LED_OFF = (36, 70, 66)
VF_RUBBER = [(186, 188, 192), (146, 148, 154), (112, 114, 120)]
VF_RUBBER_DN = [(104, 106, 112), (124, 126, 132), (140, 142, 148)]
VF_PRINT = (172, 176, 184)
VF_WHITE = (236, 238, 242)

def vf_gloss(a, x, y, w, h, top=0, total=116, stops=None):
    for r in range(h):
        rect(a, x, y + r, w, 1, ramp(stops or VF_GLOSS, (top + r) / max(1, total - 1)))


# The playlist and gen windows are tiled pieces: their surround is straight (constant width and
# colour) and their gloss flat down the sides, fading in from the titlebar and out into the bottom
# bar, so the tiles repeat and the pieces meet without a step. The curve is the main window's and EQ's.
VF_STRAIGHT_W = 3.0
VF_STRAIGHT_SILVER = (196, 200, 206)
VF_FLAT = (10, 10, 13)
VF_GLOSS_TOP = [VF_GLOSS[0], VF_GLOSS[1], VF_FLAT]
VF_GLOSS_BOTTOM = [VF_FLAT, VF_GLOSS[2], VF_GLOSS[3]]


def vf_silver_sides(a, top=0, total=116, left=True, right=True, straight=False):
    """The sculpted silver surround down the sides: wider at top and bottom, waisted in the middle
    (or `straight`, for the tiled windows)."""
    h, w = a.shape[:2]
    for r in range(h):
        t = (top + r) / max(1, total - 1)
        sw = VF_STRAIGHT_W if straight else 2.2 + 3.0 * (1 - np.sin(np.pi * t)) ** 1.5
        for side in ((0,) if left else ()) + ((1,) if right else ()):
            m = np.zeros((1, w), np.float32)
            xs = np.arange(w) + 0.5
            if side == 0:
                m[0] = np.clip(sw - xs + 0.5, 0, 1)
            else:
                m[0] = np.clip(sw - (w - xs) + 0.5, 0, 1)
            col = VF_STRAIGHT_SILVER if straight else ramp(VF_SILVER, 0.15 + 0.7 * abs(t - 0.4))
            paint(a, 0, r, m, col)
            # the dark seam where silver meets the gloss
            edge = np.clip(1 - np.abs((xs if side == 0 else w - xs) - sw - 0.5), 0, 1)[None, :]
            paint(a, 0, r, edge, (4, 4, 6), 0.8)


def vf_vfd(a, x, y, w, h, r=3):
    paint(a, x, y, rr_m(w, h, 0, 0, w, h, r), (2, 2, 3))
    paint(a, x, y, rr_m(w, h, 1, 1, w - 1, h - 1, max(1, r - 1)), VF_VFD)
    rect(a, x + r, y + 1, w - 2 * r, 1, (18, 40, 38))


def vf_key(a, x, y, w, h, pressed=False, kind="rubber", r=None):
    """Rubber (grey pill), pale (the translucent blue preset keys) or silver."""
    r = (min(w, h) / 2 - 0.5) if r is None and kind == "rubber" else (2.0 if r is None else r)
    paint(a, x, y, rr_m(w, h, 0, 0.8, w, h, r), (0, 0, 0), 0.7)
    paint(a, x, y, rr_m(w, h, 0, 0, w, h - 0.8, r), (10, 10, 12))
    if kind == "rubber":
        stops = VF_RUBBER_DN if pressed else VF_RUBBER
    elif kind == "pale":
        stops = pressed if isinstance(pressed, list) else (VF_PALE_ON if pressed else VF_PALE)
    else:
        stops = [(150, 154, 160), (190, 194, 200), (220, 222, 226)] if pressed else VF_SILVER
    paint(a, x, y, rr_m(w, h, 1, 1, w - 1, h - 1.8, max(0.5, r - 1)), vgrad_arr(w, h, stops))
    if kind == "pale" and not pressed:
        paint(a, x, y, rr_m(w, h, 1.5, 1.5, w - 1.5, 1 + (h - 3) * 0.4, max(0.5, r - 1.5)), (255, 255, 255), 0.25)


def vf_caption(a, x, y, kind, lit=True, pressed=False):
    vf_key(a, x, y, 9, 9, pressed, "rubber", 2.0)
    caption_glyph(a, kind, x, y, (24, 24, 28) if lit else (80, 82, 88))


def italic_face(size):
    for name in ITALIC_FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def vf_italic(a, s, x, y, size, col, anchor="ls"):
    """Faceplate print: bold italic sans, anti-aliased into a. Returns the right edge."""
    h, w = a.shape[:2]
    m = Image.new("L", (w, h), 0)
    f = italic_face(size)
    d = ImageDraw.Draw(m)
    d.text((x, y), s, fill=255, font=f, anchor=anchor)
    paint(a, 0, 0, np.asarray(m, dtype=np.float32) / 255, col)
    return d.textbbox((x, y), s, font=f, anchor=anchor)[2]


def vf_titlebar(lit, which="main"):
    a = new(275, 14)
    vf_gloss(a, 0, 0, 275, 14, 0, 116)
    rect(a, 0, 0, 275, 1, VF_SILVER[0])
    rect(a, 0, 1, 275, 1, VF_SILVER[2])
    vf_silver_sides(a, 0, 116)
    dim = (96, 98, 104)
    if which == "main":
        end = vf_italic(a, OPT.title, 19, 11, 10, VF_WHITE if lit else dim)
        s = "SPECTRUM ANALYZER"
        if end + 8 <= 238 - text_w(VF_TINY, s):
            draw_text(a, VF_TINY, s, 238 - text_w(VF_TINY, s), 5, VF_PRINT if lit else dim)
        vf_caption(a, 244, 3, "minimize", lit)
        vf_caption(a, 254, 3, "shade", lit)
    else:
        s = "10-BAND GRAPHIC EQUALIZER  SPECTRUM ANALYZER"
        text_center(a, VF_TINY, s, 137, 5, VF_PRINT if lit else dim)
    vf_caption(a, 6, 3, "options", lit)
    vf_caption(a, 264, 3, "close", lit)
    return a


def vf_clutter(lit_letters):
    a = new(8, 43)
    vf_gloss(a, 0, 0, 8, 43, 22, 116)
    for letter, y, h in CLUTTER_SLOTS:
        on = letter in lit_letters
        vf_key(a, 0, y - 1, 8, h + 1, on, "pale", 1.5)
        draw_text(a, VF_TINY, letter, 3, y + (h - 5) // 2, VF_PALE_INK if not on else (0, 64, 56))
    return a


def vf_make_titlebar():
    a = new(344, 87)
    vf_gloss(a, 0, 0, 344, 87, 0, 87)
    lit, dim = vf_titlebar(True), vf_titlebar(False)
    a[0:14, 27:302] = lit
    a[15:29, 27:302] = dim
    a[29:43, 27:302] = lit
    a[42:56, 27:302] = dim
    for kind, sx, x in (("options", 6, 0), ("minimize", 244, 9), ("close", 264, 18)):
        a[0:9, x:x + 9] = lit[3:12, sx:sx + 9]
        c = lit[3:12, sx:sx + 9].copy()
        vf_caption(c, 0, 0, kind, True, pressed=True)
        a[9:18, x:x + 9] = c
    a[18:27, 0:9] = lit[3:12, 254:263]
    c = lit[3:12, 254:263].copy()
    vf_caption(c, 0, 0, "shade", True, pressed=True)
    a[18:27, 9:18] = c
    unlit, on = vf_clutter(""), vf_clutter("OAIDV")
    a[0:43, 304:312] = unlit
    a[0:43, 312:320] = unlit
    for (letter, y, h), sx, sy in zip(CLUTTER_SLOTS, [304, 312, 320, 328, 336], [47, 55, 62, 69, 77]):
        a[sy:sy + h, sx:sx + 8] = on[y:y + h]
    return a


def vf_lozenge(a, x, y, w, h, col, caption=None):
    """An orange outlined lozenge (hexagonal ends) round a readout, an optional caption on its top edge."""
    pts = [(x + 3, y), (x + w - 4, y), (x + w - 1, y + h / 2 - 0.5), (x + w - 4, y + h - 1), (x + 3, y + h - 1),
           (x, y + h / 2 - 0.5)]
    m = line_m(a.shape[1], a.shape[0], pts + [pts[0]], 1.0)
    paint(a, 0, 0, np.clip(m * 1.6, 0, 1), col)
    if caption:
        tw = text_w(VF_TINY, caption)
        cx = x + (w - tw) // 2
        rect(a, cx - 1, y - 2, tw + 2, 5, VF_VFD)
        draw_text(a, VF_TINY, caption, cx, y - 2, col)


def vf_chevron(a, x, y, h, col, point="left"):
    """The thin white bracket lines at the ends of the spectrum banks."""
    d = 3
    if point == "left":
        pts = [(x + d, y), (x, y + h / 2), (x + d, y + h)]
    else:
        pts = [(x, y), (x + d, y + h / 2), (x, y + h)]
    paint(a, 0, 0, np.clip(line_m(a.shape[1], a.shape[0], pts, 1.0) * 1.5, 0, 1), col)


def vf_knob(a, cx, cy, r):
    """A rotary knob with a lit ring: black knurled skirt, a thin phosphor ring, a satin cap and
    an orange pointer (the main window's About spot)."""
    x0, y0 = int(cx - r - 2), int(cy - r - 2)
    w = h = int(2 * r + 5)
    lx, ly = cx - x0, cy - y0
    paint(a, x0, y0, circle_m(w, h, lx, ly + 0.8, r + 0.3), (0, 0, 0), 0.8)
    paint(a, x0, y0, circle_m(w, h, lx, ly, r), vgrad_arr(w, h, VF_SILVER))
    paint(a, x0, y0, circle_m(w, h, lx, ly, r - 1.2), (10, 10, 12))
    X, Y = np.mgrid[0:h, 0:w][1] + 0.5, np.mgrid[0:h, 0:w][0] + 0.5
    ang = np.arctan2(Y - ly, X - lx)
    ridge = ((np.floor(ang / (2 * np.pi) * 24) % 2) == 0).astype(np.float32)
    paint(a, x0, y0, ring_m(w, h, lx, ly, r - 3.4, r - 1.4) * ridge, (54, 56, 60), 0.9)
    paint(a, x0, y0, ring_m(w, h, lx, ly, r - 4.6, r - 3.5), VF_TEAL, 0.95)
    cap = rgrad_arr(w, h, lx - 1.5, ly - 2, r, [(120, 124, 130), (62, 64, 70), (30, 31, 34)])
    paint(a, x0, y0, circle_m(w, h, lx, ly, r - 4.8), cap)
    paint(a, x0, y0, line_m(w, h, [(lx + 1.2, ly - 1.2), (lx + 3.6, ly - 3.6)], 1.2), VF_ORANGE)


def vf_make_main():
    a = new(275, 116)
    vf_gloss(a, 0, 0, 275, 116)
    vf_silver_sides(a)
    a[0:14, :] = vf_titlebar(True)
    a[22:65, 10:18] = vf_clutter("")
    vf_vfd(a, 20, 17, 248, 54)
    vf_display_furniture(a)
    # print below the window, the knob in the About spot
    draw_text(a, VF_TINY, "TRACK SEARCH", 16, 83, VF_PRINT)
    draw_text(a, VF_TINY, "AUTO STORE", 240 - text_w(VF_TINY, "AUTO STORE"), 83, VF_PRINT)
    vf_italic(a, "DIGITAL AUDIO", 137, 113, 8, VF_WHITE, anchor="ms")
    vf_knob(a, 259.5, 98.5, 10.5)
    return a


def vf_display_furniture(a):
    """The main window's VFD contents that never change: brackets, ghost digits, legends."""
    vf_chevron(a, 21, 42, 16, (200, 236, 228), "left")
    for x in (48, 60, 78, 90):
        dot_char(a, " ", x, 26)
    for c in range(5):
        px(a, 36 + 2 * c, 32, VF_GHOST_DIGIT)
    px(a, 73, 30, VF_TEAL)
    px(a, 73, 34, VF_TEAL)
    draw_text(a, VF_TINY, "ST TP TA AF PTY RDS", 24, 62, VF_LABEL)
    # right: the title row, lozenges round kbps / kHz
    for xx in range(110, 266, 2):
        px(a, xx, 37, VF_GHOST)
    vf_lozenge(a, 107, 40, 44, 14, VF_ORANGE)
    draw_text(a, VF_TINY, "KBPS", 129, 44, VF_ORANGE)
    vf_lozenge(a, 152, 40, 36, 14, VF_ORANGE)
    draw_text(a, VF_TINY, "KHZ", 170, 44, VF_ORANGE)
    draw_text(a, VF_TINY, "DSP", 191, 44, VF_LABEL)


def vf_make_cbuttons(main):
    a = new(136, 36)
    for kind, x, w, h, mx, my in CB + [("eject", 114, 22, 16, 136, 89)]:
        for pressed, y in ((False, 0), (True, h)):
            cell = main[my:my + h, mx:mx + w].copy()
            if kind == "eject":
                vf_key(cell, 0, 1, w - 1, h - 2, pressed, "silver", 3.0)
            else:
                vf_key(cell, 0, 1, w - 1, h - 2, pressed, "rubber")
            o = 1 if pressed else 0
            transport_icon(cell, kind, (w - 1) // 2, (h - 1) // 2 + o - (1 if kind == "eject" else 0),
                           (28, 28, 32) if not pressed else (20, 20, 24))
            a[y:y + h, x:x + w] = cell
    return a


def vf_make_shufrep(main):
    a = new(92, 85)
    vf_gloss(a, 0, 0, 92, 85, 40, 116)
    for row, (on, pressed) in enumerate([(False, False), (False, True), (True, False), (True, True)]):
        y = row * 15
        for x0, w, mx, label in ((0, 28, 210, "RPT"), (28, 47, 164, "RDM")):
            c = main[89:104, mx:mx + w].copy()
            vf_key(c, 0, 0, w - 1, 15, on or pressed, "pale", 2.5)
            o = 1 if pressed else 0
            tw = text_w(VF_TINY, label)
            tx = (w - 1 - tw - 4) // 2
            draw_text(c, VF_TINY, label, tx, 5 + o, VF_PALE_INK)
            rect(c, tx + tw + 2, 6 + o, 2, 3, VF_ORANGE if on else VF_LED_OFF)
            a[y:y + 15, x0:x0 + w] = c
    for x, label, pressed, mx in [(0, "EQ", False, 219), (23, "PL", False, 242), (46, "EQ", True, 219),
                                  (69, "PL", True, 242)]:
        for on, y in ((False, 61), (True, 73)):
            c = main[58:70, mx:mx + 23].copy()
            rect(c, 0, 0, 23, 12, VF_VFD)
            col = (VF_AMBER if pressed else VF_ORANGE) if on else (VF_LABEL if not pressed else (60, 150, 136))
            vf_lozenge(c, 0, 0, 22, 12, col)
            text_center(c, VF_TINY, label, 11, 4, VF_TEXT if on else VF_LABEL)
            a[y:y + 12, x:x + 23] = c
    return a


def vf_make_monoster():
    a = new(56, 24, VF_VFD)
    for y, lit in ((0, True), (12, False)):
        col = VF_TEXT if lit else VF_GHOST
        text_center(a, VF_TINY, "STEREO", 14, y + 3, col)
        text_center(a, VF_TINY, "MONO", 42, y + 3, col)
    return a


def vf_make_numbers(ex):
    """5x7 dot-matrix VFD digits; every unlit dot shows as a ghost. nums_ex: the blank cell
    (all ghosts) and the minus."""
    a = new(108 if ex else 99, 13, VF_VFD)
    for n in range(10):
        dot_char(a, str(n), 9 * n, 0, VF_TEXT)
    if ex:
        dot_char(a, " ", 90, 0)
        dot_char(a, "-", 99, 0, VF_TEXT)
    return a


def vf_make_playpaus():
    a = new(48, 9, VF_VFD)
    tri_right(a, 2, 1, 7, VF_TEXT)
    rect(a, 9 + 2, 1, 2, 7, VF_TEXT)
    rect(a, 9 + 5, 1, 2, 7, VF_TEXT)
    rect(a, 18 + 2, 2, 5, 5, VF_TEXT)
    rect(a, 36, 0, 3, 9, VF_VFD)
    rect(a, 39 + 1, 3, 1, 3, VF_ORANGE)
    return a


def vf_make_text():
    """A character display's font: each 5x6 cell a 4x5 block of dots, the glyph lit (narrow
    glyphs centred) and every other dot a ghost, with a dark gap column and row between cells.
    The space cell is all ghosts, so the title box reads as a row of unlit character cells."""
    a = new(155, 18, VF_VFD)
    for row, chars in enumerate(FONT_GRID):
        for col, ch in enumerate(chars):
            if ch is None:
                continue
            x, y = col * 5, row * 6
            rect(a, x, y, 4, 5, VF_GHOST)
            if ch == " ":
                continue
            k = ch if ch in FONT5 else ch.upper()
            draw_text(a, FONT5, k, x + max(0, (4 - glyph_w(FONT5, k)) // 2), y, VF_TEXT)
    return a


def vf_make_posbar(main):
    a = new(307, 10)
    a[0:10, 0:248] = main[72:82, 16:264]
    rect(a, 0, 3, 248, 1, (2, 2, 3))
    rect(a, 0, 4, 248, 2, (24, 24, 28))
    rect(a, 0, 6, 248, 1, (96, 98, 104))
    for x, pressed in ((248, False), (278, True)):
        a[0:10, x:x + 29] = a[0:10, 100:129]
        vf_key(a, x + 7, 0, 15, 10, pressed, "silver", 2.0)
        rect(a, x + 14, 2, 1, 6, VF_ORANGE if pressed else (90, 92, 98))
    return a


def vf_bar(a, x, ybot, hgt, lit, cap):
    """One spectrum column: 1px dashes, 3px wide, every other row; orange cap when lit."""
    for k in range(hgt):
        yy = ybot - 2 * k
        if lit is None:
            col = VF_GHOST
        elif k < lit:
            col = VF_ORANGE if (cap and k == lit - 1) else ramp(VF_SEG, k / max(1, hgt - 1))
        else:
            col = VF_GHOST
        rect(a, x, yy, 3, 1, col)


def vf_thumb(a, x, y, pressed):
    rect(a, x, y, 14, 11, VF_VFD)
    col = VF_AMBER if pressed else VF_ORANGE
    vf_lozenge(a, x + 1, y + 1, 12, 9, col)
    rect(a, x + 5, y + 4, 4, 3, col)


def vf_make_volume(main):
    a = new(68, 433, VF_VFD)
    n = 16
    for i in range(28):
        y = i * 15
        lit = round((i + 1) / 28 * n)
        for k in range(n):
            hgt = 2 + round(3 * k / (n - 1))
            vf_bar(a, 3 + 4 * k, y + 11, hgt, hgt if k < lit else 0, k == lit - 1)
    vf_thumb(a, 0, 422, True)
    vf_thumb(a, 15, 422, False)
    return a


def vf_make_balance(main):
    a = new(68, 433, VF_VFD)
    for i in range(28):
        y = i * 15
        reach = round(4 * i / 27)
        for k in range(4):
            for bx in (30 + 4 * k, 23 - 4 * k):
                hgt = 2 + k
                vf_bar(a, bx, y + 11, hgt, hgt if k < reach else 0, k == reach - 1)
        rect(a, 27, y + 2, 1, 10, VF_ORANGE)
    vf_thumb(a, 0, 422, True)
    vf_thumb(a, 15, 422, False)
    return a


def vf_eq_frame(n):
    a = new(14, 63, VF_VFD)
    v = n / 27
    centre = round((1 - v) * 51) + 5
    segs = 29
    for k in range(segs):
        yy = 60 - 2 * k
        on = yy >= centre
        top = on and (yy - 2 < centre)
        col = (VF_ORANGE if top else ramp(VF_SEG, k / (segs - 1))) if on else VF_GHOST
        rect(a, 3, yy, 8, 1, col)
    return a


def vf_eq_thumb(pressed):
    a = new(11, 11, VF_VFD)
    col = VF_AMBER if pressed else VF_ORANGE
    rect(a, 0, 3, 11, 1, col)
    rect(a, 0, 7, 11, 1, col)
    rect(a, 0, 3, 1, 5, col)
    rect(a, 10, 3, 1, 5, col)
    rect(a, 3, 5, 5, 1, (255, 240, 200))
    return a


def vf_eq_body():
    a = new(275, 116)
    vf_gloss(a, 0, 0, 275, 116)
    vf_silver_sides(a)
    a[0:14, :] = vf_titlebar(True, "eq")
    vf_vfd(a, 84, 15, 117, 23, 2)
    vf_vfd(a, 9, 36, 257, 77)
    vf_chevron(a, 12, 40, 58, (200, 236, 228), "left")
    vf_chevron(a, 259, 40, 58, (200, 236, 228), "right")
    for lbl, yy in (("+12", 41), ("0", 66), ("-12", 92)):
        text_center(a, VF_TINY, lbl, 59, yy, VF_ORANGE)
    for xx in EQ_SLIDER_X:
        a[38:101, xx:xx + 14] = vf_eq_frame(14)
    text_center(a, VF_TINY, "PREAMP", 28, 105, VF_LABEL)
    for i, lbl in enumerate(EQ_BANDS):
        text_center(a, VF_TINY, lbl, 78 + 18 * i + 7, 105, VF_LABEL)
    return a


def vf_make_eqmain():
    a = new(275, 315)
    vf_gloss(a, 0, 0, 275, 315, 0, 315)
    body = vf_eq_body()
    a[0:116, :] = body
    lit, dim = vf_titlebar(True, "eq"), vf_titlebar(False, "eq")
    c = lit[3:12, 264:273].copy()
    vf_caption(c, 0, 0, "close", True, pressed=True)
    a[125:134, 0:9] = c
    for x, label, on, pressed in [
        (10, "ON", False, False), (36, "AUTO", False, False), (69, "ON", True, False), (95, "AUTO", True, False),
        (128, "ON", False, True), (154, "AUTO", False, True), (187, "ON", True, True), (213, "AUTO", True, True),
    ]:
        w = 26 if label == "ON" else 32
        bx = 14 if label == "ON" else 40
        c = body[18:30, bx:bx + w].copy()
        vf_key(c, 0, 0, w - 1, 12, on or pressed, "pale", 2.0)
        tw = text_w(VF_TINY, label)
        tx = (w - 1 - tw - 4) // 2
        draw_text(c, VF_TINY, label, tx, 3 + (1 if pressed else 0), VF_PALE_INK)
        rect(c, tx + tw + 2, 4 + (1 if pressed else 0), 2, 3, VF_ORANGE if on else VF_LED_OFF)
        a[119:131, x:x + w] = c
    a[134:148, :] = lit
    a[149:163, :] = dim
    a[164:175, 0:11] = vf_eq_thumb(False)
    a[176:187, 0:11] = vf_eq_thumb(True)
    for n in range(28):
        x, y = 13 + (n % 14) * 15, 164 + (n // 14) * 65
        a[y:y + 63, x:x + 14] = vf_eq_frame(n)
    for y, pressed in ((164, False), (176, True)):
        c = body[18:30, 217:261].copy()
        vf_key(c, 0, 0, 44, 12, pressed, "pale", 2.0)
        text_center(c, VF_TINY, "PRESETS", 22, 3 + (1 if pressed else 0), VF_PALE_INK)
        a[y:y + 12, 224:268] = c
    rect(a, 0, 294, 113, 19, VF_VFD)
    for x in range(0, 113, 2):
        px(a, x, 294 + 9, VF_GHOST)
    for r in range(19):
        px(a, 115, 294 + r, ramp([VF_AMBER, VF_ORANGE, VF_ORANGE, VF_AMBER], r / 18))
    for x in range(113):
        px(a, x, 314, VF_TEAL if x % 3 != 2 else VF_VFD)
    return a


def vf_bar_piece(w, h, top=0, total=116, left=False, right=False, stops=None):
    """A piece of chrome; `stops` (a gloss ramp) makes it a tiled window's, with straight sides."""
    a = new(w, h)
    vf_gloss(a, 0, 0, w, h, top, total, stops)
    if left or right:
        vf_silver_sides(a, top, total, left, right, straight=stops is not None)
    return a


def vf_tbar(w, h, **kw):
    """Tiled windows: titlebar piece, its gloss fading to the flat sides."""
    return vf_bar_piece(w, h, 0, h, stops=VF_GLOSS_TOP, **kw)


def vf_side(w, h, **kw):
    return vf_bar_piece(w, h, 0, h, stops=[VF_FLAT], **kw)


def vf_bottom(w, h, **kw):
    return vf_bar_piece(w, h, 0, h, stops=VF_GLOSS_BOTTOM, **kw)


def vf_plate(a, x, y, w, h=11):
    rect(a, x, y, w, h, (2, 2, 3))
    rect(a, x, y + 1, w, h - 2, VF_VFD)


def vf_make_pledit():
    a = new(280, 186)
    vf_gloss(a, 0, 0, 280, 186, 0, 186)
    for lit, y in ((True, 0), (False, 21)):
        def top(t):
            rect(t, 0, 0, t.shape[1], 1, VF_SILVER[0])
            rect(t, 0, 1, t.shape[1], 1, VF_SILVER[2])
            return t
        t = top(vf_tbar(25, 20))
        a[y:y + 20, 127:152] = t
        t = top(vf_tbar(25, 20, left=True))
        a[y:y + 20, 0:25] = t
        t = top(vf_tbar(100, 20))
        vf_plate(t, 2, 5, 96)
        text_center(t, FONT5, "PLAYLIST", 50, 8, VF_TEXT if lit else (40, 96, 88))
        a[y:y + 20, 26:126] = t
        t = top(vf_tbar(25, 20, right=True))
        vf_caption(t, 14, 3, "close", lit)
        rect(t, 9, 14, 10, 6, (24, 24, 28))
        a[y:y + 20, 153:178] = t
    a[42:71, 0:12] = vf_side(12, 29, left=True)
    t = vf_side(20, 29, right=True)
    rect(t, 4, 0, 10, 29, (24, 24, 28))
    rect(t, 4, 0, 1, 29, (2, 2, 3))
    a[42:71, 31:51] = t
    c = a[3:12, 167:176].copy()
    vf_caption(c, 0, 0, "close", True, pressed=True)
    a[42:51, 52:61] = c
    for x, pressed in ((52, False), (61, True)):
        hnd = new(8, 18, (24, 24, 28))
        vf_key(hnd, 0, 0, 8, 18, pressed, "pale", 1.5)
        a[53:71, x:x + 8] = hnd

    def bottom_base(w, left=False, right=False):
        return vf_bottom(w, 38, left=left, right=right)

    t = bottom_base(125, left=True)
    # the tape door: a smoked window in a silver rim
    paint(t, 8, 3, rr_m(117, 33, 0, 0, 117, 33, 3), VF_SILVER[2])
    paint(t, 8, 3, rr_m(117, 33, 1, 1, 116, 32, 2), vgrad_arr(117, 33, [(52, 54, 60), (28, 29, 33), (36, 38, 42)]))
    for bx, lbl in ((14, "ADD"), (43, "REM"), (72, "SEL"), (101, "MISC")):
        vf_key(t, bx, 8, 22, 15, False, "rubber", 4.0)
        text_center(t, VF_TINY, lbl, bx + 11, 13, (28, 28, 32))
    text_center(t, VF_TINY, "AUTO REVERSE CASSETTE DECK", 68, 27, VF_PRINT)
    a[72:110, 0:125] = t
    t = bottom_base(150, right=True)
    vf_plate(t, 5, 8, 58, 10)
    for k, kind in enumerate(["previous", "play", "pause", "stop", "next", "eject"]):
        bx = 3 + 10 * k
        vf_key(t, bx, 22, 10, 10, False, "rubber", 2.0)
        mini_transport_icon(t, kind, bx, 22, (28, 28, 32))
    vf_plate(t, 64, 21, 35, 10)
    rect(t, 84, 24, 1, 1, VF_TEXT)
    rect(t, 84, 27, 1, 1, VF_TEXT)
    vf_key(t, 106, 8, 22, 15, False, "rubber", 4.0)
    text_center(t, VF_TINY, "LIST", 117, 13, (28, 28, 32))
    for k in range(4):
        for j in range(k + 1):
            px(t, 141 - 3 * k + 3 * j, 29 - 3 * j, VF_PRINT)
    a[72:110, 126:276] = t
    a[0:38, 179:204] = bottom_base(25)
    return a


def vf_make_gen():
    a = new(194, 109)
    vf_gloss(a, 0, 0, 194, 109, 0, 109)
    for lit, y in ((True, 0), (False, 21)):
        for px0 in (0, 26, 52, 78, 104, 130):
            t = vf_tbar(25, 20, left=px0 == 0, right=px0 == 130)
            rect(t, 0, 0, 25, 1, VF_SILVER[0])
            rect(t, 0, 1, 25, 1, VF_SILVER[2])
            if px0 == 26:
                vf_plate(t, 21, 2, 4, 11)
                rect(t, 20, 2, 1, 11, (2, 2, 3))
            elif px0 == 52:
                vf_plate(t, 0, 2, 25, 11)
            elif px0 == 78:
                vf_plate(t, 0, 2, 4, 11)
                rect(t, 4, 2, 1, 11, (2, 2, 3))
            elif px0 == 130:
                vf_caption(t, 14, 3, "close", lit)
            a[y:y + 20, px0:px0 + 25] = t

    def bottom(w, grip, left):
        t = vf_bottom(w, 14, left=left, right=not left)
        rect(t, 0, 12, w, 1, VF_SILVER[2])
        rect(t, 0, 13, w, 1, VF_SILVER[0])
        if grip:
            for k in range(3):
                for j in range(k + 1):
                    px(t, w - 7 - 3 * k + 3 * j, 9 - 3 * j, VF_PRINT)
        return t

    a[42:56, 0:125] = bottom(125, False, True)
    a[57:71, 0:125] = bottom(125, True, False)
    t = vf_bottom(25, 14)
    rect(t, 0, 12, 25, 1, VF_SILVER[2])
    rect(t, 0, 13, 25, 1, VF_SILVER[0])
    a[72:86, 127:152] = t
    for x, w, h, left in ((127, 11, 29, True), (158, 11, 24, True), (139, 8, 29, False), (170, 8, 24, False)):
        a[42:42 + h, x:x + w] = vf_side(w, h, left=left, right=not left)
    c = a[3:12, 144:153].copy()
    vf_caption(c, 0, 0, "close", True, pressed=True)
    a[42:51, 148:157] = c
    for lit, y in ((True, 88), (False, 96)):
        rect(a, 0, y, 194, 7, SEP)
        x = 1
        for ch in GEN_LETTERS:
            w = glyph_w(FONT5, ch) + 1
            rect(a, x, y, w, 7, VF_VFD)
            draw_text(a, FONT5, ch, x, y + 1, VF_TEXT if lit else (40, 96, 88))
            x += w + 1
        assert x <= 194, x
    return a


def vf_make_genex():
    a = new(256, 64)
    vf_gloss(a, 0, 0, 256, 64, 0, 64)
    cols = [VF_VFD, VF_TEAL, (20, 21, 23), (28, 29, 31), (200, 236, 228), (36, 90, 84),
            (14, 70, 64), (34, 35, 38), VF_ORANGE, (90, 92, 98), (0, 0, 0), VF_ORANGE,
            (20, 21, 23), (40, 41, 44), (130, 230, 212), (60, 62, 66), VF_AMBER, (12, 12, 14)]
    rect(a, 0, 0, 256, 1, (20, 20, 24))
    for i, c in enumerate(cols):
        px(a, 48 + 2 * i, 0, c)
    vf_key(a, 0, 1, 47, 15, False, "rubber", 5.0)
    vf_key(a, 0, 16, 47, 15, True, "rubber", 5.0)
    return a

# ------------------------------------------------------------------------------------------
# vfd-silver: the same unit on a satin silver faceplate: the keys sit on the silver (darker
# bevels down the sides) and only the display sections are VFD glass, sharing the vf_* VFD
# sprites (digits, text, analyzer, EQ columns, lozenges). The silver varies vertically only (fine
# horizontal brush streaks on the main window and EQ), and the tiled playlist and gen pieces have
# straight sides of constant columns, so their tiles repeat cleanly.
# ------------------------------------------------------------------------------------------

SV_SATIN = [(234, 237, 241), (218, 222, 228), (204, 208, 215), (192, 196, 204), (180, 184, 193)]
SV_FLAT = (206, 210, 217)          # the tiled windows' silver where the sides run
SV_BEVEL = [(156, 161, 171), (132, 137, 147)]
SV_EDGE = (74, 78, 86)
SV_HI = (248, 249, 251)
SV_SHADOW = (122, 126, 135)
SV_INK = (24, 26, 32)              # print on the silver
SV_PRINT = (66, 70, 80)            # smaller print
SV_DIM = (138, 142, 151)           # unlit titlebar print
SV_RIM = (10, 10, 13)              # black gloss rim of a glass window
SV_GROOVE = (40, 42, 49)
SV_SMOKE = [(66, 70, 80), (34, 36, 42), (48, 52, 60)]
SV_LED_OFF = (92, 96, 104)
SV_STREAK = [int(v) for v in np.random.default_rng(5655).integers(-2, 3, 97)]
SV_TBAR = [SV_SATIN[0], SV_SATIN[1], SV_FLAT]
SV_BOTTOM = [SV_FLAT, SV_SATIN[3], SV_SATIN[4]]


def sv_satin(a, x, y, w, h, top=0, total=116, stops=None, streaks=True):
    """Satin silver, lighter at the top; `streaks` adds faint horizontal brush lines."""
    for r in range(h):
        c = ramp(stops or SV_SATIN, (top + r) / max(1, total - 1))
        s = SV_STREAK[(top + r) % len(SV_STREAK)] if streaks else 0
        rect(a, x, y + r, w, 1, tuple(v + s for v in c))


def sv_sides(a, top=0, total=116, left=True, right=True):
    """The darker silver bevels down the sides, waisted in the middle (main window and EQ)."""
    h, w = a.shape[:2]
    xs = np.arange(w) + 0.5
    for r in range(h):
        t = (top + r) / max(1, total - 1)
        sw = 3.0 + 3.0 * (1 - np.sin(np.pi * t)) ** 1.5
        col = ramp(SV_BEVEL, min(1.0, abs(t - 0.4) * 1.6))
        for side in ((0,) if left else ()) + ((1,) if right else ()):
            d = xs if side == 0 else w - xs
            paint(a, 0, r, np.clip(sw - d + 0.5, 0, 1)[None, :], col)
            paint(a, 0, r, np.clip(1 - np.abs(d - sw - 0.5), 0, 1)[None, :], SV_HI, 0.9)
            paint(a, 0, r, (d < 1).astype(np.float32)[None, :], SV_EDGE)


def sv_frame_edges(a):
    """Top and bottom outer edges of a whole window body."""
    w = a.shape[1]
    rect(a, 0, 0, w, 1, SV_EDGE)
    rect(a, 1, 1, w - 2, 1, SV_HI)
    rect(a, 1, a.shape[0] - 2, w - 2, 1, SV_SHADOW)
    rect(a, 0, a.shape[0] - 1, w, 1, SV_EDGE)


def sv_glass(a, rects, r=3, top_line=True):
    """A recessed VFD window (the union of `rects`, x y w h): shadowed silver lip, black gloss rim,
    the dark violet-black glass."""
    h, w = a.shape[:2]

    def union(inset, rr):
        m = np.zeros((h, w), np.float32)
        for (x, y, ww, hh) in rects:
            m = np.maximum(m, rr_m(w, h, x + inset, y + inset, x + ww - inset, y + hh - inset, max(0.5, rr)))
        return m
    paint(a, 0, 1, union(-1, r + 1), SV_HI, 0.9)
    paint(a, 0, -1, union(-1, r + 1), SV_SHADOW)
    paint(a, 0, 0, union(-1, r + 1), lerp(SV_SHADOW, SV_EDGE, 0.4))
    paint(a, 0, 0, union(0, r), SV_RIM)
    paint(a, 0, 0, union(1, r - 1), VF_VFD)
    if top_line:
        x, y, ww, hh = rects[0]
        rect(a, x + r, y + 1, ww - 2 * r, 1, (18, 40, 38))


def sv_key_label(a, s, cx, y, col=SV_INK):
    text_center(a, VF_TINY, s, cx, y, col)


def sv_knob(a, cx, cy, r):
    x0, y0 = int(cx - r - 3), int(cy - r - 3)
    w = h = int(2 * r + 7)
    paint(a, x0, y0, circle_m(w, h, cx - x0, cy - y0 + 0.6, r + 1.2), SV_EDGE, 0.9)
    paint(a, x0, y0, circle_m(w, h, cx - x0, cy - y0 + 1.4, r + 1.0), SV_HI, 0.5)
    vf_knob(a, cx, cy, r)


def sv_titlebar(lit, which="main"):
    a = new(275, 14)
    sv_satin(a, 0, 0, 275, 14, 0, 116)
    sv_sides(a, 0, 116)
    rect(a, 0, 0, 275, 1, SV_EDGE)
    rect(a, 1, 1, 273, 1, SV_HI)
    ink = SV_INK if lit else SV_DIM
    if which == "main":
        end = vf_italic(a, OPT.title, 19, 11, 10, ink)
        s = "SPECTRUM ANALYZER"
        if end + 8 <= 238 - text_w(VF_TINY, s):
            draw_text(a, VF_TINY, s, 238 - text_w(VF_TINY, s), 5, SV_PRINT if lit else SV_DIM)
        sv_caption(a, 244, 3, "minimize", lit)
        sv_caption(a, 254, 3, "shade", lit)
    else:
        s = "10-BAND GRAPHIC EQUALIZER WITH SPECTRUM ANALYZER"
        text_center(a, VF_TINY, s, 137, 5, SV_PRINT if lit else SV_DIM)
    sv_caption(a, 6, 3, "options", lit)
    sv_caption(a, 264, 3, "close", lit)
    return a


def sv_caption(a, x, y, kind, lit=True, pressed=False):
    vf_key(a, x, y, 9, 9, pressed, "rubber", 2.0)
    caption_glyph(a, kind, x, y, (20, 20, 24) if lit else (96, 98, 104))


def sv_clutter(lit_letters):
    a = new(8, 43)
    sv_satin(a, 0, 0, 8, 43, 22, 116)
    for letter, y, h in CLUTTER_SLOTS:
        on = letter in lit_letters
        vf_key(a, 0, y - 1, 8, h + 1, on, "pale", 1.5)
        draw_text(a, VF_TINY, letter, 3, y + (h - 5) // 2, VF_PALE_INK if not on else (0, 64, 56))
    return a


def sv_make_titlebar():
    a = new(344, 87)
    sv_satin(a, 0, 0, 344, 87, 0, 87, streaks=False)
    lit, dim = sv_titlebar(True), sv_titlebar(False)
    a[0:14, 27:302] = lit
    a[15:29, 27:302] = dim
    a[29:43, 27:302] = lit
    a[42:56, 27:302] = dim
    for kind, sx, x in (("options", 6, 0), ("minimize", 244, 9), ("close", 264, 18)):
        a[0:9, x:x + 9] = lit[3:12, sx:sx + 9]
        c = lit[3:12, sx:sx + 9].copy()
        sv_caption(c, 0, 0, kind, True, pressed=True)
        a[9:18, x:x + 9] = c
    a[18:27, 0:9] = lit[3:12, 254:263]
    c = lit[3:12, 254:263].copy()
    sv_caption(c, 0, 0, "shade", True, pressed=True)
    a[18:27, 9:18] = c
    unlit, on = sv_clutter(""), sv_clutter("OAIDV")
    a[0:43, 304:312] = unlit
    a[0:43, 312:320] = unlit
    for (letter, y, h), sx, sy in zip(CLUTTER_SLOTS, [304, 312, 320, 328, 336], [47, 55, 62, 69, 77]):
        a[sy:sy + h, sx:sx + 8] = on[y:y + h]
    return a


# the main window's VFD: the right part (title, kbps / kHz, stereo) and the deeper left bank
# (time, analyzer), one window
SV_GLASS_MAIN = [(20, 17, 248, 40), (20, 17, 86, 48)]


def sv_make_main():
    a = new(275, 116)
    sv_satin(a, 0, 0, 275, 116)
    sv_sides(a)
    sv_frame_edges(a)
    a[0:14, :] = sv_titlebar(True)
    a[22:65, 10:18] = sv_clutter("")
    sv_glass(a, SV_GLASS_MAIN)
    vf_display_furniture(a)
    rect(a, 20, 62, 86, 5, VF_VFD)       # the RDS legends don't fit this shallower bank
    # print on the silver
    draw_text(a, VF_TINY, "AUTO STORE", 240 - text_w(VF_TINY, "AUTO STORE"), 83, SV_PRINT)
    vf_italic(a, "DIGITAL AUDIO", 127, 113, 8, SV_INK, anchor="ms")
    sv_knob(a, 259.5, 98.5, 10.5)
    return a


def sv_make_shufrep(main):
    a = vf_make_shufrep(main)
    for x, label, pressed, mx in [(0, "EQ", False, 219), (23, "PL", False, 242), (46, "EQ", True, 219),
                                  (69, "PL", True, 242)]:
        for on, y in ((False, 61), (True, 73)):
            c = main[58:70, mx:mx + 23].copy()
            vf_key(c, 0, 0, 22, 12, pressed, "rubber", 2.5)
            o = 1 if pressed else 0
            draw_text(c, VF_TINY, label, 5, 3 + o, SV_INK)
            rect(c, 14, 4 + o, 3, 3, VF_ORANGE if on else SV_LED_OFF)
            a[y:y + 12, x:x + 23] = c
    return a


def sv_track(a, x, y, w):
    """A dark recessed slot in the silver, 3px deep, at rows y .. y+2."""
    rect(a, x, y - 1, w, 1, SV_SHADOW)
    rect(a, x, y, w, 3, SV_GROOVE)
    rect(a, x, y, w, 1, (22, 23, 28))
    rect(a, x, y + 3, w, 1, SV_HI)


def sv_thumb(a, x, y, w, h, pressed):
    vf_key(a, x, y, w, h, pressed, "silver", 2.0)
    rect(a, x + w // 2 - 1, y + 2, 2, h - 4, VF_ORANGE if pressed else SV_INK)


def sv_make_posbar(main):
    a = new(307, 10)
    a[0:10, 0:248] = main[72:82, 16:264]
    sv_track(a, 1, 4, 246)
    for x, pressed in ((248, False), (278, True)):
        a[0:10, x:x + 29] = a[0:10, 100:129]
        sv_thumb(a, x + 7, 0, 15, 10, pressed)
    return a


def sv_segs(a, x0, y, n, lit, rev=False):
    """VFD-like lit segments inside a track: n cells, 2px every 3px; `lit` from the start."""
    for k in range(n):
        xx = x0 - 3 * k - 1 if rev else x0 + 3 * k
        if k < lit:
            col = VF_ORANGE if k == lit - 1 else ramp(VF_SEG, k / max(1, n - 1))
        else:
            col = (24, 58, 54)
        rect(a, xx, y, 2, 2, col)


def sv_make_volume(main):
    a = new(68, 433)
    sv_satin(a, 0, 0, 68, 433, 57, 116, streaks=False)
    n = 20
    for i in range(28):
        y = i * 15
        a[y:y + 13, :] = main[57:70, 107:175]
        sv_track(a, 2, y + 5, 64)
        sv_segs(a, 4, y + 6, n, round(i / 27 * n))
    c = main[58:69, 107:121].copy()
    for x, pressed in ((0, True), (15, False)):
        t = c.copy()
        sv_thumb(t, 0, 0, 14, 11, pressed)
        a[422:433, x:x + 14] = t
    return a


def sv_make_balance(main):
    a = new(68, 433)
    sv_satin(a, 0, 0, 68, 433, 57, 116, streaks=False)
    for i in range(28):
        y = i * 15
        a[y:y + 13, 9:47] = main[57:70, 177:215]
        sv_track(a, 11, y + 5, 34)
        reach = round(5 * i / 27)
        sv_segs(a, 29, y + 6, 5, reach)
        sv_segs(a, 27, y + 6, 5, reach, rev=True)
        rect(a, 27, y + 4, 2, 5, VF_ORANGE if i == 0 else SV_INK)
    c = main[58:69, 177:191].copy()
    for x, pressed in ((0, True), (15, False)):
        t = c.copy()
        sv_thumb(t, 0, 0, 14, 11, pressed)
        a[422:433, x:x + 14] = t
    return a


SV_LABEL = (52, 170, 152)   # band labels in the EQ glass


def sv_eq_body():
    a = new(275, 116)
    sv_satin(a, 0, 0, 275, 116)
    sv_sides(a)
    sv_frame_edges(a)
    a[0:14, :] = sv_titlebar(True, "eq")
    sv_glass(a, [(84, 15, 117, 23), (13, 37, 249, 76)], 3, top_line=False)
    rect(a, 87, 16, 111, 1, (18, 40, 38))
    vf_chevron(a, 16, 41, 56, (200, 236, 228), "left")
    vf_chevron(a, 255, 41, 56, (200, 236, 228), "right")
    for lbl, yy in (("+12", 41), ("0", 66), ("-12", 92)):
        text_center(a, VF_TINY, lbl, 59, yy, VF_ORANGE)
    for xx in EQ_SLIDER_X:
        a[38:101, xx:xx + 14] = vf_eq_frame(14)
    text_center(a, VF_TINY, "PREAMP", 28, 104, SV_LABEL)
    for i, lbl in enumerate(EQ_BANDS):
        text_center(a, VF_TINY, lbl, 78 + 18 * i + 7, 104, SV_LABEL)
    return a


def sv_make_eqmain():
    a = new(275, 315)
    sv_satin(a, 0, 0, 275, 315, 0, 315, streaks=False)
    body = sv_eq_body()
    a[0:116, :] = body
    lit, dim = sv_titlebar(True, "eq"), sv_titlebar(False, "eq")
    c = lit[3:12, 264:273].copy()
    sv_caption(c, 0, 0, "close", True, pressed=True)
    a[125:134, 0:9] = c
    for x, label, on, pressed in [
        (10, "ON", False, False), (36, "AUTO", False, False), (69, "ON", True, False), (95, "AUTO", True, False),
        (128, "ON", False, True), (154, "AUTO", False, True), (187, "ON", True, True), (213, "AUTO", True, True),
    ]:
        w = 26 if label == "ON" else 32
        bx = 14 if label == "ON" else 40
        c = body[18:30, bx:bx + w].copy()
        vf_key(c, 0, 0, w - 1, 12, pressed, "pale", 2.0)
        tw = text_w(VF_TINY, label)
        tx = (w - 1 - tw - 4) // 2
        draw_text(c, VF_TINY, label, tx, 3 + (1 if pressed else 0), VF_PALE_INK)
        rect(c, tx + tw + 2, 4 + (1 if pressed else 0), 2, 3, VF_ORANGE if on else VF_LED_OFF)
        a[119:131, x:x + w] = c
    a[134:148, :] = lit
    a[149:163, :] = dim
    a[164:175, 0:11] = vf_eq_thumb(False)
    a[176:187, 0:11] = vf_eq_thumb(True)
    for n in range(28):
        x, y = 13 + (n % 14) * 15, 164 + (n // 14) * 65
        a[y:y + 63, x:x + 14] = vf_eq_frame(n)
    for y, pressed in ((164, False), (176, True)):
        c = body[18:30, 217:261].copy()
        vf_key(c, 0, 0, 44, 12, pressed, "pale", 2.0)
        text_center(c, VF_TINY, "PRESETS", 22, 3 + (1 if pressed else 0), VF_PALE_INK)
        a[y:y + 12, 224:268] = c
    rect(a, 0, 294, 113, 19, VF_VFD)
    for x in range(0, 113, 2):
        px(a, x, 294 + 9, VF_GHOST)
    for r in range(19):
        px(a, 115, 294 + r, ramp([VF_AMBER, VF_ORANGE, VF_ORANGE, VF_AMBER], r / 18))
    for x in range(113):
        px(a, x, 314, VF_TEAL if x % 3 != 2 else VF_VFD)
    return a


# Tiled windows: every side is a fixed list of column colours (outer edge first), the same in
# the side pieces and down the titlebar and bottom pieces, so the tiles meet without a step.
SV_PL_LEFT = [SV_EDGE] + [SV_BEVEL[0]] * 3 + [SV_HI] + [SV_FLAT] * 4 + [SV_SHADOW, (40, 40, 46), SV_RIM]
SV_PL_RIGHT = ([SV_RIM, (40, 40, 46), SV_FLAT, SV_FLAT, (70, 72, 80)] + [SV_GROOVE] * 8 + [SV_HI, SV_FLAT]
                + [SV_HI] + [SV_BEVEL[0]] * 3 + [SV_EDGE])
SV_GEN_LEFT = [SV_EDGE] + [SV_BEVEL[0]] * 3 + [SV_HI] + [SV_FLAT] * 2 + [SV_RIM] * 4
SV_GEN_RIGHT = [SV_RIM, SV_FLAT, SV_FLAT, SV_HI] + [SV_BEVEL[0]] * 3 + [SV_EDGE]


def sv_cols(a, x, cols, y0=0, y1=None):
    for k, c in enumerate(cols):
        rect(a, x + k, y0, 1, (a.shape[0] if y1 is None else y1) - y0, c)


def sv_outer(cols):
    """The outer part of a side (edge, bevel, highlight): it runs through every piece."""
    n = 0
    for c in (cols if cols[0] == SV_EDGE else cols[::-1]):
        n += 1
        if c == SV_HI:
            break
    return n


def sv_piece(w, h, kind, left=None, right=None):
    """A tiled-window piece: `kind` "top" (satin to flat), "side" (flat) or "bottom" (flat down
    to darker), with `left` / `right` the side's column list running its full height."""
    a = new(w, h)
    if kind == "side":
        rect(a, 0, 0, w, h, SV_FLAT)
    else:
        sv_satin(a, 0, 0, w, h, 0, h, SV_TBAR if kind == "top" else SV_BOTTOM, streaks=False)
    if left:
        sv_cols(a, 0, left if kind == "side" else left[:sv_outer(left)])
    if right:
        cols = right if kind == "side" else right[-sv_outer(right):]
        sv_cols(a, w - len(cols), cols)
    if kind == "top":
        rect(a, 0, 0, w, 1, SV_EDGE)
        rect(a, 1 if left else 0, 1, w - (1 if left else 0) - (1 if right else 0), 1, SV_HI)
    if kind == "bottom":
        rect(a, 0, h - 1, w, 1, SV_EDGE)
        rect(a, 1 if left else 0, h - 2, w - (1 if left else 0) - (1 if right else 0), 1, SV_SHADOW)
    return a


def sv_print_box(a, x0, x1, y0, y1, col, left=True, right=True):
    """A printed outline (silkscreen box) from x0 to x1 inclusive."""
    rect(a, x0, y0, x1 - x0 + 1, 1, col)
    rect(a, x0, y1, x1 - x0 + 1, 1, col)
    if left:
        rect(a, x0, y0, 1, y1 - y0 + 1, col)
    if right:
        rect(a, x1, y0, 1, y1 - y0 + 1, col)


def sv_make_pledit():
    a = new(280, 186)
    sv_satin(a, 0, 0, 280, 186, 0, 186, streaks=False)
    L, R = SV_PL_LEFT, SV_PL_RIGHT
    rim = [SV_SHADOW, (40, 40, 46), SV_RIM]       # the list's top edge, rows 17..19
    for lit, y in ((True, 0), (False, 21)):
        ink = SV_INK if lit else SV_DIM
        t = sv_piece(25, 20, "top")
        for k, c in enumerate(rim):
            rect(t, 0, 17 + k, 25, 1, c)
        a[y:y + 20, 127:152] = t
        t = sv_piece(25, 20, "top", left=L)
        for k, c in enumerate(rim):
            rect(t, 9 + k, 17 + k, 25 - 9 - k, 1, c)
        sv_cols(t, 9, L[9:], 17, 20)
        a[y:y + 20, 0:25] = t
        t = sv_piece(100, 20, "top")
        for k, c in enumerate(rim):
            rect(t, 0, 17 + k, 100, 1, c)
        sv_print_box(t, 18, 81, 3, 13, SV_PRINT if lit else SV_DIM)
        text_center(t, FONT5, "PLAYLIST", 50, 6, ink)
        a[y:y + 20, 26:126] = t
        t = sv_piece(25, 20, "top", right=R)
        for k, c in enumerate(rim):
            rect(t, 0, 17 + k, 5 + 2 - k, 1, c)
        sv_cols(t, 5, R[:3], 17, 20)
        sv_caption(t, 13, 3, "close", lit)
        a[y:y + 20, 153:178] = t
    a[42:71, 0:12] = sv_piece(12, 29, "side", left=L)
    a[42:71, 31:51] = sv_piece(20, 29, "side", right=R)
    c = a[3:12, 166:175].copy()
    sv_caption(c, 0, 0, "close", True, pressed=True)
    a[42:51, 52:61] = c
    for x, pressed in ((52, False), (61, True)):
        hnd = new(8, 18, SV_GROOVE)
        vf_key(hnd, 0, 0, 8, 18, pressed, "silver", 1.5)
        for k in range(3):
            rect(hnd, 2, 6 + 2 * k, 4, 1, SV_SHADOW)
        a[53:71, x:x + 8] = hnd

    def bottom_base(w, left=False, right=False, list_from=0, list_to=None):
        t = sv_piece(w, 38, "bottom", left=L if left else None, right=R if right else None)
        lt = w if list_to is None else list_to
        rect(t, list_from, 0, lt - list_from, 1, SV_RIM)
        rect(t, list_from, 1, lt - list_from, 1, (40, 40, 46))
        rect(t, list_from, 2, lt - list_from, 1, SV_HI)
        return t

    t = bottom_base(125, left=True, list_from=10)
    sv_cols(t, 10, L[10:], 0, 2)
    for bx, lbl in ((14, "ADD"), (43, "REM"), (72, "SEL"), (101, "MISC")):
        vf_key(t, bx, 6, 22, 15, False, "rubber", 4.0)
        sv_key_label(t, lbl, bx + 11, 11)
    # the tape door: a smoked slot
    paint(t, 12, 24, rr_m(112, 11, 0, 0, 112, 11, 2), SV_EDGE)
    paint(t, 12, 24, rr_m(112, 11, 1, 1, 111, 10, 1.5), vgrad_arr(112, 11, SV_SMOKE))
    rect(t, 14, 35, 108, 1, SV_HI)
    text_center(t, VF_TINY, "AUTO REVERSE CASSETTE DECK", 68, 27, (190, 196, 206))
    a[72:110, 0:125] = t
    t = bottom_base(150, right=True, list_to=130)
    sv_cols(t, 130, R[:2], 0, 2)
    sv_cols(t, 134, R[4:14], 0, 2)
    sv_glass(t, [(5, 8, 58, 10)], 1, top_line=False)
    for k, kind in enumerate(["previous", "play", "pause", "stop", "next", "eject"]):
        bx = 3 + 10 * k
        vf_key(t, bx, 22, 10, 10, False, "rubber", 2.0)
        mini_transport_icon(t, kind, bx, 22, (24, 24, 28))
    sv_glass(t, [(64, 21, 35, 10)], 1, top_line=False)
    rect(t, 84, 24, 1, 1, VF_TEXT)
    rect(t, 84, 27, 1, 1, VF_TEXT)
    vf_key(t, 106, 8, 22, 15, False, "rubber", 4.0)
    sv_key_label(t, "LIST", 117, 13)
    for k in range(4):
        for j in range(k + 1):
            px(t, 141 - 3 * k + 3 * j, 33 - 3 * j, SV_PRINT)
    a[72:110, 126:276] = t
    a[0:38, 179:204] = bottom_base(25)
    return a


def sv_make_gen():
    a = new(194, 109)
    sv_satin(a, 0, 0, 194, 109, 0, 109, streaks=False)
    L, R = SV_GEN_LEFT, SV_GEN_RIGHT
    for lit, y in ((True, 0), (False, 21)):
        box = SV_PRINT if lit else SV_DIM
        for px0 in (0, 26, 52, 78, 104, 130):
            t = sv_piece(25, 20, "top", left=L if px0 == 0 else None, right=R if px0 == 130 else None)
            # the art's black rim, rows 16..19
            x0 = 7 if px0 == 0 else 0
            x1 = 18 if px0 == 130 else 24
            rect(t, x0, 16, x1 - x0 + 1, 4, SV_RIM)
            if px0 == 26:
                sv_print_box(t, 20, 24, 2, 12, box, right=False)
            elif px0 == 52:
                sv_print_box(t, 0, 24, 2, 12, box, left=False, right=False)
            elif px0 == 78:
                sv_print_box(t, 0, 4, 2, 12, box, left=False)
            elif px0 == 130:
                sv_caption(t, 14, 3, "close", lit)
            a[y:y + 20, px0:px0 + 25] = t

    def bottom(w, left):
        t = sv_piece(w, 14, "bottom", left=L if left else None, right=None if left else R)
        if left:
            rect(t, 7, 0, w - 7, 4, SV_RIM)
        else:
            rect(t, 0, 0, w - 7, 4, SV_RIM)
        return t

    a[42:56, 0:125] = bottom(125, True)
    t = bottom(125, False)
    for k in range(3):
        for j in range(k + 1):
            px(t, 125 - 6 - 3 * k + 3 * j, 11 - 3 * j, SV_PRINT)
    a[57:71, 0:125] = t
    t = sv_piece(25, 14, "bottom")
    rect(t, 0, 0, 25, 4, SV_RIM)
    a[72:86, 127:152] = t
    for x, w, h, left in ((127, 11, 29, True), (158, 11, 24, True), (139, 8, 29, False), (170, 8, 24, False)):
        a[42:42 + h, x:x + w] = sv_piece(w, h, "side", left=L if left else None, right=None if left else R)
    c = a[3:12, 144:153].copy()
    sv_caption(c, 0, 0, "close", True, pressed=True)
    a[42:51, 148:157] = c
    # the title letters: printed on the silver, each cell the titlebar's own rows 4..10
    tb = sv_piece(25, 20, "top")
    for lit, y in ((True, 88), (False, 96)):
        rect(a, 0, y, 194, 7, SEP)
        x = 1
        for ch in GEN_LETTERS:
            w = glyph_w(FONT5, ch) + 1
            for r in range(7):
                rect(a, x, y + r, w, 1, tuple(int(v) for v in tb[4 + r, 10]))
            draw_text(a, FONT5, ch, x, y + 1, SV_INK if lit else SV_DIM)
            x += w + 1
        assert x <= 194, x
    return a


def sv_make_genex():
    a = new(256, 64)
    sv_satin(a, 0, 0, 256, 64, 0, 64, streaks=False)
    cols = [VF_VFD, VF_TEAL, (204, 208, 215), (24, 26, 32), (24, 26, 32), (40, 150, 136),
            (14, 70, 64), (180, 184, 193), (24, 26, 32), (236, 238, 242), (180, 184, 193), (112, 116, 124),
            (160, 164, 172), (196, 200, 206), (60, 62, 68), (110, 210, 192), (40, 42, 48), (122, 126, 135)]
    rect(a, 0, 0, 256, 1, (204, 208, 215))
    for i, c in enumerate(cols):
        px(a, 48 + 2 * i, 0, c)
    vf_key(a, 0, 1, 47, 15, False, "rubber", 5.0)
    vf_key(a, 0, 16, 47, 15, True, "rubber", 5.0)
    return a


VF_MAKERS = {
    "main.bmp": vf_make_main, "titlebar.bmp": vf_make_titlebar, "cbuttons.bmp": vf_make_cbuttons,
    "shufrep.bmp": vf_make_shufrep, "posbar.bmp": vf_make_posbar, "volume.bmp": vf_make_volume,
    "balance.bmp": vf_make_balance, "monoster.bmp": vf_make_monoster, "playpaus.bmp": vf_make_playpaus,
    "numbers.bmp": vf_make_numbers, "nums_ex.bmp": vf_make_numbers,
    "text.bmp": vf_make_text, "pledit.bmp": vf_make_pledit, "eqmain.bmp": vf_make_eqmain,
    "gen.bmp": vf_make_gen, "genex.bmp": vf_make_genex,
}

SV_MAKERS = dict(VF_MAKERS, **{
    "main.bmp": sv_make_main, "titlebar.bmp": sv_make_titlebar, "shufrep.bmp": sv_make_shufrep,
    "posbar.bmp": sv_make_posbar, "volume.bmp": sv_make_volume, "balance.bmp": sv_make_balance,
    "pledit.bmp": sv_make_pledit, "eqmain.bmp": sv_make_eqmain, "gen.bmp": sv_make_gen,
    "genex.bmp": sv_make_genex,
})


# ------------------------------------------------------------------------------------------
# Text files
# ------------------------------------------------------------------------------------------


def viscolor():
    rows = [(T.disp, "background"), (T.vis_dots, "dots")]
    rows += [(c, f"spectrum {i + 1}" + (" (top)" if i == 0 else "")) for i, c in enumerate(T.vis_rows)]
    osc = [T.vis[0], T.vis[1], T.vis[1], T.vis[2], T.vis[2]]
    rows += [(c, f"oscilloscope {i + 1}") for i, c in enumerate(osc)]
    rows += [(T.vis_peak, "peaks")]
    return rows


def readme_title():
    return wsz_name().replace("-", " ")


def write_text_files():
    with open(os.path.join(OUT, "viscolor.txt"), "w", newline="\r\n") as f:
        for (r, g, b), note in viscolor():
            f.write(f"{r},{g},{b}, // {note}\n")
    p = T.pledit
    with open(os.path.join(OUT, "pledit.txt"), "w", newline="\r\n") as f:
        f.write(f"[Text]\nNormal={p['Normal']}\nCurrent={p['Current']}\nNormalBG={p['NormalBG']}\n"
                f"SelectedBG={p['SelectedBG']}\nMbBG={p['NormalBG']}\nMbFG={p['Normal']}\n"
                f"Font={T.font}\n")
    text = (f"{readme_title()} - a vacuum fluorescent display head unit, {T.look}.\n"
            "\n"
            "A classic (Winamp 2.x format) skin: teal phosphor segments with dim ghosts of the\n"
            "unlit ones, amber-orange caps and indicators, dot-matrix time digits and\n"
            "spectrum-analyzer bars on black glass. Every bitmap was drawn by a script\n"
            "(gen_skin.py); nothing was taken from any other skin or product, and it carries\n"
            "no logos or marks.\n"
            "\n"
            "License: CC0 1.0 Universal (public domain dedication).\n")
    text.encode("ascii")
    with open(os.path.join(OUT, "readme.txt"), "w", newline="\r\n") as f:
        f.write(text)


# ------------------------------------------------------------------------------------------
# Build
# ------------------------------------------------------------------------------------------

SHEETS = {}


def save(a, name):
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
    img.save(os.path.join(OUT, name))
    return img


def build():
    over = SV_MAKERS if T.name == "vfd-silver" else VF_MAKERS
    main = over["main.bmp"]()
    sheets = {
        "main.bmp": main,
        "titlebar.bmp": over["titlebar.bmp"](),
        "cbuttons.bmp": over["cbuttons.bmp"](main),
        "shufrep.bmp": over["shufrep.bmp"](main),
        "posbar.bmp": over["posbar.bmp"](main),
        "volume.bmp": over["volume.bmp"](main),
        "balance.bmp": over["balance.bmp"](main),
        "monoster.bmp": over["monoster.bmp"](),
        "playpaus.bmp": over["playpaus.bmp"](),
        "numbers.bmp": over["numbers.bmp"](False),
        "nums_ex.bmp": over["nums_ex.bmp"](True),
        "text.bmp": over["text.bmp"](),
        "pledit.bmp": over["pledit.bmp"](),
        "eqmain.bmp": over["eqmain.bmp"](),
        "gen.bmp": over["gen.bmp"](),
        "genex.bmp": over["genex.bmp"](),
    }
    SHEETS.clear()
    for name, arr in sheets.items():
        SHEETS[name[:-4]] = save(arr, name)
    write_text_files()
    names = list(sheets) + ["pledit.txt", "viscolor.txt", "readme.txt"]
    wsz = os.path.join(OPT.out, wsz_name() + ".wsz")
    with zipfile.ZipFile(wsz, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(OUT, n), "rb") as fh:
                z.writestr(info, fh.read())
    # genex.bmp completed for real Winamp and WACUP: all 24 colours, readable text, and the
    # standard 112x59 button and scrollbar layout (skins/genex_wacup.py).
    genex_wacup.process(wsz)
    return wsz


# ------------------------------------------------------------------------------------------
# Preview: the windows put together from the sprites the way the app does
# ------------------------------------------------------------------------------------------


def blit(dst, sheet, r, dx, dy, w=None, sx=0):
    x, y, rw, rh = r
    w = rw if w is None else w
    dst.paste(sheet.crop((x + sx, y, x + sx + w, y + rh)), (dx, dy))


def stretch(dst, sheet, r, dx, dy, dw, dh):
    x, y, w, h = r
    dst.paste(sheet.crop((x, y, x + w, y + h)).resize((dw, dh), Image.NEAREST), (dx, dy))


FONT_LOOKUP = {}
for _row, _chars in enumerate(FONT_GRID):
    for _col, _ch in enumerate(_chars):
        if _ch is not None:
            FONT_LOOKUP[_ch] = (_row, _col)


def draw_bitmap_text(dst, s, x, y):
    text = SHEETS["text"]
    for ch in s:
        row, col = FONT_LOOKUP.get(ch.lower(), FONT_LOOKUP[" "])
        blit(dst, text, (col * 5, row * 6, 5, 6), x, y)
        x += 5


def tt_font(size):
    for p in LIST_FONTS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def preview_main(lit, state):
    S = SHEETS
    img = Image.new("RGB", (275, 116))
    img.paste(S["main"], (0, 0))
    blit(img, S["titlebar"], (27, 0 if lit else 15, 275, 14), 0, 0)
    cb = {"previous": (0, 23, 18), "play": (23, 23, 18), "pause": (46, 23, 18), "stop": (69, 23, 18),
          "next": (92, 22, 18)}
    pos = {"previous": (16, 88), "play": (39, 88), "pause": (62, 88), "stop": (85, 88), "next": (108, 88)}
    for k, (x, w, h) in cb.items():
        blit(img, S["cbuttons"], (x, 18 if state["pressed"] == k else 0, w, h), *pos[k])
    blit(img, S["cbuttons"], (114, 16 if state["pressed"] == "eject" else 0, 22, 16), 136, 89)
    for name, x0, on in (("eq", 0, state["eq"]), ("pl", 23, state["pl"])):
        pressed = state["pressed"] == name
        sx = x0 + (46 if pressed else 0)
        blit(img, S["shufrep"], (sx, 73 if on else 61, 23, 12), 219 + x0, 58)
    blit(img, S["titlebar"], (304, 0, 8, 43), 10, 22)
    spr = {"O": (304, 47, 8, 8, 3), "A": (312, 55, 8, 7, 11), "I": (320, 62, 8, 7, 18), "D": (328, 69, 8, 8, 25),
           "V": (336, 77, 8, 7, 33)}
    for L in state["clutter"]:
        x, y, w, h, oy = spr[L]
        blit(img, S["titlebar"], (x, y, w, h), 10, 22 + oy)
    for name, x0, w, on, dst in (("shuffle", 28, 47, state["shuffle"], 164), ("repeat", 0, 28, state["repeat"], 210)):
        row = (2 if on else 0) + (1 if state["pressed"] == name else 0)
        blit(img, S["shufrep"], (x0, row * 15, w, 15), dst, 89)
    blit(img, S["playpaus"], (0 if state["playing"] else 9, 0, 9, 9), 26, 28)
    blit(img, S["monoster"], (29, 12 if state["stereo"] else 0, 27, 12), 212, 41)
    blit(img, S["monoster"], (0, 0 if state["stereo"] else 12, 29, 12), 239, 41)
    blit(img, S["posbar"], (0, 0, 248, 10), 16, 72)
    tl = round(state["pos"] * 219)
    blit(img, S["posbar"], (278 if state["seek"] else 248, 0, 29, 10), 16 + tl, 72)
    v = state["volume"]
    idx = max(0, round(v / 100 * 28) - 1)
    blit(img, S["volume"], (0, idx * 15, 68, 13), 107, 57)
    blit(img, S["volume"], (0 if state["vdrag"] else 15, 422, 14, 11), 107 + round(v / 100 * 54), 58)
    b = state["balance"]
    idx = int(abs(b) / 100 * 27)
    blit(img, S["balance"], (9, idx * 15, 38, 13), 177, 57)
    blit(img, S["balance"], (15, 422, 14, 11), 177 + round((b + 100) / 200 * 24), 58)
    secs = state["time"]
    m, s = secs // 60, secs % 60
    nums = S["nums_ex"]
    if state["remaining"]:
        blit(img, nums, (99, 0, 9, 13), 36, 26)
    for d, x in ((m // 10, 48), (m % 10, 60), (s // 10, 78), (s % 10, 90)):
        blit(img, nums, (9 * d, 0, 9, 13), x, 26)
    # the title box blanked with text.bmp's space, then the title in pledit's font and colour
    for x in range(0, 154, 5):
        w = min(5, 154 - x)
        blit(img, S["text"], (150, 0, w, 6), 111 + x, 24)
    box = img.crop((111, 22, 265, 36))
    ImageDraw.Draw(box).text((0, 3 + 2 + 2), state["title"], fill=T.ink, font=tt_font(11),
                             anchor="lm")
    img.paste(box, (111, 22))
    draw_bitmap_text(img, "192", 111, 43)
    draw_bitmap_text(img, "44", 156, 43)
    cols = [c for c, _ in viscolor()]
    vis = Image.new("RGB", (76, 16))
    vp = vis.load()
    for y in range(16):
        for x in range(76):
            vp[x, y] = cols[1] if (y % 2 == 1 and x % 2 == 0) else cols[0]
    heights = state["bars"]
    for x in range(75):
        if x % 4 == 3:
            continue
        hgt = heights[x // 4] - 2
        for y in range(16 - hgt, 16):
            vp[x, y] = cols[min(17, max(2, y + 2))]
        pk = heights[x // 4] + 2
        if 0 <= 16 - pk < 16:
            vp[x, 16 - pk] = cols[23]
    img.paste(vis, (24, 43))
    return img


def preview_eq(lit, state):
    S = SHEETS
    sheet = S["eqmain"]
    img = Image.new("RGB", (275, 116))
    blit(img, sheet, (0, 0, 275, 116), 0, 0)
    blit(img, sheet, (0, 134 if lit else 149, 275, 14), 0, 0)
    if state["pressed"] == "close":
        blit(img, sheet, (0, 125, 9, 9), 264, 3)
    on, pressed = state["on"], state["pressed"] == "on"
    blit(img, sheet, ((187 if on else 128) if pressed else (69 if on else 10), 119, 26, 12), 14, 18)
    blit(img, sheet, ((95 if state["auto"] else 36), 119, 32, 12), 40, 18)
    blit(img, sheet, (224, 176 if state["pressed"] == "presets" else 164, 44, 12), 217, 18)

    def slider(x, value, drag):
        n = round(value / 100 * 27)
        blit(img, sheet, (13 + (n % 14) * 15, 164 + (n // 14) * 65, 14, 63), x, 38)
        ty = 38 + round((1 - value / 100) * 51)
        blit(img, sheet, (0, 176 if drag else 164, 11, 11), x + 1, ty)

    slider(21, state["preamp"], False)
    for i, v in enumerate(state["bands"]):
        slider(78 + 18 * i, v, state["drag"] == i)
    blit(img, sheet, (0, 294, 113, 19), 86, 17)
    py_ = round((100 - state["preamp"]) / 100 * 18)
    blit(img, sheet, (0, 314, 113, 1), 86, 17 + py_)
    ys = [(100 - v) / 100 * 18 for v in state["bands"]]
    last = round(ys[0])
    for x in range(0, 109):
        i = min(8, x // 12)
        t = (x - i * 12) / 12
        y = round(ys[i] + (ys[i + 1] - ys[i]) * (3 * t * t - 2 * t * t * t))
        y = max(0, min(18, y))
        top, h = min(y, last), 1 + abs(last - y)
        blit(img, sheet, (115, 294 + top, 1, h), 86 + 2 + x, 17 + top)
        last = y
    return img


def preview_playlist(lit, w, h, rows, pressed_close=False, drag=False):
    S = SHEETS
    sheet = S["pledit"]
    img = Image.new("RGB", (w, h))
    ty = 0 if lit else 21
    for x in range(25, w - 25, 25):
        blit(img, sheet, (127, ty, 25, 20), x, 0)
    blit(img, sheet, (0, ty, 25, 20), 0, 0)
    blit(img, sheet, (26, ty, 100, 20), (w - 100) // 2, 0)
    blit(img, sheet, (153, ty, 25, 20), w - 25, 0)
    for y in range(20, h - 38, 29):
        blit(img, sheet, (0, 42, 12, 29), 0, y)
        blit(img, sheet, (31, 42, 20, 29), w - 20, y)
    for x in range(125, w - 150, 25):
        blit(img, sheet, (179, 0, 25, 38), x, h - 38)
    blit(img, sheet, (0, 72, 125, 38), 0, h - 38)
    blit(img, sheet, (126, 72, 150, 38), w - 150, h - 38)
    if pressed_close:
        blit(img, sheet, (52, 42, 9, 9), w - 11, 3)
    d = ImageDraw.Draw(img)
    p = T.pledit
    lx, lw = 12, w - 32
    d.rectangle((lx, 20, lx + lw - 1, h - 39), fill=rgb(p["NormalBG"]))
    font = tt_font(11)
    for i, (txt, dur) in enumerate(rows):
        y = 23 + i * 15
        if y + 15 > h - 38:
            break
        if i == 2:
            d.rectangle((lx, y, lx + lw - 1, y + 14), fill=rgb(p["SelectedBG"]))
        col = rgb(p["Current"]) if i == 1 else rgb(p["Normal"])
        d.text((lx + 2, y + 1), f"{i + 1}. {txt}", fill=col, font=font)
        d.text((lx + lw - 3 - d.textlength(dur, font=font), y + 1), dur, fill=col, font=font)
    blit(img, sheet, (61 if drag else 52, 53, 8, 18), w - 15, 20 + 30)
    draw_bitmap_text(img, "3:27/41:10", w - 150 + 7, h - 38 + 10)
    for dx, ch in zip([1, 7, 12, 20, 25], " 0327"):
        draw_bitmap_text(img, ch, w - 150 + 66 + dx, h - 38 + 23)
    return img


def gen_letters():
    g = SHEETS["gen"]
    pxs = g.load()
    out = {}
    for state, y in (("focused", 88), ("unfocused", 96)):
        bg = pxs[0, y]
        letters, n, x = {}, 0, 1
        while x < g.width and n < 26:
            if pxs[x, y] == bg:
                x += 1
                continue
            start = x
            while x < g.width and pxs[x, y] != bg:
                x += 1
            letters[chr(65 + n)] = (start, x - start)
            n += 1
        assert n == 26, f"gen.bmp {state} letters: found {n}"
        out[state] = letters
    return out


def preview_gen(lit, w, h, title, pressed_close=False):
    g = SHEETS["gen"]
    L = gen_letters()
    st = "focused" if lit else "unfocused"
    ty = 0 if lit else 21
    img = Image.new("RGB", (w, h), (0, 0, 0))
    piece = lambda px0: (px0, ty, 25, 20)
    for tx in range(0, w, 25):
        blit(img, g, piece(104), tx, 0)
    text_wd = sum(L[st].get(c, (0, 5))[1] for c in title.upper())
    if text_wd + 100 <= w:
        tx = (w - text_wd) // 2
        for cx in range(tx, tx + text_wd, 25):
            blit(img, g, piece(52), cx, 0, min(25, tx + text_wd - cx))
        blit(img, g, piece(26), tx - 25, 0)
        blit(img, g, piece(78), tx + text_wd, 0)
        x = tx
        for c in title.upper():
            if c in L[st]:
                lx, lw = L[st][c]
                blit(img, g, (lx, 88 if lit else 96, lw, 7), x, 4)
                x += lw
            else:
                x += 5
    blit(img, g, piece(0), 0, 0)
    blit(img, g, piece(130), w - 25, 0)
    if pressed_close:
        blit(img, g, (148, 42, 9, 9), w - 11, 3)
    right_x = w - 8
    side_bottom = h - 14 - 24
    for ty2 in range(20, side_bottom, 29):
        blit(img, g, (127, 42, 11, 29), 0, ty2)
        blit(img, g, (139, 42, 8, 29), right_x, ty2)
        stretch(img, g, (139, 42, 1, 29), right_x - 3, ty2, 3, 29)
    blit(img, g, (158, 42, 11, 24), 0, side_bottom)
    blit(img, g, (170, 42, 8, 24), right_x, side_bottom)
    stretch(img, g, (170, 42, 1, 24), right_x - 3, side_bottom, 3, 24)
    by = h - 14
    for tx in range(0, w, 25):
        blit(img, g, (127, 72, 25, 14), tx, by)
    lw_ = min(125, -(-w // 2))
    rw_ = min(125, w - lw_)
    blit(img, g, (0, 42, 125, 14), 0, by, lw_)
    blit(img, g, (0, 57, 125, 14), w - rw_, by, rw_, 125 - rw_)
    pic = Image.linear_gradient("L").resize((w - 22, h - 34)).convert("RGB")
    arr = np.array(pic).astype(np.float32) / 255
    c0, c1 = np.array(T.disp, np.float32), np.array(T.accent, np.float32)
    col = c0 + (c1 - c0) * arr[..., :1]
    img.paste(Image.fromarray(col.astype(np.uint8)), (11, 20))
    return img


PREVIEW_ROWS = [("Night Drive - Copper Wire", "4:12"), ("Slow Burn - Lantern Hours", "3:47"),
                ("Kiln - Second Firing", "5:03"), ("Ash & Smoke - Afterglow", "2:58"),
                ("Ember Trio - Coal Seam", "6:21"), ("Field Notes - Warm Static", "3:33"),
                ("Tinder - Small Hours", "4:40"), ("The Forge - Bellows", "3:09"),
                ("Hearth - Long Winter", "5:51"), ("Glowworm - Low Light", "4:05"),
                ("Foundry - Pour", "3:22")]


def preview():
    bars = [12, 15, 14, 11, 13, 10, 9, 11, 8, 7, 9, 6, 5, 6, 4, 3, 4, 2, 3]
    A = dict(pressed=None, eq=True, pl=True, clutter="AV", shuffle=True, repeat=False, playing=True, stereo=True,
             pos=0.38, seek=False, volume=72, vdrag=False, balance=0, time=207, remaining=False,
             title="Night Drive - Copper Wire (Radio Edit)", bars=bars)
    B = dict(pressed="play", eq=False, pl=True, clutter="", shuffle=False, repeat=True, playing=False, stereo=False,
             pos=0.8, seek=True, volume=25, vdrag=True, balance=-60, time=95, remaining=True,
             title="Paused: Quiet Hours (Live)", bars=[3, 2, 4, 1, 2, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    EA = dict(pressed=None, on=True, auto=False, preamp=50, drag=None,
              bands=[75, 68, 56, 49, 49, 33, 30, 30, 49, 49])
    EB = dict(pressed="close", on=False, auto=True, preamp=70, drag=3,
              bands=[51, 51, 59, 65, 65, 100, 59, 51, 0, 51])
    cols = []
    for lit, st, est in ((True, A, EA), (False, B, EB)):
        h = 116 + 116 + 232 + 140
        col = Image.new("RGB", (275, h))
        col.paste(preview_main(lit, st), (0, 0))
        col.paste(preview_eq(lit, est), (0, 116))
        col.paste(preview_playlist(lit, 275, 232, PREVIEW_ROWS, pressed_close=not lit, drag=not lit), (0, 232))
        col.paste(preview_gen(lit, 275, 140, "album art", pressed_close=not lit), (0, 464))
        cols.append(col)
    gap = 12
    out = Image.new("RGB", (275 * 2 + gap * 3, cols[0].height + gap * 2), (60, 60, 64))
    out.paste(cols[0], (gap, gap))
    out.paste(cols[1], (275 + 2 * gap, gap))
    out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
    out.save(os.path.join(OPT.out, f"preview-{T.name}.png"))


def main(argv):
    ap = argparse.ArgumentParser(description="Build the VFD skins.")
    ap.add_argument("themes", nargs="*", help="themes to build (default: all)")
    ap.add_argument("--list", action="store_true", help="print the themes and exit")
    ap.add_argument("--title", default=OPT.title, help="main titlebar print")
    ap.add_argument("--name", default=OPT.name, help=".wsz base name (the silver one adds -Silver)")
    ap.add_argument("--out", default=OPT.out, help="where the .wsz files and previews go")
    args = ap.parse_args(argv)
    OPT.title, OPT.name, OPT.out = args.title, args.name, os.path.abspath(args.out)
    if args.list:
        for k, v in THEMES.items():
            print(f"{k:11s} {OPT.name + v.suffix}.wsz")
        return 0
    for theme in args.themes:
        if theme not in THEMES:
            ap.error(f"unknown theme {theme!r} (have: {', '.join(THEMES)})")
    os.makedirs(OPT.out, exist_ok=True)
    for theme in (args.themes or list(THEMES)):
        use_theme(theme)
        wsz = build()
        preview()
        print(f"{wsz}  preview-{theme}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
