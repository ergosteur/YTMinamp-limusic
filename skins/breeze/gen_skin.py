#!/usr/bin/python3
"""Breeze: classic Winamp 2.x skins in the Breeze style, light and dark.

One procedural generator, two themes (breeze-light, breeze-dark; no argument builds both).
Everything is drawn here from code: flat Breeze surfaces in the Breeze colour schemes' colours,
1px soft outlines, slightly rounded corners, round slider handles, plain titlebar glyphs, and
hand-made pixel fonts. The app's own icon (src-tauri/icons/icon.png), downscaled, sits in the
About spot.

Writes each theme's sheets into out/<theme>/, zips them flat into YTMinamp-Breeze-<Light|Dark>.wsz
and draws preview-<theme>.png (every window put together from the sprites at their real
positions, as the app does, 2x).

    /usr/bin/python3 -I gen_skin.py [breeze-light] [breeze-dark] [--accent=#rrggbb]

The accent is Breeze blue (#3daee9) unless --accent sets another.
"""

import os
import re
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # skins/genex_wacup.py, which finishes each .wsz
import genex_wacup  # noqa: E402

ICON = os.path.join(HERE, os.pardir, os.pardir, "src-tauri", "icons", "icon.png")  # the app's icon
OUT = None
T = None

# ------------------------------------------------------------------------------------------
# Colours: the Breeze colour schemes' own (BreezeLight.colors and BreezeDark.colors)
# ------------------------------------------------------------------------------------------

BREEZE_BLUE = (61, 174, 233)          # DecorationFocus / Selection BackgroundNormal

SCHEMES = {
    "breeze-light": dict(
        name="Light",
        window=(239, 240, 241),           # [Colors:Window] BackgroundNormal
        window_alt=(227, 229, 231),       # [Colors:Window] BackgroundAlternate
        button=(252, 252, 252),           # [Colors:Button] BackgroundNormal
        view=(255, 255, 255),             # [Colors:View] BackgroundNormal
        view_alt=(247, 247, 247),         # [Colors:View] BackgroundAlternate
        text=(35, 38, 41),                # ForegroundNormal
        text_inactive=(112, 125, 138),    # ForegroundInactive
        header=(222, 224, 226),           # [Colors:Header] BackgroundNormal (active titlebar)
        header_inactive=(239, 240, 241),  # [Colors:Header][Inactive] BackgroundNormal
        link=(41, 128, 185),              # ForegroundLink
        negative=(218, 68, 83),           # ForegroundNegative (the close button)
        dark=False,
    ),
    "breeze-dark": dict(
        name="Dark",
        window=(32, 35, 38),
        window_alt=(41, 44, 48),
        button=(41, 44, 48),
        view=(20, 22, 24),
        view_alt=(29, 31, 34),
        text=(252, 252, 252),
        text_inactive=(161, 169, 177),
        header=(41, 44, 48),
        header_inactive=(32, 35, 38),
        link=(29, 153, 243),
        negative=(218, 68, 83),
        dark=True,
    ),
}
THEME_KEYS = list(SCHEMES)

SEP = (255, 0, 255)          # gen.bmp letter separators (never shown)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ramp(stops, t):
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    i = min(n - 1, int(t * n))
    return lerp(stops[i], stops[i + 1], t * n - i)


def hexc(c):
    return "#%02X%02X%02X" % tuple(c)


def parse_colour(s):
    s = s.strip()
    if s.startswith("#") and len(s) == 7:
        return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
    parts = [int(p) for p in re.findall(r"\d+", s)[:3]]
    return tuple(parts) if len(parts) == 3 else None


def set_theme(key, accent):
    """Fills the module's palette names for one theme."""
    s = SCHEMES[key]
    g = globals()
    g["T"] = dict(s, key=key, accent=accent,
                  wsz=f"YTMinamp-Breeze-{s['name']}.wsz", preview=f"preview-{key}.png")
    W, X = s["window"], s["text"]
    g.update(
        DARK=s["dark"],
        WIN=W, WIN_ALT=s["window_alt"], BTN=s["button"], VIEW=s["view"], VIEW_ALT=s["view_alt"],
        TXT=X, TXT_IN=s["text_inactive"], HDR=s["header"], HDR_IN=s["header_inactive"],
        ACC=accent, NEG=s["negative"],
        # Breeze's frame outline: the background mixed a fifth of the way towards the text.
        FRAME=lerp(W, X, 0.2),
        OUTLINE=lerp(W, X, 0.25) if s["dark"] else lerp(W, X, 0.28),   # the window's own edge
        BTN_LINE=lerp(s["button"], X, 0.3 if not s["dark"] else 0.25),
        GROOVE=lerp(W, X, 0.2),
        SHADOW=lerp(W, BLACK, 0.07) if not s["dark"] else None,
        # checked / pressed fills: the button colour tinted with the accent
        TINT=lerp(s["button"], accent, 0.2 if not s["dark"] else 0.25),
        TINT_PRESS=lerp(s["button"], accent, 0.35 if not s["dark"] else 0.42),
        # the playlist's selection: the accent at reduced intensity on the View background
        SEL=lerp(s["view"], accent, 0.38 if not s["dark"] else 0.42),
        CURRENT=s["link"] if not s["dark"] else accent,
        FAINT=lerp(s["view"], X, 0.12),
        DIM=lerp(s["view"], X, 0.45),
    )


# ------------------------------------------------------------------------------------------
# Canvas helpers (numpy, H x W x 3, int)
# ------------------------------------------------------------------------------------------


def new(w, h, col):
    a = np.zeros((h, w, 3), dtype=np.int32)
    a[:, :] = col
    return a


def rect(a, x, y, w, h, col):
    if w > 0 and h > 0:
        a[y:y + h, x:x + w] = col


def px(a, x, y, col, alpha=1.0):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        if alpha >= 1:
            a[y, x] = col
        else:
            a[y, x] = np.round(a[y, x] * (1 - alpha) + np.array(col) * alpha).astype(np.int32)


def outline(a, x, y, w, h, col):
    rect(a, x, y, w, 1, col)
    rect(a, x, y + h - 1, w, 1, col)
    rect(a, x, y, 1, h, col)
    rect(a, x + w - 1, y, 1, h, col)


_COV = {}


def coverage(w, h, r, ss=6):
    """How much of each pixel a w x h rectangle with corner radius r covers (anti-aliased)."""
    k = (w, h, r)
    if k not in _COV:
        o = (np.arange(ss) + 0.5) / ss
        xs = (np.arange(w)[:, None] + o[None, :]).reshape(-1)
        ys = (np.arange(h)[:, None] + o[None, :]).reshape(-1)
        X, Y = np.meshgrid(xs, ys)
        dx = np.maximum(np.maximum(r - X, X - (w - r)), 0)
        dy = np.maximum(np.maximum(r - Y, Y - (h - r)), 0)
        inside = (dx * dx + dy * dy) <= r * r + 1e-9
        _COV[k] = inside.reshape(h, ss, w, ss).mean(axis=(1, 3))
    return _COV[k]


def rounded(a, x, y, w, h, r, col):
    if w <= 0 or h <= 0:
        return
    c = coverage(w, h, r)[:, :, None]
    sub = a[y:y + h, x:x + w].astype(np.float64)
    a[y:y + h, x:x + w] = np.round(sub * (1 - c) + np.array(col, dtype=np.float64) * c).astype(np.int32)


def frame(a, x, y, w, h, fill, line, r=2.5):
    """A Breeze frame: a 1px outline with softly rounded corners round a flat fill."""
    rounded(a, x, y, w, h, r, line)
    rounded(a, x + 1, y + 1, w - 2, h - 2, max(0.5, r - 1), fill)


def disc(a, x, y, d, col):
    rounded(a, x, y, d, d, d / 2, col)


def handle(a, x, y, d, pressed):
    """Breeze's slider handle: a round knob, button-coloured, outlined; the accent when held."""
    disc(a, x, y, d, ACC if pressed else BTN_LINE)
    disc(a, x + 1, y + 1, d - 2, lerp(BTN, ACC, 0.18) if pressed else BTN)


def save(a, name):
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
    img.save(os.path.join(OUT, name))
    return img


# ------------------------------------------------------------------------------------------
# Pixel fonts (all designed for this skin). '#' ink, '+' half ink.
# ------------------------------------------------------------------------------------------

def G(*rows):
    return list(rows)


# 5-row capitals for text.bmp and gen.bmp's letters: rounded, Noto-ish proportions.
FONT5 = {
    "A": G(".##.", "#..#", "####", "#..#", "#..#"),
    "B": G("###.", "#..#", "###.", "#..#", "###."),
    "C": G(".###", "#...", "#...", "#...", ".###"),
    "D": G("###.", "#..#", "#..#", "#..#", "###."),
    "E": G("####", "#...", "###.", "#...", "####"),
    "F": G("####", "#...", "###.", "#...", "#..."),
    "G": G(".###", "#...", "#.##", "#..#", ".###"),
    "H": G("#..#", "#..#", "####", "#..#", "#..#"),
    "I": G("#", "#", "#", "#", "#"),
    "J": G("..#", "..#", "..#", "..#", "##."),
    "K": G("#..#", "#.#.", "##..", "#.#.", "#..#"),
    "L": G("#..", "#..", "#..", "#..", "###"),
    "M": G("#...#", "##.##", "#.#.#", "#...#", "#...#"),
    "N": G("#..#", "##.#", "#.##", "#..#", "#..#"),
    "O": G(".##.", "#..#", "#..#", "#..#", ".##."),
    "P": G("###.", "#..#", "###.", "#...", "#..."),
    "Q": G(".##.", "#..#", "#..#", "#.#.", ".#.#"),
    "R": G("###.", "#..#", "###.", "#.#.", "#..#"),
    "S": G(".###", "#...", ".##.", "...#", "###."),
    "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#..#", "#..#", "#..#", "#..#", ".##."),
    "V": G("#...#", "#...#", ".#.#.", ".#.#.", "..#.."),
    "W": G("#...#", "#...#", "#.#.#", "#.#.#", ".#.#."),
    "X": G("#..#", "#..#", ".##.", "#..#", "#..#"),
    "Y": G("#...#", ".#.#.", "..#..", "..#..", "..#.."),
    "Z": G("####", "..#.", ".#..", "#...", "####"),
    "0": G(".#.", "#.#", "#.#", "#.#", ".#."),
    "1": G(".#", "##", ".#", ".#", ".#"),
    "2": G("##.", "..#", ".#.", "#..", "###"),
    "3": G("##.", "..#", ".#.", "..#", "##."),
    "4": G("#.#", "#.#", "###", "..#", "..#"),
    "5": G("###", "#..", "##.", "..#", "##."),
    "6": G(".##", "#..", "##.", "#.#", ".#."),
    "7": G("###", "..#", ".#.", ".#.", ".#."),
    "8": G(".#.", "#.#", ".#.", "#.#", ".#."),
    "9": G(".#.", "#.#", ".##", "..#", "##."),
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
    "?": G("##.", "..#", ".#.", "...", ".#."),
    "*": G("#.#", ".#.", "#.#", "...", "..."),
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
    "M": G("#...#", "##.##", "#.#.#", "#...#", "#...#"),
    "N": G("#..#", "##.#", "#.##", "#..#", "#..#"),
    "O": G(".#.", "#.#", "#.#", "#.#", ".#."),
    "P": G("##.", "#.#", "##.", "#..", "#.."),
    "Q": G(".#.", "#.#", "#.#", "##.", ".##"),
    "R": G("##.", "#.#", "##.", "#.#", "#.#"),
    "S": G(".##", "#..", ".#.", "..#", "##."),
    "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "V": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": G("#...#", "#...#", "#.#.#", "#.#.#", ".#.#."),
    "X": G("#.#", "#.#", ".#.", "#.#", "#.#"),
    "Y": G("#.#", "#.#", ".#.", ".#.", ".#."),
    "Z": G("###", "..#", ".#.", "#..", "###"),
    " ": G("..", "..", "..", "..", ".."),
}
for _c in "0123456789+-.":
    TINY[_c] = FONT5[_c]

# Mixed-case UI font: cap height 7 (rows 0-6), x-height 5 (rows 2-6), descenders rows 7-8.
_UI = {
    "A": G("..#..", ".#.#.", ".#.#.", "#...#", "#####", "#...#", "#...#"),
    "B": G("###.", "#..#", "#..#", "###.", "#..#", "#..#", "###."),
    "C": G(".###", "#...", "#...", "#...", "#...", "#...", ".###"),
    "D": G("###.", "#..#", "#..#", "#..#", "#..#", "#..#", "###."),
    "E": G("####", "#...", "#...", "###.", "#...", "#...", "####"),
    "F": G("####", "#...", "#...", "###.", "#...", "#...", "#..."),
    "G": G(".###", "#...", "#...", "#.##", "#..#", "#..#", ".###"),
    "H": G("#..#", "#..#", "#..#", "####", "#..#", "#..#", "#..#"),
    "I": G("#", "#", "#", "#", "#", "#", "#"),
    "J": G("..#", "..#", "..#", "..#", "..#", "..#", "##."),
    "K": G("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": G("#...", "#...", "#...", "#...", "#...", "#...", "####"),
    "M": G("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": G("#..#", "##.#", "##.#", "#.##", "#.##", "#..#", "#..#"),
    "O": G(".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": G("###.", "#..#", "#..#", "###.", "#...", "#...", "#..."),
    "Q": G(".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###.", "....#"),
    "R": G("###.", "#..#", "#..#", "###.", "#.#.", "#..#", "#..#"),
    "S": G(".###", "#...", "#...", ".##.", "...#", "...#", "###."),
    "T": G("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": G("#..#", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."),
    "V": G("#...#", "#...#", "#...#", ".#.#.", ".#.#.", ".#.#.", "..#.."),
    "W": G("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": G("#...#", ".#.#.", ".#.#.", "..#..", ".#.#.", ".#.#.", "#...#"),
    "Y": G("#...#", ".#.#.", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": G("####", "...#", "..#.", "..#.", ".#..", "#...", "####"),
    "a": G("....", "....", ".##.", "...#", ".###", "#..#", ".###"),
    "b": G("#...", "#...", "###.", "#..#", "#..#", "#..#", "###."),
    "c": G("...", "...", ".##", "#..", "#..", "#..", ".##"),
    "d": G("...#", "...#", ".###", "#..#", "#..#", "#..#", ".###"),
    "e": G("....", "....", ".##.", "#..#", "####", "#...", ".###"),
    "f": G(".##", "#..", "###", "#..", "#..", "#..", "#.."),
    "g": G("....", "....", ".###", "#..#", "#..#", "#..#", ".###", "...#", ".##."),
    "h": G("#...", "#...", "###.", "#..#", "#..#", "#..#", "#..#"),
    "i": G("#", ".", "#", "#", "#", "#", "#"),
    "j": G(".#", "..", ".#", ".#", ".#", ".#", ".#", ".#", "#."),
    "k": G("#...", "#...", "#..#", "#.#.", "##..", "#.#.", "#..#"),
    "l": G("#", "#", "#", "#", "#", "#", "#"),
    "m": G(".....", ".....", "####.", "#.#.#", "#.#.#", "#.#.#", "#.#.#"),
    "n": G("....", "....", "###.", "#..#", "#..#", "#..#", "#..#"),
    "o": G("....", "....", ".##.", "#..#", "#..#", "#..#", ".##."),
    "p": G("....", "....", "###.", "#..#", "#..#", "#..#", "###.", "#...", "#..."),
    "q": G("....", "....", ".###", "#..#", "#..#", "#..#", ".###", "...#", "...#"),
    "r": G("...", "...", "#.#", "##.", "#..", "#..", "#.."),
    "s": G("...", "...", ".##", "#..", ".#.", "..#", "##."),
    "t": G(".#.", ".#.", "###", ".#.", ".#.", ".#.", "..#"),
    "u": G("....", "....", "#..#", "#..#", "#..#", "#..#", ".###"),
    "v": G(".....", ".....", "#...#", "#...#", ".#.#.", ".#.#.", "..#.."),
    "w": G(".....", ".....", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#."),
    "x": G(".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"),
    "y": G("....", "....", "#..#", "#..#", "#..#", "#..#", ".###", "...#", ".##."),
    "z": G("....", "....", "####", "..#.", ".#..", "#...", "####"),
    " ": G("..", ".."),
}
UI = {}
for _c, _g in _UI.items():
    _w = max(len(r) for r in _g)
    UI[_c] = [r.ljust(_w, ".") for r in _g] + ["." * _w] * (9 - len(_g))

# Time digits for numbers.bmp (9x13 cells): a light, rounded sans, 6x11, drawn at (1, 1).
DIGITS = {
    0: G(".####.", "#....#", "#....#", "#....#", "#....#", "#....#", "#....#", "#....#", "#....#", "#....#", ".####."),
    1: G("...#..", "..##..", ".#.#..", "...#..", "...#..", "...#..", "...#..", "...#..", "...#..", "...#..", "...#.."),
    2: G(".####.", "#....#", ".....#", ".....#", "....#.", "...#..", "..#...", ".#....", "#.....", "#.....", "######"),
    3: G(".####.", "#....#", ".....#", ".....#", ".....#", "..###.", ".....#", ".....#", ".....#", "#....#", ".####."),
    4: G("....#.", "...##.", "..#.#.", "..#.#.", ".#..#.", "#...#.", "######", "....#.", "....#.", "....#.", "....#."),
    5: G("######", "#.....", "#.....", "#.....", "#####.", ".....#", ".....#", ".....#", ".....#", "#....#", ".####."),
    6: G("..###.", ".#....", "#.....", "#.....", "#####.", "#....#", "#....#", "#....#", "#....#", "#....#", ".####."),
    7: G("######", ".....#", ".....#", "....#.", "....#.", "...#..", "...#..", "..#...", "..#...", "..#...", "..#..."),
    8: G(".####.", "#....#", "#....#", "#....#", "#....#", ".####.", "#....#", "#....#", "#....#", "#....#", ".####."),
    9: G(".####.", "#....#", "#....#", "#....#", "#....#", "#....#", ".#####", ".....#", ".....#", "....#.", ".###.."),
}


def glyph_w(font, c):
    return len(font[c][0])


def text_w(font, s, gap=1):
    s = [c for c in s if c in font]
    return sum(glyph_w(font, c) for c in s) + gap * max(0, len(s) - 1)


def draw_glyph(a, g, x, y, col, bold=False):
    for r, row in enumerate(g):
        for k, ch in enumerate(row):
            if ch == "#":
                px(a, x + k, y + r, col)
                if bold:
                    px(a, x + k + 1, y + r, col)
            elif ch == "+":
                px(a, x + k, y + r, col, 0.45)


def draw_text(a, font, s, x, y, col, gap=1):
    for c in s:
        if c not in font:
            continue
        draw_glyph(a, font[c], x, y, col)
        x += len(font[c][0]) + gap
    return x


def text_center(a, font, s, cx, y, col, gap=1):
    draw_text(a, font, s, cx - text_w(font, s, gap) // 2, y, col, gap)


# ------------------------------------------------------------------------------------------
# Shared pieces
# ------------------------------------------------------------------------------------------


def deco_button(a, x, y, kind, lit=True, pressed=False):
    """9x9 titlebar button in the Breeze decoration's manner: a plain glyph; pressed, a round
    backdrop (the close button's turns red, its glyph white)."""
    bg = HDR if lit else HDR_IN
    rect(a, x, y, 9, 9, bg)
    ink = TXT if lit else TXT_IN
    if pressed:
        if kind == "close":
            disc(a, x, y, 9, NEG)
            ink = WHITE
        else:
            disc(a, x, y, 9, lerp(bg, TXT, 0.22))
    if kind == "options":           # the application menu: three short bars
        for yy in (2, 4, 6):
            rect(a, x + 2, y + yy, 5, 1, ink)
    elif kind == "minimize":        # chevron down
        for i, (dx, dy) in enumerate([(2, 3), (3, 4), (4, 5), (5, 4), (6, 3)]):
            px(a, x + dx, y + dy, ink)
    elif kind == "shade":           # chevron up
        for dx, dy in [(2, 5), (3, 4), (4, 3), (5, 4), (6, 5)]:
            px(a, x + dx, y + dy, ink)
    elif kind == "close":
        for i in range(5):
            px(a, x + 2 + i, y + 2 + i, ink)
            px(a, x + 6 - i, y + 2 + i, ink)


def button(a, x, y, w, h, bg, state="normal"):
    """A Breeze push button in a w x h cell: rounded 1px outline, flat face, a 1px gap right
    and below (with a faint drop shadow there in the light theme).
    state: normal | pressed | checked | checked-pressed."""
    rect(a, x, y, w, h, bg)
    bw, bh = w - 1, h - 1
    if SHADOW is not None:
        rounded(a, x, y + 1, bw, bh, 2.5, lerp(bg, BLACK, 0.09))
    face = {"normal": BTN, "pressed": TINT_PRESS, "checked": TINT, "checked-pressed": TINT_PRESS}[state]
    line = BTN_LINE if state == "normal" else ACC
    frame(a, x, y, bw, bh, face, line)


def tri_right(a, x, y, h, col):
    half = h // 2
    for r in range(h):
        n = half - abs(r - half) + 1
        rect(a, x, y + r, n, 1, col)


def tri_left(a, x, y, h, col):
    half = h // 2
    for r in range(h):
        n = half - abs(r - half) + 1
        rect(a, x + half + 1 - n, y + r, n, 1, col)


def transport_icon(a, kind, x, y, w, h, ink):
    cx, cy = x + (w - 1) // 2, y + (h - 1) // 2
    if kind == "previous":
        rect(a, cx - 4, cy - 3, 1, 7, ink)
        tri_left(a, cx - 3, cy - 3, 7, ink)
        tri_left(a, cx + 1, cy - 3, 7, ink)
    elif kind == "play":
        tri_right(a, cx - 1, cy - 4, 9, ink)
    elif kind == "pause":
        rect(a, cx - 3, cy - 3, 2, 7, ink)
        rect(a, cx + 2, cy - 3, 2, 7, ink)
    elif kind == "stop":
        rounded(a, cx - 3, cy - 3, 7, 7, 1.0, ink)
    elif kind == "next":
        tri_right(a, cx - 4, cy - 3, 7, ink)
        tri_right(a, cx, cy - 3, 7, ink)
        rect(a, cx + 4, cy - 3, 1, 7, ink)
    elif kind == "eject":
        for r in range(4):
            rect(a, cx - r, cy - 4 + r, 2 * r + 1, 1, ink)
        rect(a, cx - 3, cy + 1, 7, 2, ink)


def mini_transport_icon(a, kind, x, y, ink):
    cx, cy = x + 5, y + 5
    if kind == "previous":
        rect(a, cx - 3, cy - 2, 1, 5, ink)
        tri_left(a, cx - 2, cy - 2, 5, ink)
        tri_left(a, cx + 1, cy - 2, 5, ink)
    elif kind == "play":
        tri_right(a, cx - 1, cy - 3, 7, ink)
    elif kind == "pause":
        rect(a, cx - 2, cy - 2, 2, 5, ink)
        rect(a, cx + 1, cy - 2, 2, 5, ink)
    elif kind == "stop":
        rect(a, cx - 2, cy - 2, 5, 5, ink)
    elif kind == "next":
        tri_right(a, cx - 3, cy - 2, 5, ink)
        tri_right(a, cx, cy - 2, 5, ink)
        rect(a, cx + 3, cy - 2, 1, 5, ink)
    elif kind == "eject":
        for r in range(3):
            rect(a, cx - r, cy - 3 + r, 2 * r + 1, 1, ink)
        rect(a, cx - 2, cy + 1, 5, 1, ink)


# Breeze's media-playlist-shuffle / -repeat, redrawn small.
ICON_SHUFFLE = G(
    "........#..",
    "##....#####",
    "..#..#..#..",
    "...##......",
    "...##......",
    "..#..#..#..",
    "##....#####",
    "........#..",
)
ICON_REPEAT = G(
    "......#...",
    ".########.",
    "#.....#..#",
    "#........#",
    "#........#",
    "#..#.....#",
    ".########.",
    "...#......",
)


def logo_rgba(h):
    """The app's icon (red disc, white play mark, yellow bolt) downscaled to h x h, RGBA."""
    im = Image.open(ICON).convert("RGBA").resize((h, h), Image.LANCZOS)
    return np.array(im).astype(np.float64)


def paste_logo(a, x, y, h):
    lg = logo_rgba(h)
    al = lg[:, :, 3:4] / 255
    sub = a[y:y + lg.shape[0], x:x + lg.shape[1]].astype(np.float64)
    a[y:y + lg.shape[0], x:x + lg.shape[1]] = np.round(sub * (1 - al) + lg[:, :, :3] * al).astype(np.int32)


# ------------------------------------------------------------------------------------------
# titlebar.bmp (344 x 87)
# ------------------------------------------------------------------------------------------

CLUTTER_SLOTS = [("O", 3, 8), ("A", 11, 7), ("I", 18, 7), ("D", 25, 8), ("V", 33, 7)]


def clutter_bar(lit_letters):
    a = new(8, 43, WIN)
    frame(a, 0, 0, 8, 43, WIN, FRAME, 2.0)
    for letter, y, h in CLUTTER_SLOTS:
        on = letter in lit_letters
        if on:
            rounded(a, 1, y, 6, h, 1.5, TINT_PRESS)
        gy = y + (h - 5) // 2
        draw_text(a, TINY, letter, 2, gy, TXT if on else TXT_IN)
    return a


def window_bar(w, h, lit, title, buttons, font=None, ty=3):
    """A Breeze titlebar: the Header colour, the title centred, plain glyph buttons."""
    a = new(w, h, HDR if lit else HDR_IN)
    rect(a, 0, 0, w, 1, OUTLINE)
    rect(a, 0, 0, 1, h, OUTLINE)
    rect(a, w - 1, 0, 1, h, OUTLINE)
    font = font or UI
    text_center(a, font, title, w // 2, ty, TXT if lit else TXT_IN)
    for kind, x in buttons:
        deco_button(a, x, 3, kind, lit)
    return a


def main_titlebar(lit):
    return window_bar(275, 14, lit, "YTMinamp", [("options", 6), ("minimize", 244), ("shade", 254), ("close", 264)])


def make_titlebar():
    a = new(344, 87, WIN)
    for kind, x in [("options", 0), ("minimize", 9), ("close", 18)]:
        b = new(9, 9, HDR)
        deco_button(b, 0, 0, kind, True)
        a[0:9, x:x + 9] = b
        deco_button(b, 0, 0, kind, True, pressed=True)
        a[9:18, x:x + 9] = b
    b = new(9, 9, HDR)
    deco_button(b, 0, 0, "shade", True)
    a[18:27, 0:9] = b
    deco_button(b, 0, 0, "shade", True, pressed=True)
    a[18:27, 9:18] = b
    a[0:14, 27:302] = main_titlebar(True)
    a[15:29, 27:302] = main_titlebar(False)
    a[29:43, 27:302] = main_titlebar(True)
    a[42:56, 27:302] = main_titlebar(False)
    unlit = clutter_bar("")
    lit = clutter_bar("OAIDV")
    a[0:43, 304:312] = unlit
    a[0:43, 312:320] = unlit
    for (letter, y, h), sx, sy in zip(CLUTTER_SLOTS, [304, 312, 320, 328, 336], [47, 55, 62, 69, 77]):
        a[sy:sy + h, sx:sx + 8] = lit[y:y + h]
    return a


# ------------------------------------------------------------------------------------------
# main.bmp (275 x 116)
# ------------------------------------------------------------------------------------------


def make_main():
    a = new(275, 116, WIN)
    outline(a, 0, 0, 275, 116, OUTLINE)
    a[0:14, :] = main_titlebar(True)
    a[22:65, 10:18] = clutter_bar("")
    # left display: indicator, time, analyzer, on the View background
    frame(a, 20, 19, 86, 44, VIEW, FRAME)
    for yy in (30, 35):
        rect(a, 73, yy, 2, 2, TXT)
    # right display: the title row above, kbps / kHz / mono / stereo below, one View panel
    frame(a, 108, 20, 161, 36, VIEW, FRAME)
    rect(a, 112, 37, 153, 1, lerp(VIEW, TXT, 0.08))
    draw_text(a, TINY, "KBPS", 129, 44, DIM)
    draw_text(a, TINY, "KHZ", 169, 44, DIM)
    # the app's icon where Winamp keeps its About button
    paste_logo(a, 250, 90, 16)
    return a


# ------------------------------------------------------------------------------------------
# cbuttons.bmp (136 x 36)
# ------------------------------------------------------------------------------------------


def make_cbuttons():
    a = new(136, 36, WIN)
    specs = [("previous", 0, 23, 18), ("play", 23, 23, 18), ("pause", 46, 23, 18),
             ("stop", 69, 23, 18), ("next", 92, 22, 18)]
    for kind, x, w, h in specs:
        for pressed, y in ((False, 0), (True, 18)):
            button(a, x, y, w, h, WIN, "pressed" if pressed else "normal")
            transport_icon(a, kind, x, y, w - 1, h - 1, TXT)
    for pressed, y in ((False, 0), (True, 16)):
        button(a, 114, y, 22, 16, WIN, "pressed" if pressed else "normal")
        transport_icon(a, "eject", 114, y, 21, 15, TXT)
    return a


# ------------------------------------------------------------------------------------------
# shufrep.bmp (92 x 85)
# ------------------------------------------------------------------------------------------


def state_of(on, pressed):
    return ("checked-pressed" if pressed else "checked") if on else ("pressed" if pressed else "normal")


def icon_toggle(a, x, y, w, h, icon, label, on, pressed, cell_w=None):
    cw = cell_w or w
    rect(a, x, y, cw, h, WIN)
    button(a, x, y, w, h, WIN, state_of(on, pressed))
    ink = ACC if on else TXT
    iw, ih = len(icon[0]), len(icon)
    tw = (text_w(UI, label) + 4) if label else 0
    gx = x + (w - 1 - iw - tw) // 2
    draw_glyph(a, icon, gx, y + (h - 1 - ih) // 2, ink)
    if label:
        draw_text(a, UI, label, gx + iw + 4, y + 3, TXT)


def label_toggle(a, x, y, w, h, label, on, pressed):
    button(a, x, y, w, h, WIN, state_of(on, pressed))
    text_center(a, TINY, label, x + (w - 1) // 2 + 1, y + (h - 1 - 5) // 2, ACC if on else TXT)


def make_shufrep():
    a = new(92, 85, WIN)
    for row, (on, pressed) in enumerate([(False, False), (False, True), (True, False), (True, True)]):
        y = row * 15
        icon_toggle(a, 0, y, 27, 15, ICON_REPEAT, None, on, pressed, cell_w=28)
        icon_toggle(a, 28, y, 46, 15, ICON_SHUFFLE, None, on, pressed, cell_w=47)
    for x, label, pressed in [(0, "EQ", False), (23, "PL", False), (46, "EQ", True), (69, "PL", True)]:
        label_toggle(a, x, 61, 23, 12, label, False, pressed)
        label_toggle(a, x, 73, 23, 12, label, True, pressed)
    return a


# ------------------------------------------------------------------------------------------
# monoster, playpaus, numbers, nums_ex, text
# ------------------------------------------------------------------------------------------


def make_monoster():
    a = new(56, 24, VIEW)
    for y, on in ((0, True), (12, False)):
        col = TXT if on else lerp(VIEW, TXT, 0.25)
        text_center(a, TINY, "STEREO", 14, y + 4, col)
        text_center(a, TINY, "MONO", 29 + 13, y + 4, col)
    return a


def make_playpaus():
    a = new(48, 9, VIEW)
    tri_right(a, 2, 1, 7, ACC)                        # playing
    rect(a, 9 + 2, 1, 2, 7, TXT)                      # paused
    rect(a, 9 + 5, 1, 2, 7, TXT)
    rounded(a, 18 + 1, 1, 7, 7, 1.0, TXT)             # stopped
    rect(a, 36, 0, 3, 9, VIEW)                        # not working
    rect(a, 39 + 1, 3, 1, 3, ACC)                     # working
    return a


def make_numbers(ex):
    a = new(108 if ex else 99, 13, VIEW)
    for n in range(10):
        draw_glyph(a, DIGITS[n], 9 * n + 1, 1, TXT)
    if ex:
        rect(a, 99 + 2, 6, 5, 1, TXT)                 # minus
    return a


FONT_GRID = [
    list("abcdefghijklmnopqrstuvwxyz\"@") + [None, None, " "],
    list("0123456789") + ["…", ".", ":", "(", ")", "-", "'", "!", "_", "+", "\\", "/", "[", "]", "^", "&", "%",
                          ",", "=", "$", "#"],
    ["å", "ö", "ä", "?", "*"] + [None] * 26,
]


def make_text():
    a = new(155, 18, VIEW)
    for row, chars in enumerate(FONT_GRID):
        for col, ch in enumerate(chars):
            if ch is None or ch == " ":
                continue
            key = ch if ch in FONT5 else ch.upper()
            g = FONT5[key]
            ox = (5 - len(g[0])) // 2 if len(g[0]) < 4 else 0
            draw_glyph(a, g, col * 5 + ox, row * 6, TXT)
    return a


# ------------------------------------------------------------------------------------------
# posbar.bmp (307 x 10), volume.bmp / balance.bmp (68 x 433)
# ------------------------------------------------------------------------------------------


def groove(a, x, y, w, col, h=3):
    rounded(a, x, y, w, h, 1.5, col)


def make_posbar():
    a = new(307, 10, WIN)
    groove(a, 2, 3, 244, GROOVE)
    for x0, pressed in ((248, False), (278, True)):
        rect(a, x0, 0, 29, 10, WIN)
        rect(a, x0, 3, 29, 3, GROOVE)
        handle(a, x0 + 10, 0, 9, pressed)
    return a


def volume_thumbs(a, fill_left):
    for x0, pressed in ((0, True), (15, False)):
        rect(a, x0, 422, 14, 11, WIN)
        rect(a, x0, 426, 14, 3, GROOVE)
        if fill_left:
            rect(a, x0, 426, 7, 3, ACC)
        handle(a, x0 + 2, 422, 11, pressed)


def make_volume():
    a = new(68, 433, WIN)
    for i in range(28):
        y = i * 15
        level = (i + 1) / 28
        fill_to = 7 + round(level * 54)
        groove(a, 3, y + 5, 62, GROOVE)
        groove(a, 3, y + 5, fill_to - 3, ACC)
    volume_thumbs(a, True)
    return a


def make_balance():
    a = new(68, 433, WIN)
    for i in range(28):
        y = i * 15
        groove(a, 11, y + 5, 34, GROOVE)
        rect(a, 28, y + 2, 1, 2, DIM if i else ACC)
        rect(a, 28, y + 9, 1, 2, DIM if i else ACC)
    volume_thumbs(a, False)
    return a


# ------------------------------------------------------------------------------------------
# eqmain.bmp (275 x 315)
# ------------------------------------------------------------------------------------------

EQ_BANDS = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]


def eq_titlebar(lit):
    return window_bar(275, 14, lit, "Equalizer", [("close", 264)])


def eq_slider_frame(a, x, y, n):
    """14x63: a vertical Breeze slider's groove, filled with the accent from the bottom."""
    rect(a, x, y, 14, 63, WIN)
    v = n / 27
    centre = round((1 - v) * 51) + 5
    groove_v(a, x + 5, y + 2, 59, GROOVE)
    if centre < 61:
        rounded(a, x + 5, y + centre, 3, 61 - centre, 1.5, ACC)
    for cx in (x + 1, x + 11):
        rect(a, cx, y + 30, 2, 1, FRAME)


def groove_v(a, x, y, h, col):
    rounded(a, x, y, 3, h, 1.5, col)


def checkbox(a, x, y, on, pressed):
    """Breeze's check box, 8x8: rounded outline; checked, an accent fill with a white tick."""
    if on:
        frame(a, x, y, 8, 8, ACC, ACC, 2.0)
        for dx, dy in [(1, 4), (2, 5), (3, 6), (4, 5), (5, 4), (6, 3), (6, 2)]:
            px(a, x + dx, y + dy - 1, WHITE)
        for dx, dy in [(2, 4), (3, 5), (4, 4), (5, 3)]:
            px(a, x + dx, y + dy - 1, WHITE, 0.5)
    else:
        frame(a, x, y, 8, 8, TINT if pressed else VIEW, ACC if pressed else BTN_LINE, 2.0)


def check_toggle(a, x, y, w, label, on, pressed):
    rect(a, x, y, w, 12, WIN)
    checkbox(a, x + 1, y + 2, on, pressed)
    draw_text(a, UI, label, x + 11, y + 2, TXT)


def make_eqmain():
    a = new(275, 315, WIN)
    outline(a, 0, 0, 275, 116, OUTLINE)
    a[0:14, :] = eq_titlebar(True)
    # graph: a View panel
    frame(a, 85, 16, 115, 21, VIEW, FRAME)
    # slider bay: a Breeze group frame
    frame(a, 16, 36, 245, 68, WIN, FRAME)
    rect(a, 40, 39, 1, 62, FRAME)
    for lbl, yy in (("+12DB", 41), ("0DB", 66), ("-12DB", 92)):
        text_center(a, TINY, lbl, 58, yy, DIM)
    for x in [21] + [78 + 18 * i for i in range(10)]:
        eq_slider_frame(a, x, 38, 14)
    text_center(a, TINY, "PREAMP", 28, 106, TXT_IN)
    for i, lbl in enumerate(EQ_BANDS):
        text_center(a, TINY, lbl, 78 + 18 * i + 7, 106, TXT_IN)

    # under the window
    b = new(9, 9, HDR)
    deco_button(b, 0, 0, "close", True, pressed=True)
    a[125:134, 0:9] = b
    for x, label, on, pressed in [
        (10, "On", False, False), (36, "Auto", False, False), (69, "On", True, False), (95, "Auto", True, False),
        (128, "On", False, True), (154, "Auto", False, True), (187, "On", True, True), (213, "Auto", True, True),
    ]:
        check_toggle(a, x, 119, 26 if label == "On" else 32, label, on, pressed)
    a[134:148, :] = eq_titlebar(True)
    a[149:163, :] = eq_titlebar(False)
    for y, pressed in ((164, False), (176, True)):
        rect(a, 0, y, 11, 11, WIN)
        rect(a, 4, y, 3, 5, GROOVE)
        rect(a, 4, y + 5, 3, 6, ACC)
        handle(a, 0, y, 11, pressed)
    for n in range(28):
        eq_slider_frame(a, 13 + (n % 14) * 15, 164 + (n // 14) * 65, n)
    for y, pressed in ((164, False), (176, True)):
        button(a, 224, y, 44, 12, WIN, "pressed" if pressed else "normal")
        text_center(a, UI, "Presets", 224 + 21, y + 2, TXT)
    # graph
    rect(a, 0, 294, 113, 19, VIEW)
    for x in range(1, 113, 12):
        for y in range(0, 19, 2):
            px(a, x, 294 + y, FAINT)
    for x in range(0, 113, 2):
        px(a, x, 294 + 9, FAINT)
    for r in range(19):
        px(a, 115, 294 + r, ACC)
    for x in range(113):
        px(a, x, 314, DIM if x % 3 != 2 else VIEW)
    return a


# ------------------------------------------------------------------------------------------
# pledit.bmp (280 x 186) and gen.bmp (194 x 109): the 20px-titled frames
# ------------------------------------------------------------------------------------------


def bar20(w, lit):
    a = new(w, 20, HDR if lit else HDR_IN)
    rect(a, 0, 0, w, 1, OUTLINE)
    return a


def make_pledit():
    a = new(280, 186, WIN)
    for lit, y in ((True, 0), (False, 21)):
        t = bar20(25, lit)
        rect(t, 0, 19, 25, 1, FRAME)
        a[y:y + 20, 127:152] = t
        # top-left corner: the window's edge, then the list's frame starting at x 11
        t = bar20(25, lit)
        rect(t, 0, 0, 1, 20, OUTLINE)
        rect(t, 11, 19, 14, 1, FRAME)
        a[y:y + 20, 0:25] = t
        # title
        t = bar20(100, lit)
        text_center(t, UI, "Playlist", 50, 4, TXT if lit else TXT_IN)
        rect(t, 0, 19, 100, 1, FRAME)
        a[y:y + 20, 26:126] = t
        # top-right corner: close button; the list's frame (which holds the scrollbar) ends at x 19
        t = bar20(25, lit)
        rect(t, 24, 0, 1, 20, OUTLINE)
        deco_button(t, 14, 3, "close", lit)
        rect(t, 0, 19, 20, 1, FRAME)
        a[y:y + 20, 153:178] = t

    # left side tile
    t = new(12, 29, WIN)
    rect(t, 0, 0, 1, 29, OUTLINE)
    rect(t, 11, 0, 1, 29, FRAME)
    a[42:71, 0:12] = t
    # right side tile: the list's View background runs under the scrollbar (cols 0..13), then
    # its frame, the window, the edge
    t = new(20, 29, WIN)
    rect(t, 0, 0, 14, 29, VIEW)
    rect(t, 14, 0, 1, 29, FRAME)
    rect(t, 19, 0, 1, 29, OUTLINE)
    a[42:71, 31:51] = t
    # close pressed, scroll handles (8x18 at the tile's x 5): Breeze's slim rounded handle
    t = new(9, 9, HDR)
    deco_button(t, 0, 0, "close", True, pressed=True)
    a[42:51, 52:61] = t
    for x, sel in ((52, False), (61, True)):
        rect(a, x, 53, 8, 18, VIEW)
        rounded(a, x + 2, 53, 4, 18, 2.0, ACC if sel else lerp(VIEW, TXT, 0.4))

    def bottom_base(w):
        t = new(w, 38, WIN)
        rect(t, 0, 37, w, 1, OUTLINE)
        return t

    t = bottom_base(125)
    rect(t, 0, 0, 1, 38, OUTLINE)
    rect(t, 11, 0, 114, 1, FRAME)
    for bx, lbl in ((14, "Add"), (43, "Rem"), (72, "Sel"), (101, "Misc")):
        button(t, bx, 8, 22, 18, WIN)
        text_center(t, UI, lbl, bx + 11, 13, TXT)
    a[72:110, 0:125] = t

    t = bottom_base(150)
    rect(t, 149, 0, 1, 38, OUTLINE)
    rect(t, 0, 0, 145, 1, FRAME)
    frame(t, 5, 8, 58, 10, VIEW, FRAME, 2.0)                 # running time
    for k, kind in enumerate(["previous", "play", "pause", "stop", "next", "eject"]):
        mini_transport_icon(t, kind, 3 + 10 * k, 22, TXT)  # flat tool buttons
    frame(t, 64, 21, 35, 10, VIEW, FRAME, 2.0)               # mini time
    rect(t, 84, 22 + 2, 1, 1, DIM)
    rect(t, 84, 22 + 5, 1, 1, DIM)
    button(t, 106, 8, 22, 18, WIN)
    text_center(t, UI, "List", 117, 13, TXT)
    for k in range(3):                                      # size grip: dots
        for j in range(k + 1):
            px(t, 146 - 3 * k + 3 * j, 34 - 3 * j, FRAME)
    a[72:110, 126:276] = t

    t = bottom_base(25)
    rect(t, 0, 0, 25, 1, FRAME)
    a[0:38, 179:204] = t
    return a


GEN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def make_gen():
    a = new(194, 109, WIN)
    for lit, y in ((True, 0), (False, 21)):
        for px0 in (0, 26, 52, 78, 104, 130):
            t = bar20(25, lit)
            if px0 == 0:
                rect(t, 0, 0, 1, 20, OUTLINE)
            if px0 == 130:
                deco_button(t, 14, 3, "close", lit)
                rect(t, 24, 0, 1, 20, OUTLINE)
            a[y:y + 20, px0:px0 + 25] = t

    def bottom(w, grip, left_edge):
        t = new(w, 14, WIN)
        rect(t, 0, 13, w, 1, OUTLINE)
        if left_edge:
            rect(t, 0, 0, 1, 14, OUTLINE)
        else:
            rect(t, w - 1, 0, 1, 14, OUTLINE)
        if grip:
            for k in range(3):
                for j in range(k + 1):
                    px(t, w - 4 - 3 * k + 3 * j, 10 - 3 * j, FRAME)
        return t

    a[42:56, 0:125] = bottom(125, False, True)
    a[57:71, 0:125] = bottom(125, True, False)
    t = new(25, 14, WIN)
    rect(t, 0, 13, 25, 1, OUTLINE)
    a[72:86, 127:152] = t
    for x, w, h, outer_left in ((127, 11, 29, True), (158, 11, 24, True), (139, 8, 29, False), (170, 8, 24, False)):
        t = new(w, h, WIN)
        if outer_left:
            rect(t, 0, 0, 1, h, OUTLINE)
        else:
            rect(t, w - 1, 0, 1, h, OUTLINE)
        a[42:42 + h, x:x + w] = t
    t = new(9, 9, HDR)
    deco_button(t, 0, 0, "close", True, pressed=True)
    a[42:51, 148:157] = t

    # letters: each row starts at x 1, letters in their own cells, 1px separators of x 0's colour
    for lit, y in ((True, 88), (False, 96)):
        rect(a, 0, y, 194, 7, SEP)
        x = 1
        for c in GEN_LETTERS:
            w = glyph_w(FONT5, c) + 1
            rect(a, x, y, w, 7, HDR if lit else HDR_IN)
            draw_text(a, FONT5, c, x, y + 1, TXT if lit else TXT_IN)
            x += w + 1
        assert x <= 194, x
    return a


# ------------------------------------------------------------------------------------------
# genex.bmp: Media Library colours along the top row, every other pixel from x 48
# ------------------------------------------------------------------------------------------


def genex_colours():
    return [
        VIEW,                       # item background
        TXT,                        # item text
        WIN,                        # window background
        TXT,                        # button text
        TXT,                        # window text
        FRAME,                      # dividers, sunken borders
        SEL,                        # selection bar
        HDR,                        # list header background
        TXT,                        # list header text
        BTN,                        # header frame, light
        FRAME,                      # header frame, dark
        ACC,                        # header frame, pressed
        WIN,                        # header dead area
        lerp(WIN, TXT, 0.4),        # scrollbar
        lerp(WIN, TXT, 0.4),        # scrollbar 2
        ACC,                        # scrollbar pressed
        ACC,                        # scrollbar pressed 2
        WIN,                        # scrollbar dead area
    ]


def make_genex():
    a = new(256, 64, WIN)
    for i, c in enumerate(genex_colours()):
        px(a, 48 + 2 * i, 0, c)
    button(a, 0, 1, 47, 15, WIN)
    button(a, 0, 16, 47, 15, WIN, "pressed")
    return a


# ------------------------------------------------------------------------------------------
# Text files
# ------------------------------------------------------------------------------------------


def viscolor():
    if DARK:
        stops = [lerp(ACC, WHITE, 0.55), lerp(ACC, WHITE, 0.2), ACC, lerp(ACC, VIEW, 0.35), lerp(ACC, VIEW, 0.6)]
    else:
        stops = [lerp(ACC, BLACK, 0.35), lerp(ACC, BLACK, 0.12), ACC, lerp(ACC, VIEW, 0.35), lerp(ACC, VIEW, 0.58)]
    v = [(VIEW, "background"), (lerp(VIEW, TXT, 0.08), "dots")]
    v += [(ramp(stops, i / 15), f"spectrum {i + 1} (top)" if i == 0 else f"spectrum {i + 1}") for i in range(16)]
    osc = [stops[0], stops[1], ACC, stops[3], stops[4]]
    v += [(c, f"oscilloscope {i + 1}") for i, c in enumerate(osc)]
    v += [(TXT, "peaks")]
    return v


def write_text_files():
    with open(os.path.join(OUT, "viscolor.txt"), "w", newline="\r\n") as f:
        for (r, g, b), note in viscolor():
            f.write(f"{r},{g},{b}, // {note}\n")
    with open(os.path.join(OUT, "pledit.txt"), "w", newline="\r\n") as f:
        f.write(f"[Text]\nNormal={hexc(TXT)}\nCurrent={hexc(CURRENT)}\nNormalBG={hexc(VIEW)}\n"
                f"SelectedBG={hexc(SEL)}\nMbBG={hexc(VIEW)}\nMbFG={hexc(TXT)}\nFont=Noto Sans\n")
    name = T["name"]
    with open(os.path.join(OUT, "readme.txt"), "w", newline="\r\n") as f:
        title = f"YTMinamp Breeze {name} - a skin in the Breeze style, drawn from scratch."
        f.write(
            f"{title}\n\n"
            "A classic (Winamp 2.x format) skin made to sit beside Breeze desktops: the\n"
            f"Breeze {name} colour scheme's own colours, flat surfaces with 1px soft outlines, the\n"
            "Breeze window decoration's plain titlebar glyphs, round slider handles and the accent\n"
            "colour for focus, slider fill and selection. Every bitmap was drawn by a script\n"
            "(gen_skin.py) from rectangles and hand-made pixel fonts; the emblem is YTMinamp's\n"
            "own icon. Breeze's design is LGPL; this is an homage, not a copy of its artwork.\n\n"
            "License: CC0 1.0 Universal (public domain dedication).\n"
        )


# ------------------------------------------------------------------------------------------
# Build
# ------------------------------------------------------------------------------------------

SHEETS = {}


def build():
    sheets = {
        "main.bmp": make_main(),
        "titlebar.bmp": make_titlebar(),
        "cbuttons.bmp": make_cbuttons(),
        "shufrep.bmp": make_shufrep(),
        "posbar.bmp": make_posbar(),
        "volume.bmp": make_volume(),
        "balance.bmp": make_balance(),
        "monoster.bmp": make_monoster(),
        "playpaus.bmp": make_playpaus(),
        "numbers.bmp": make_numbers(False),
        "nums_ex.bmp": make_numbers(True),
        "text.bmp": make_text(),
        "pledit.bmp": make_pledit(),
        "eqmain.bmp": make_eqmain(),
        "gen.bmp": make_gen(),
        "genex.bmp": make_genex(),
    }
    for name, arr in sheets.items():
        SHEETS[name[:-4]] = save(arr, name)
    write_text_files()
    names = list(sheets) + ["pledit.txt", "viscolor.txt", "readme.txt"]
    with zipfile.ZipFile(os.path.join(HERE, T["wsz"]), "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(OUT, n), "rb") as f:
                z.writestr(info, f.read())
    # genex.bmp completed for real Winamp and WACUP: all 24 colours, readable text, and the
    # standard 112x59 button and scrollbar layout (skins/genex_wacup.py).
    genex_wacup.process(os.path.join(HERE, T["wsz"]))
    return names


# ------------------------------------------------------------------------------------------
# Preview: every window put together from the sprites the way the app does
# ------------------------------------------------------------------------------------------

NOTO = "/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf"


def ui_font(size):
    for f in (NOTO, "NotoSans-Regular.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


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
for _k, _v in {"<": "[", ">": "]", "{": "[", "}": "]"}.items():
    FONT_LOOKUP[_k] = FONT_LOOKUP[_v]


def draw_bitmap_text(dst, s, x, y):
    text = SHEETS["text"]
    for ch in s:
        row, col = FONT_LOOKUP.get(ch.lower(), FONT_LOOKUP[" "])
        blit(dst, text, (col * 5, row * 6, 5, 6), x, y)
        x += 5


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
        blit(img, nums, (99, 0, 9, 13), 38, 26)
    for d, x in ((m // 10, 48), (m % 10, 60), (s // 10, 78), (s % 10, 90)):
        blit(img, nums, (9 * d, 0, 9, 13), x, 26)
    # title: the space cell across the box, then the title in the playlist's font (as the app)
    for x in range(0, 154, 5):
        blit(img, S["text"], (150, 0, min(5, 154 - x), 6), 111 + x, 24)
    d = ImageDraw.Draw(img)
    clip = Image.new("RGB", (154, 14))
    clip.paste(img.crop((111, 22, 265, 36)))
    cd = ImageDraw.Draw(clip)
    cd.text((0, 24 + 3 + 2 - 22), state["title"], fill=TXT, font=ui_font(11), anchor="lm")
    img.paste(clip, (111, 22))
    draw_bitmap_text(img, "192", 111, 43)
    draw_bitmap_text(img, "44", 156, 43)
    cols = [c for c, _ in viscolor()]
    vis = Image.new("RGB", (76, 16))
    vp = vis.load()
    for y in range(16):
        for x in range(76):
            vp[x, y] = cols[1] if (y % 2 == 1 and x % 2 == 0) else cols[0]
    for x in range(75):
        if x % 4 == 3:
            continue
        hgt = state["bars"][x // 4] - 2
        for y in range(16 - hgt, 16):
            vp[x, y] = cols[min(17, max(2, y))]
        pk = state["bars"][x // 4] + 2
        if 0 <= 16 - pk < 16:
            vp[x, 16 - pk] = cols[23]
    img.paste(vis, (24, 43))
    del d
    return img


def preview_eq(lit, state):
    sheet = SHEETS["eqmain"]
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
    sheet = SHEETS["pledit"]
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
    lx, lw = 12, w - 32
    d.rectangle((lx, 20, lx + lw - 1, h - 39), fill=VIEW)
    font = ui_font(9)
    for i, (txt, dur) in enumerate(rows):
        y = 23 + i * 15
        if y + 15 > h - 38:
            break
        if i == 2:
            d.rectangle((lx, y, lx + lw - 1, y + 14), fill=SEL)
        col = CURRENT if i == 1 else TXT
        d.text((lx + 2, y + 2), f"{i + 1}. {txt}", fill=col, font=font)
        d.text((lx + lw - 3 - d.textlength(dur, font=font), y + 2), dur, fill=col, font=font)
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
    # a stand-in picture: a cool gradient
    pic = Image.linear_gradient("L").resize((w - 22, h - 34)).convert("RGB")
    arr = np.array(pic).astype(np.float32) / 255
    col = np.stack([20 + 40 * arr[..., 0], 60 + 114 * arr[..., 0], 90 + 143 * arr[..., 0]], -1)
    img.paste(Image.fromarray(col.astype(np.uint8)), (11, 20))
    return img


def preview():
    rows = [("Morning Light - Open Fields", "4:12"), ("The Long Way Round", "3:47"),
            ("Breeze - Open Window", "5:03"), ("First Breath", "2:58"),
            ("Syntax & Colour", "6:21"), ("Deep Folders", "3:33"),
            ("Folded Paper", "4:40"), ("Compositor", "3:09"),
            ("Hallway Track", "5:51"), ("Effects", "4:05"),
            ("Six Frames", "3:22")]
    bars = [12, 15, 14, 11, 13, 10, 9, 11, 8, 7, 9, 6, 5, 6, 4, 3, 4, 2, 3]
    A = dict(pressed=None, eq=True, pl=True, clutter="AV", shuffle=True, repeat=False, playing=True, stereo=True,
             pos=0.38, seek=False, volume=72, vdrag=False, balance=0, time=207, remaining=False,
             title=f"YTMinamp Breeze {T['name']} - drawn from scratch", bars=bars)
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
        col.paste(preview_playlist(lit, 275, 232, rows, pressed_close=not lit, drag=not lit), (0, 232))
        col.paste(preview_gen(lit, 275, 140, "album art", pressed_close=not lit), (0, 464))
        cols.append(col)
    gap = 12
    out = Image.new("RGB", (275 * 2 + gap * 3, cols[0].height + gap * 2), (96, 98, 102))
    out.paste(cols[0], (gap, gap))
    out.paste(cols[1], (275 + 2 * gap, gap))
    out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
    out.save(os.path.join(HERE, T["preview"]))


def run(key, accent):
    global OUT
    set_theme(key, accent)
    OUT = os.path.join(HERE, "out", key)
    os.makedirs(OUT, exist_ok=True)
    SHEETS.clear()
    names = build()
    preview()
    for n in names:
        if n.endswith(".bmp"):
            im = Image.open(os.path.join(OUT, n))
            assert im.mode == "RGB", (n, im.mode)
    print(f"{key:13s} accent {hexc(accent)} -> {T['wsz']}, {T['preview']}")


if __name__ == "__main__":
    if "--list" in sys.argv[1:]:
        print("\n".join(THEME_KEYS))
        sys.exit(0)
    keys, accent = [], None
    for arg in sys.argv[1:]:
        if arg.startswith("--accent="):
            accent = parse_colour(arg.split("=", 1)[1])
            if accent is None:
                sys.exit(f"bad --accent {arg!r}; use #rrggbb or r,g,b")
        elif arg in THEME_KEYS:
            keys.append(arg)
        else:
            sys.exit(f"unknown argument {arg!r}; themes: {', '.join(THEME_KEYS)}")
    accent = accent or BREEZE_BLUE
    for k in keys or THEME_KEYS:
        run(k, accent)
