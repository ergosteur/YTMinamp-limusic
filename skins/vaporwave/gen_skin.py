#!/usr/bin/python3
"""Vaporwave: a classic Winamp 2.x skin in the vaporwave aesthetic, drawn procedurally.

A pink-to-purple-to-cyan sunset sky, a striped retro sun setting between two palm silhouettes
and a neon wireframe grid floor on the main window; magenta chrome with hard two-pixel bevels;
dark purple glass displays with cyan/pink text and a chromatic-aberration fringe; spaced-out
"aesthetic" lettering in the titlebars; a marble bust silhouette in the About spot.

Everything is drawn here from code (gradients, anti-aliased masks and hand-made pixel fonts).
Writes the bitmaps and text files into <out>/out/, zips them flat into <out>/<name>.wsz, and
draws <out>/preview.png (main, EQ, playlist and gen frame assembled from the sprites at their
real positions, 2x).
Started from skins/ember/gen_skin.py's layouts (via skins/frutiger-aero/gen_skin.py).

    gen_skin.py [--title TEXT] [--name NAME] [--out DIR] [--list]

--title sets the main titlebar's text (default "YTMinamp"; full-width forms, U+FF01..FF5E, are
folded to their ASCII letters, and the lettering is spaced out either way),
--name the .wsz's base name (default YTMinamp-Vaporwave; readme.txt's title follows it), --out
the folder for the .wsz and the preview (default: this folder).
"""

import argparse
import os
import sys
import unicodedata
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # skins/genex_wacup.py, which finishes each .wsz
import genex_wacup  # noqa: E402

DEFAULT_NAME = "YTMinamp-Vaporwave"
DEFAULT_TITLE = "YTMinamp"
OUT = os.path.join(HERE, "out")   # set by main() from --out
TITLE = DEFAULT_TITLE             # set by main() from --title

# ------------------------------------------------------------------------------------------
# Palette
# ------------------------------------------------------------------------------------------

WHITE = (255, 255, 255)
PINK = (255, 113, 206)
HOT = (255, 60, 190)
PURPLE = (185, 103, 255)
CYAN = (1, 205, 254)
NEON_CYAN = (110, 242, 255)
SUN_YEL = (255, 246, 150)
INK = (46, 4, 84)               # dark labels on chrome
DISP = (26, 8, 52)              # the dark purple glass of the displays
DISP_GHOST = (46, 18, 80)       # unlit segments
TXT = (120, 242, 255)           # display text (cyan)
TXT_DIM = (150, 96, 206)
FRINGE = (200, 40, 160)         # the chromatic-aberration fringe on display text
SEP = (255, 0, 255)             # gen.bmp letter separators (never shown)

# 90s chrome: a hard two-pixel bevel round a vertical "chrome horizon" face
BEV = dict(hi=(255, 236, 252), lite=(255, 176, 236), shade=(150, 48, 160), dark=(34, 0, 52))
CHROME_PINK = [(0, (255, 214, 246)), (0.5, (246, 158, 232)), (0.5, (206, 92, 210)), (1, (236, 146, 240))]
CHROME_PINK_DOWN = [(0, (196, 90, 200)), (0.5, (214, 120, 220)), (0.5, (186, 76, 196)), (1, (220, 130, 228))]
CHROME_CYAN = [(0, (214, 255, 255)), (0.5, (120, 232, 252)), (0.5, (34, 170, 222)), (1, (108, 226, 255))]
CHROME_CYAN_DOWN = [(0, (40, 150, 206)), (0.5, (70, 190, 232)), (0.5, (30, 150, 206)), (1, (90, 210, 244))]
BEV_CYAN = dict(hi=(236, 255, 255), lite=(160, 240, 255), shade=(20, 120, 170), dark=(8, 30, 70))


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ramp(stops, t):
    """Colour along a list of evenly spaced stops, t in 0..1."""
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    i = min(n - 1, int(t * n))
    return lerp(stops[i], stops[i + 1], t * n - i)


def stops_at(stops, t):
    """Colour along (position, colour) stops; equal positions make a hard break."""
    if t <= stops[0][0]:
        return stops[0][1]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t0 <= t <= t1 and t1 > t0:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return stops[-1][1]


def vgrad(h, stops, w=1):
    g = np.array([stops_at(stops, (r + 0.5) / h) for r in range(h)], dtype=np.float32)
    return np.repeat(g[:, None, :], w, axis=1)


def rows_at(H, y, h, stops):
    """(H, 1, 3): the gradient laid over rows y..y+h of a canvas H tall (clamped outside)."""
    return np.array([stops_at(stops, max(0.0, min(1.0, (r + 0.5 - y) / max(1e-6, h)))) for r in range(H)],
                    dtype=np.float32)[:, None, :]


# ------------------------------------------------------------------------------------------
# Canvas helpers (numpy, H x W x 3) and anti-aliased masks
# ------------------------------------------------------------------------------------------


def new(w, h, col=(0, 0, 0)):
    a = np.zeros((h, w, 3), dtype=np.float32)
    a[:, :] = col
    return a


def rect(a, x, y, w, h, col):
    if w > 0 and h > 0:
        a[max(0, y):y + h, max(0, x):x + w] = col


def px(a, x, y, col):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        a[y, x] = col


SS = 4


def mask(w, h, fn, ss=SS):
    """Coverage (h, w) in 0..1 of whatever fn(draw, S) draws at S-times scale."""
    im = Image.new("L", (w * ss, h * ss), 0)
    fn(ImageDraw.Draw(im), ss)
    return np.asarray(im.resize((w, h), Image.BOX), dtype=np.float32) / 255.0


def ellipse_mask(w, h, x, y, ew, eh):
    return mask(w, h, lambda d, S: d.ellipse((x * S, y * S, (x + ew) * S - 1, (y + eh) * S - 1), fill=255))


def poly_mask(w, h, pts, ss=SS):
    return mask(w, h, lambda d, S: d.polygon([(px_ * S, py_ * S) for px_, py_ in pts], fill=255), ss)


def paint(a, x, y, m, col, alpha=1.0):
    """Blends a colour (tuple, or an array broadcastable to the mask) over a through mask m."""
    h, w = m.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(a.shape[1], x + w), min(a.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    mm = np.clip(m[y0 - y:y1 - y, x0 - x:x1 - x] * alpha, 0, 1)[..., None]
    c = np.asarray(col, dtype=np.float32)
    if c.ndim == 3:
        c = np.broadcast_to(c, (h, w, 3))[y0 - y:y1 - y, x0 - x:x1 - x]
    reg = a[y0:y1, x0:x1]
    a[y0:y1, x0:x1] = reg * (1 - mm) + c * mm


def blur(m, r):
    im = Image.fromarray(np.clip(m * 255, 0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, dtype=np.float32) / 255.0


def gauss(W, H, cx, cy, sx, sy=None):
    sy = sx if sy is None else sy
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) + 0.5
    return np.exp(-(((xx - cx) / sx) ** 2 + ((yy - cy) / sy) ** 2) / 2)


def save(a, name):
    img = Image.fromarray(np.clip(np.round(a), 0, 255).astype(np.uint8), "RGB")
    img.save(os.path.join(OUT, name))
    return img


# ------------------------------------------------------------------------------------------
# Fonts: 5px pixel fonts for the displays and labels, a 7px one (with descenders) for titles
# ------------------------------------------------------------------------------------------

def G(*rows):
    return list(rows)


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
    "0": G(".#.", "#.#", "#.#", "#.#", ".#."),
    "1": G(".#.", "##.", ".#.", ".#.", "###"),
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
    "\u2026": G(".....", ".....", ".....", ".....", "#.#.#"),
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
    "\u00e5": G(".##.", ".##.", "#..#", "####", "#..#"),
    "\u00f6": G("#..#", ".##.", "#..#", "#..#", ".##."),
    "\u00e4": G("#..#", ".##.", "#..#", "####", "#..#"),
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

# 7px titles: capitals on rows 0..6, lowercase x-height on rows 2..6, descenders on rows 7..8.
X = "....."
WIDE7 = {
    "A": G(".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": G("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": G(".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": G("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": G("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": G("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": G(".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"),
    "H": G("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": G("###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"),
    "J": G("..###", "...#.", "...#.", "...#.", "#..#.", "#..#.", ".##.."),
    "K": G("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": G("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": G("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": G("#...#", "##..#", "#.#.#", "#.#.#", "#..##", "#...#", "#...#"),
    "O": G(".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": G("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": G(".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": G("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": G(".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": G("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": G("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": G("#...#", "#...#", "#...#", "#...#", ".#.#.", ".#.#.", "..#.."),
    "W": G("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": G("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": G("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": G("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "a": G(X, X, ".###.", "....#", ".####", "#...#", ".####"),
    "b": G("#....", "#....", "####.", "#...#", "#...#", "#...#", "####."),
    "c": G(X, X, ".####", "#....", "#....", "#....", ".####"),
    "d": G("....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"),
    "e": G(X, X, ".###.", "#...#", "#####", "#....", ".####"),
    "f": G("..##", ".#..", "###.", ".#..", ".#..", ".#..", ".#.."),
    "g": G(X, X, ".####", "#...#", "#...#", "#...#", ".####", "....#", ".###."),
    "h": G("#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"),
    "i": G(".#.", "...", "##.", ".#.", ".#.", ".#.", "###"),
    "j": G("..#", "...", ".##", "..#", "..#", "..#", "..#", "#.#", ".#."),
    "k": G("#...", "#...", "#..#", "#.#.", "##..", "#.#.", "#..#"),
    "l": G("##.", ".#.", ".#.", ".#.", ".#.", ".#.", "###"),
    "m": G(X, X, "##.#.", "#.#.#", "#.#.#", "#.#.#", "#.#.#"),
    "n": G(X, X, "####.", "#...#", "#...#", "#...#", "#...#"),
    "o": G(X, X, ".###.", "#...#", "#...#", "#...#", ".###."),
    "p": G(X, X, "####.", "#...#", "#...#", "#...#", "####.", "#....", "#...."),
    "q": G(X, X, ".####", "#...#", "#...#", "#...#", ".####", "....#", "....#"),
    "r": G(X, X, "#.##.", "##..#", "#....", "#....", "#...."),
    "s": G(X, X, ".####", "#....", ".###.", "....#", "####."),
    "t": G(".#..", ".#..", "###.", ".#..", ".#..", ".#..", "..##"),
    "u": G(X, X, "#...#", "#...#", "#...#", "#...#", ".####"),
    "v": G(X, X, "#...#", "#...#", ".#.#.", ".#.#.", "..#.."),
    "w": G(X, X, "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."),
    "x": G(X, X, "#...#", ".#.#.", "..#..", ".#.#.", "#...#"),
    "y": G(X, X, "#...#", "#...#", "#...#", "#...#", ".####", "....#", ".###."),
    "z": G(X, X, "#####", "...#.", "..#..", ".#...", "#####"),
    "0": G(".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": G("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": G(".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": G("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": G("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": G("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": G(".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": G("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": G(".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": G(".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    "-": G("...", "...", "...", "###", "...", "...", "..."),
    ".": G(".", ".", ".", ".", ".", ".", "#"),
    "!": G("#", "#", "#", "#", "#", ".", "#"),
    "'": G("#", "#", ".", ".", ".", ".", "."),
    "&": G(".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"),
}


def glyph_w(font, c):
    return len(font[c][0])


def text_w(font, s, gap=1):
    s = [c for c in s if c in font]
    return sum(glyph_w(font, c) for c in s) + gap * max(0, len(s) - 1)


def draw_text(a, font, s, x, y, col, gap=1, shadow=None, sh_alpha=1.0):
    for c in s:
        if c not in font:
            continue
        g = font[c]
        if shadow is not None:
            for r, row in enumerate(g):
                for k, ch in enumerate(row):
                    if ch == "#" and 0 <= y + r + 1 < a.shape[0] and 0 <= x + k + 1 < a.shape[1]:
                        a[y + r + 1, x + k + 1] = a[y + r + 1, x + k + 1] * (1 - sh_alpha) + np.asarray(shadow) * sh_alpha
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    px(a, x + k, y + r, col(r) if callable(col) else col)
        x += len(g[0]) + gap
    return x


def text_center(a, font, s, cx, y, col, gap=1, shadow=None, sh_alpha=1.0):
    draw_text(a, font, s, cx - text_w(font, s, gap) // 2, y, col, gap, shadow, sh_alpha)


def fold_title(s):
    """Full-width forms (U+FF01..FF5E, the ideographic space) folded to ASCII; letters the
    title font lacks fall back to their capital, anything else to a space."""
    s = unicodedata.normalize("NFKC", s)
    out = []
    for c in s:
        if c in WIDE7 or c == " ":
            out.append(c)
        elif c.upper() in WIDE7:
            out.append(c.upper())
        else:
            out.append(" ")
    return "".join(out).strip()


def wide_layout(s, gap):
    """[(glyph, x)] for s set "full width": every glyph in a 5px cell, `gap` between cells."""
    out, x = [], 0
    for c in s:
        if c == " ":
            x += 5 + gap
            continue
        g = WIDE7[c]
        w = len(g[0])
        out.append((c, x + (5 - w + 1) // 2 if w < 5 else x))
        x += 5 + gap
    return out, max(0, x - gap)


def title_mask(s, W, H, cx, top, max_w=None):
    """(H, W) 0/1 mask of s in the spaced title font, centred on cx with caps from row `top`;
    returns (mask, x0, x1)."""
    s = fold_title(s)
    gap = 3
    lay, tw = wide_layout(s, gap)
    while max_w is not None and tw > max_w and gap > 1:
        gap -= 1
        lay, tw = wide_layout(s, gap)
    x0 = int(round(cx - tw / 2))
    m = np.zeros((H, W), np.float32)
    for c, gx in lay:
        for r, row in enumerate(WIDE7[c]):
            for k, ch in enumerate(row):
                if ch == "#" and 0 <= top + r < H and 0 <= x0 + gx + k < W:
                    m[top + r, x0 + gx + k] = 1
    return m, x0, x0 + tw


def aberrated(a, m, lit):
    """Neon title text: a dark drop, a cyan ghost one pixel left, a white core."""
    if lit:
        paint(a, 1, 1, m, (52, 0, 76), 0.85)
        paint(a, -1, 0, m, NEON_CYAN, 0.95)
        paint(a, 0, 0, m, WHITE)
    else:
        paint(a, 1, 1, m, (70, 56, 92), 0.5)
        paint(a, 0, 0, m, (224, 214, 236))


# ------------------------------------------------------------------------------------------
# Shared pieces: the sunset, the grid, the sun, palms, chrome buttons
# ------------------------------------------------------------------------------------------

SKY = [(0, (255, 128, 214)), (0.45, (186, 106, 246)), (0.82, (120, 196, 255)), (1, (150, 236, 255))]
FLOOR = [(0, (70, 10, 110)), (0.12, (40, 6, 80)), (1, (14, 2, 34))]


def sunset(w, h, top, hz, floor_glow=True):
    """The body: a pink-to-purple-to-cyan sky from row `top` down to the horizon `hz`, and a
    dark violet floor below it."""
    a = new(w, h)
    a[:hz] = np.broadcast_to(rows_at(h, top, hz - top, SKY)[:hz], (hz, w, 3))
    a[hz:] = np.broadcast_to(rows_at(h, hz, h - hz, FLOOR)[hz:], (h - hz, w, 3))
    if floor_glow:
        # the horizon line and a pink haze just above it
        rect(a, 0, hz, w, 1, (255, 150, 230))
        for i in range(1, 4):
            a[hz - i] = a[hz - i] * (1 - 0.18 * (4 - i) / 3) + np.asarray((255, 200, 240)) * 0.18 * (4 - i) / 3
    return a


def grid(a, hz, vx, step=22, x_range=None, line_alpha=0.85):
    """A neon wireframe floor below the horizon `hz`: magenta rungs that close up toward the
    horizon and cyan rails converging on (vx, hz)."""
    H, W = a.shape[:2]
    rows = []
    k = 0
    while True:
        y = hz + 1.2 * (1.42 ** k - 1) + 2
        if y >= H:
            break
        rows.append(y)
        k += 1
    fade = np.clip((np.arange(H, dtype=np.float32) - hz) / 9.0, 0, 1)[:, None]
    rungs = mask(W, H, lambda d, S: [d.rectangle((0, int(y * S), W * S, int(y * S) + S - 1), fill=255)
                                    for y in rows])
    paint(a, 0, 0, rungs * (0.35 + 0.65 * fade), (255, 70, 200), line_alpha)
    bottom = H + 2

    def rails(d, S):
        for i in range(-30, 31):
            xb = vx + i * step * 3.2
            d.line((vx * S, hz * S, xb * S, bottom * S), fill=255, width=S)
    m = mask(W, H, rails)
    m[:hz + 1] = 0
    paint(a, 0, 0, m * fade, (60, 236, 255), line_alpha)
    # a soft glow along the horizon
    glow = np.exp(-np.abs(np.arange(H, dtype=np.float32) - hz) / 2.5)[:, None] * np.ones((1, W), np.float32)
    paint(a, 0, 0, glow, (255, 120, 220), 0.35)


SUN_STOPS = [(0, SUN_YEL), (0.45, (255, 170, 120)), (0.75, (255, 90, 160)), (1, (230, 40, 170))]


def retro_sun(a, cx, cy, r, gaps):
    """A striped sun: yellow at the top to magenta at the bottom, cut by horizontal gaps
    (absolute (row, height) pairs) that let the sky through."""
    H, W = a.shape[:2]
    paint(a, 0, 0, gauss(W, H, cx, cy, r * 1.15, r * 0.9), (255, 190, 230), 0.45)
    disc = ellipse_mask(W, H, cx - r, cy - r, 2 * r, 2 * r)
    for gy, gh in gaps:
        disc[gy:gy + gh] = 0
    disc[int(cy):] = 0
    paint(a, 0, 0, disc, rows_at(H, cy - r, r, SUN_STOPS))


def palm(a, base, crown, lean, size, col, ss=8):
    """A palm silhouette: a curved tapering trunk from `base` to `crown` and drooping fronds."""
    H, W = a.shape[:2]
    bx, by = base
    tx, ty = crown

    def trunk_pt(t):
        x = (1 - t) ** 2 * bx + 2 * (1 - t) * t * (bx + lean) + t * t * tx
        y = (1 - t) ** 2 * by + 2 * (1 - t) * t * ((by + ty) / 2) + t * t * ty
        return x, y

    def fn(d, S):
        n = 24
        left, right = [], []
        for i in range(n + 1):
            t = i / n
            x, y = trunk_pt(t)
            hw = (0.75 * size * (1 - t) + 0.45 * size * t) / 2
            left.append(((x - hw) * S, y * S))
            right.append(((x + hw) * S, y * S))
        d.polygon(left + right[::-1], fill=255)
        for ang, ln, droop in ((-172, 1.0, 0.55), (-142, 0.9, 0.5), (-108, 0.62, 0.3), (-72, 0.62, 0.3),
                               (-38, 0.9, 0.5), (-8, 1.0, 0.55), (-160, 0.7, 0.85), (-20, 0.7, 0.85)):
            L = 9.0 * size * ln
            a_ = np.radians(ang)
            top_e, bot_e = [], []
            for i in range(13):
                t = i / 12
                x = tx + L * t * np.cos(a_)
                y = ty + L * t * np.sin(a_) + droop * L * t * t
                th = 0.9 * size * np.sin(np.pi * min(1, t * 1.1 + 0.08)) + 0.2
                top_e.append((x * S, (y - th / 2) * S))
                bot_e.append((x * S, (y + th / 2) * S))
            d.polygon(top_e + bot_e[::-1], fill=255)
        d.ellipse(((tx - 1.1 * size) * S, (ty - 0.9 * size) * S, (tx + 1.1 * size) * S, (ty + 1.0 * size) * S),
                  fill=255)
    paint(a, 0, 0, mask(W, H, fn, ss), col)


def bevel(a, x, y, w, h, pal, pressed=False, face=None):
    """A hard 90s two-pixel bevel round a face (stops for a vertical face gradient, or a colour)."""
    H, W = a.shape[:2]
    if face is not None:
        if isinstance(face, list):
            a[y:y + h, x:x + w] = rows_at(H, y, h, face)[y:y + h]
        else:
            rect(a, x, y, w, h, face)
    tl1, br1, tl2, br2 = ((pal["dark"], pal["hi"], pal["shade"], pal["lite"]) if pressed
                          else (pal["hi"], pal["dark"], pal["lite"], pal["shade"]))
    rect(a, x, y, w, 1, tl1)
    rect(a, x, y, 1, h, tl1)
    rect(a, x, y + h - 1, w, 1, br1)
    rect(a, x + w - 1, y, 1, h, br1)
    rect(a, x + 1, y + 1, w - 2, 1, tl2)
    rect(a, x + 1, y + 1, 1, h - 2, tl2)
    rect(a, x + 1, y + h - 2, w - 2, 1, br2)
    rect(a, x + w - 2, y + 1, 1, h - 2, br2)


def button(a, x, y, w, h, style="pink", pressed=False):
    if style == "cyan":
        bevel(a, x, y, w, h, BEV_CYAN, pressed, CHROME_CYAN_DOWN if pressed else CHROME_CYAN)
    else:
        bevel(a, x, y, w, h, BEV, pressed, CHROME_PINK_DOWN if pressed else CHROME_PINK)


def sunken(a, x, y, w, h, fill=DISP):
    """A sunken well: dark top/left, pink-white bottom/right, two pixels outside x,y,w,h."""
    rect(a, x - 2, y - 2, w + 4, h + 4, (255, 210, 246))
    rect(a, x - 2, y - 2, w + 3, 1, (120, 30, 140))
    rect(a, x - 2, y - 2, 1, h + 3, (120, 30, 140))
    rect(a, x - 1, y - 1, w + 2, h + 2, (232, 140, 230))
    rect(a, x - 1, y - 1, w + 1, 1, (20, 0, 36))
    rect(a, x - 1, y - 1, 1, h + 1, (20, 0, 36))
    if fill is not None:
        rect(a, x, y, w, h, fill)


def label(a, x, y, w, h, text, style, pressed):
    o = 1 if pressed else 0
    tx = x + (w - text_w(TINY, text)) // 2 + o
    ty = y + (h - 5) // 2 + o
    if style == "cyan":
        draw_text(a, TINY, text, tx, ty, (6, 30, 70), shadow=(220, 255, 255), sh_alpha=0.6)
    else:
        draw_text(a, TINY, text, tx, ty, INK, shadow=(255, 220, 250), sh_alpha=0.6)


ICON_KINDS = ("previous", "play", "pause", "stop", "next", "eject")


def icon_mask(kind, W, H, cx, cy, s=1.0):
    if kind == "play":
        return poly_mask(W, H, [(cx - 3 * s, cy - 4.5 * s), (cx - 3 * s, cy + 4.5 * s), (cx + 4.5 * s, cy)])
    if kind == "pause":
        return mask(W, H, lambda d, S: (
            d.rectangle(((cx - 3.5 * s) * S, (cy - 4 * s) * S, (cx - 1 * s) * S - 1, (cy + 4 * s) * S - 1), fill=255),
            d.rectangle(((cx + 1 * s) * S, (cy - 4 * s) * S, (cx + 3.5 * s) * S - 1, (cy + 4 * s) * S - 1), fill=255)))
    if kind == "stop":
        return mask(W, H, lambda d, S: d.rectangle(
            ((cx - 3.5 * s) * S, (cy - 3.5 * s) * S, (cx + 3.5 * s) * S - 1, (cy + 3.5 * s) * S - 1), fill=255))
    if kind in ("previous", "next"):
        def fn(d, S):
            sg = 1 if kind == "next" else -1
            hh = 3.5 * s
            for bx in (cx - sg * 4 * s, cx - sg * 0.5 * s):
                tip = bx + sg * 3.5 * s
                d.polygon([(bx * S, (cy - hh) * S), (bx * S, (cy + hh) * S), (tip * S, cy * S)], fill=255)
            bar = cx + sg * 3 * s
            x0, x1 = (bar, bar + 1.5 * s) if sg == 1 else (bar - 1.5 * s, bar)
            d.rectangle((x0 * S, (cy - hh) * S, x1 * S - 1, (cy + hh) * S - 1), fill=255)
        return mask(W, H, fn)
    if kind == "eject":
        return mask(W, H, lambda d, S: (
            d.polygon([((cx - 4 * s) * S, (cy + 0.5 * s) * S), ((cx + 4 * s) * S, (cy + 0.5 * s) * S),
                       (cx * S, (cy - 3.8 * s) * S)], fill=255),
            d.rectangle(((cx - 4 * s) * S, (cy + 2 * s) * S, (cx + 4 * s) * S - 1, (cy + 3.5 * s) * S - 1),
                        fill=255)))
    raise ValueError(kind)


def glyph(a, kind, cx, cy, s, pressed):
    """A transport glyph with a chromatic split: cyan ghost left, magenta ghost right."""
    H, W = a.shape[:2]
    m = icon_mask(kind, W, H, cx, cy, s)
    paint(a, 0, 0, np.roll(m, -1, axis=1), (0, 190, 240), 0.9)
    paint(a, 0, 0, np.roll(m, 1, axis=1), HOT, 0.9)
    paint(a, 0, 0, m, (40, 0, 76) if not pressed else (24, 0, 50))


def mini_button(a, x, y, kind, lit=True, pressed=False):
    """9x9 titlebar button: a small raised chrome key (grey-lilac when the window is unfocused)."""
    cell = a[y:y + 9, x:x + 9]
    if lit or pressed:
        button(cell, 0, 0, 9, 9, "pink", pressed)
        ink = INK
    else:
        bevel(cell, 0, 0, 9, 9, dict(hi=(240, 232, 246), lite=(210, 198, 222), shade=(130, 116, 150),
                                     dark=(60, 48, 76)), False, (190, 178, 204))
        ink = (90, 76, 110)
    o = 1 if pressed else 0
    if kind == "close":
        for i in range(5):
            px(cell, 2 + i + o, 2 + i + o, ink)
            px(cell, 6 - i + o, 2 + i + o, ink)
    elif kind == "minimize":
        rect(cell, 2 + o, 5 + o, 5, 2, ink)
    elif kind == "shade":
        rect(cell, 2 + o, 2 + o, 5, 2, ink)
        rect(cell, 2 + o, 5 + o, 5, 1, ink)
    else:  # options: a small diamond
        for r, w in ((2, 1), (3, 3), (4, 5), (5, 3), (6, 1)):
            rect(cell, 4 - w // 2 + o, r + o, w, 1, ink)


# ------------------------------------------------------------------------------------------
# Titlebars: magenta chrome, two neon racing lines either side of the title
# ------------------------------------------------------------------------------------------

BAR_LIT = [(0, (255, 132, 222)), (0.5, (226, 62, 190)), (1, (130, 22, 150))]
BAR_DIM = [(0, (196, 184, 212)), (0.5, (164, 150, 184)), (1, (122, 108, 142))]


def bar(w, h, lit):
    """A titlebar strip (vertical-only): light top edge, chrome body, dark bottom edge."""
    a = vgrad(h, BAR_LIT if lit else BAR_DIM, w)
    rect(a, 0, 0, w, 1, (255, 214, 246) if lit else (236, 230, 242))
    rect(a, 0, h - 1, w, 1, (44, 0, 64) if lit else (78, 66, 94))
    return a


def stripes(a, x0, x1, rows, lit):
    """Two neon racing lines (cyan over pink) across columns x0..x1."""
    if x1 <= x0:
        return
    c1, c2 = ((NEON_CYAN, (255, 196, 246)) if lit else ((214, 206, 226), (204, 194, 218)))
    rect(a, x0, rows[0], x1 - x0, 1, c1)
    rect(a, x0, rows[1], x1 - x0, 1, c2)


def main_titlebar(lit):
    a = bar(275, 14, lit)
    rect(a, 0, 0, 1, 14, (255, 214, 246) if lit else (236, 230, 242))
    rect(a, 274, 0, 1, 14, (44, 0, 64) if lit else (78, 66, 94))
    m, x0, x1 = title_mask(TITLE, 275, 14, 137, 2, max_w=200)
    stripes(a, 19, x0 - 7, (5, 8), lit)
    stripes(a, x1 + 7, 240, (5, 8), lit)
    aberrated(a, m, lit)
    mini_button(a, 6, 3, "options", lit)
    mini_button(a, 244, 3, "minimize", lit)
    mini_button(a, 254, 3, "shade", lit)
    mini_button(a, 264, 3, "close", lit)
    return a


# ------------------------------------------------------------------------------------------
# main.bmp (275 x 116)
# ------------------------------------------------------------------------------------------

HZ = 87               # the main window's horizon
SUN = (60, HZ, 27)    # centre x, centre y, radius


def bust(a, x, y, s=1.0):
    """A small marble bust in profile, facing left (the About spot), top-left at x, y: the
    head, a long straight nose, curls in a pinker marble, the cut chest on a two-step plinth."""
    H, W = a.shape[:2]

    def shape(parts):
        def fn(d, S):
            def P(px_, py_):
                return ((x + px_ * s) * S, (y + py_ * s) * S)

            def E(cx, cy, rx, ry):
                d.ellipse(P(cx - rx, cy - ry) + P(cx + rx, cy + ry), fill=255)
            if parts == "head":
                E(8.0, 5.0, 3.6, 4.2)
                d.polygon([P(5.4, 1.4), P(4.4, 2.6), P(4.2, 3.6), P(2.0, 6.6), P(3.6, 6.9), P(3.4, 7.5),
                           P(3.9, 7.9), P(3.6, 8.5), P(4.0, 9.4), P(5.6, 9.9), P(8.0, 9.0), P(8.0, 1.4)], fill=255)
                d.polygon([P(6.0, 8.8), P(10.0, 8.8), P(10.4, 12.2), P(5.8, 12.2)], fill=255)
                d.polygon([P(1.0, 16.0), P(1.9, 13.4), P(5.2, 11.9), P(10.8, 11.9), P(12.9, 13.4),
                           P(13.7, 16.0)], fill=255)
                d.rectangle(P(2.6, 16.0) + P(12.1, 17.2), fill=255)
                d.rectangle(P(1.6, 17.2) + P(13.1, 18.4), fill=255)
            else:
                for cx, cy, r in ((6.2, 1.4, 1.3), (8.2, 0.9, 1.4), (10.2, 1.7, 1.4), (11.4, 3.6, 1.3),
                                  (11.6, 5.7, 1.2), (11.1, 7.6, 1.1), (9.0, 2.6, 1.3), (10.0, 4.6, 1.2)):
                    E(cx, cy, r, r)
        return mask(W, H, fn, 8)
    mh, mc = shape("head"), shape("hair")
    m = np.maximum(mh, mc)
    paint(a, 0, 0, np.clip(blur(m, 0.6) * 3.0, 0, 1), (30, 0, 50), 0.85)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) + 0.5
    t = np.clip((xx - x - 2 * s) / (11 * s), 0, 1)[..., None]
    paint(a, 0, 0, m, np.asarray((244, 254, 255), np.float32) * (1 - t) + np.asarray((240, 170, 232), np.float32) * t)
    paint(a, 0, 0, mc * (1 - 0.6 * mh), (214, 110, 214))
    paint(a, 0, 0, mc * mh, (226, 140, 224), 0.8)
    paint(a, 0, 0, m * gauss(W, H, x + 5.6 * s, y + 4.6 * s, 0.45 * s, 0.35 * s), (90, 30, 130), 0.9)   # eye
    paint(a, 0, 0, m * gauss(W, H, x + 7.8 * s, y + 10.6 * s, 2.0 * s, 0.7 * s), (150, 70, 180), 0.6)   # jaw
    paint(a, 0, 0, m * gauss(W, H, x + 7.2 * s, y + 16.1 * s, 6 * s, 0.35 * s), (150, 70, 180), 0.7)   # plinth


def main_bg():
    """The main window's background before any control is drawn on it."""
    a = sunset(275, 116, 14, HZ)
    cx, cy, r = SUN
    retro_sun(a, cx, cy, r, gaps=[(HZ - 17, 1), (HZ - 6, 1), (HZ - 3, 2)])
    grid(a, HZ, 137)
    palm(a, (6, HZ + 1), (15, 68), -5, 1.2, (36, 4, 62))
    palm(a, (99, HZ + 1), (97, 67), 4, 1.0, (36, 4, 62))
    return a


def display_box(a, x, y, w, h, gloss_rows=3):
    sunken(a, x, y, w, h)
    for i in range(gloss_rows):
        rect(a, x, y + i, w, 1, lerp(DISP, (120, 60, 170), 0.5 * (1 - i / gloss_rows) ** 1.5))


SEG = {
    "a": [(0, c) for c in range(2, 7)],
    "g": [(6, c) for c in range(2, 7)],
    "d": [(12, c) for c in range(2, 7)],
    "f": [(r, c) for r in range(1, 6) for c in (1, 2)],
    "b": [(r, c) for r in range(1, 6) for c in (6, 7)],
    "e": [(r, c) for r in range(7, 12) for c in (1, 2)],
    "c": [(r, c) for r in range(7, 12) for c in (6, 7)],
}
DIGIT_SEGS = {
    0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc",
    5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg",
}


def seg_col(r):
    return lerp((255, 190, 240), PINK, r / 12)


def seven_seg(a, x, y, lit_segs):
    rect(a, x, y, 9, 13, DISP)
    on = set()
    for s in lit_segs:
        on.update(SEG[s])
    for s, cells in SEG.items():
        if s not in lit_segs:
            for r, c in cells:
                px(a, x + c, y + r, DISP_GHOST)
    # chromatic split: a cyan ghost one pixel left of the pink segments
    for r, c in on:
        if (r, c - 1) not in on:
            px(a, x + c - 1, y + r, (30, 150, 200))
    for r, c in on:
        px(a, x + c, y + r, seg_col(r))


TRANSPORT = [("previous", 16, 23), ("play", 39, 23), ("pause", 62, 23), ("stop", 85, 23), ("next", 108, 22)]
EJECT = (136, 89, 22, 16)


def transport_cell(kind, w, h, pressed):
    c = new(w, h)
    button(c, 0, 0, w, h, "pink", pressed)
    o = 1 if pressed else 0
    glyph(c, kind, w / 2 + o + (0.5 if kind == "play" else 0), h / 2 + o, 1.0 if kind != "eject" else 0.9, pressed)
    return c


def volume_strip(seat, level=None):
    """68x13: a sunken groove over its seat, lit cyan-to-pink up to level 0..1."""
    a = seat.copy()
    sunken(a, 3, 5, 62, 3, (16, 4, 34))
    if level:
        n = int(round(level * 62))
        for c in range(n):
            col = ramp([NEON_CYAN, PURPLE, PINK], c / 61)
            rect(a, 3 + c, 5, 1, 3, col)
            px(a, 3 + c, 5, lerp(col, WHITE, 0.5))
    return a


def balance_strip(seat, t=None):
    """38x13: a short groove lit outward from its middle by t 0..1."""
    a = seat.copy()
    sunken(a, 3, 5, 32, 3, (16, 4, 34))
    if t:
        n = int(round(t * 15))
        for c in range(n + 1):
            col = ramp([NEON_CYAN, PINK], c / 15)
            for xx in (18 - c, 19 + c):
                if 3 <= xx < 35:
                    rect(a, xx, 5, 1, 3, col)
                    px(a, xx, 5, lerp(col, WHITE, 0.5))
    rect(a, 18, 1, 2, 2, (40, 0, 70))
    return a


def make_main():
    a = main_bg()
    base = a.copy()
    rect(a, 0, 0, 1, 116, (255, 214, 246))
    rect(a, 274, 0, 1, 116, (44, 0, 64))
    rect(a, 0, 115, 275, 1, (44, 0, 64))
    a[0:14, :] = main_titlebar(True)

    display_box(a, 21, 20, 84, 41, gloss_rows=4)
    for x in (48, 60, 78, 90):
        seven_seg(a, x, 26, "")
    for yy in (29, 34):
        rect(a, 73, yy, 2, 2, PINK)
        px(a, 72, yy, (30, 150, 200))
        px(a, 72, yy + 1, (30, 150, 200))
    display_box(a, 109, 21, 159, 14, gloss_rows=3)
    display_box(a, 109, 40, 159, 14, gloss_rows=0)
    draw_text(a, TINY, "KBPS", 129, 44, TXT_DIM)
    draw_text(a, TINY, "KHZ", 169, 44, TXT_DIM)

    a[57:70, 107:175] = volume_strip(base[57:70, 107:175], 0.72)
    a[57:70, 177:215] = balance_strip(base[57:70, 177:215])
    # the seek groove: one dark, one deep and one light row
    rect(a, 18, 76, 244, 1, (34, 0, 56))
    rect(a, 18, 77, 244, 1, (16, 4, 34))
    rect(a, 18, 78, 244, 1, (255, 210, 246))
    for kind, x, w in TRANSPORT:
        a[88:106, x:x + w] = transport_cell(kind, w, 18, False)
    x, y, w, h = EJECT
    a[y:y + h, x:x + w] = transport_cell("eject", w, h, False)
    bust(a, 251, 89, 1.2)
    return a, base


# ------------------------------------------------------------------------------------------
# titlebar.bmp (344 x 87): buttons, bars, clutterbar
# ------------------------------------------------------------------------------------------

CLUTTER_SLOTS = [("O", 3, 8), ("A", 11, 7), ("I", 18, 7), ("D", 25, 8), ("V", 33, 7)]


def clutter_bar(lit_letters):
    """8x43: a slim chrome strip with the letters; lit ones on cyan."""
    a = new(8, 43)
    bevel(a, 0, 0, 8, 43, BEV, False, [(0, (246, 158, 232)), (1, (214, 110, 220))])
    for letter, y, h in CLUTTER_SLOTS:
        if letter in lit_letters:
            rect(a, 1, y, 6, h, (110, 236, 255))
            rect(a, 1, y, 6, 1, (220, 255, 255))
        draw_text(a, TINY, letter, 2, y + (h - 5) // 2, INK)
    return a


def make_titlebar(main):
    a = new(344, 87, (214, 110, 220))
    plain = bar(275, 14, True)
    for kind, x in (("options", 0), ("minimize", 9), ("close", 18)):
        for pressed, y in ((False, 0), (True, 9)):
            c = plain[3:12, 0:9].copy()
            mini_button(c, 0, 0, kind, True, pressed)
            a[y:y + 9, x:x + 9] = c
    for pressed, x in ((False, 0), (True, 9)):
        c = plain[3:12, 0:9].copy()
        mini_button(c, 0, 0, "shade", True, pressed)
        a[18:27, x:x + 9] = c
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
    main[22:65, 10:18] = unlit
    return a


# ------------------------------------------------------------------------------------------
# cbuttons.bmp (136 x 36), shufrep.bmp (92 x 85)
# ------------------------------------------------------------------------------------------


def make_cbuttons(main):
    a = new(136, 36)
    sx = {"previous": 0, "play": 23, "pause": 46, "stop": 69, "next": 92}
    for kind, x, w in TRANSPORT:
        a[0:18, sx[kind]:sx[kind] + w] = main[88:106, x:x + w]
        a[18:36, sx[kind]:sx[kind] + w] = transport_cell(kind, w, 18, True)
    a[0:16, 114:136] = main[89:105, 136:158]
    a[16:32, 114:136] = transport_cell("eject", 22, 16, True)
    a[32:36, 114:136] = main[105:109, 136:158]
    return a


def make_shufrep():
    a = new(92, 85, (214, 110, 220))
    for row, (on, pressed) in enumerate([(False, False), (False, True), (True, False), (True, True)]):
        y = row * 15
        style = "cyan" if on else "pink"
        for x, w, text in ((0, 28, "REPEAT"), (28, 47, "SHUFFLE")):
            cell = new(w, 15)
            button(cell, 0, 0, w, 15, style, pressed)
            label(cell, 0, 0, w, 15, text, style, pressed)
            a[y:y + 15, x:x + w] = cell
    for x, text, pressed in [(0, "EQ", False), (23, "PL", False), (46, "EQ", True), (69, "PL", True)]:
        for on, y in ((False, 61), (True, 73)):
            style = "cyan" if on else "pink"
            cell = new(23, 12)
            button(cell, 0, 0, 23, 12, style, pressed)
            label(cell, 0, 0, 23, 12, text, style, pressed)
            a[y:y + 12, x:x + 23] = cell
    return a


# ------------------------------------------------------------------------------------------
# monoster, playpaus, numbers, nums_ex, text
# ------------------------------------------------------------------------------------------


def make_monoster(main):
    a = new(56, 24, DISP)
    for y, on in ((0, True), (12, False)):
        a[y:y + 12, 0:29] = main[41:53, 239:268]
        a[y:y + 12, 29:56] = main[41:53, 212:239]
        col = NEON_CYAN if on else DISP_GHOST
        text_center(a, TINY, "STEREO", 14, y + 4, col)
        text_center(a, TINY, "MONO", 29 + 13, y + 4, col)
    return a


def make_playpaus():
    a = new(48, 9, DISP)
    cell = a[:, 0:9]
    m = poly_mask(9, 9, [(2, 1), (2, 8), (8, 4.5)])
    paint(cell, -1, 0, m, (30, 150, 200))
    paint(cell, 0, 0, m, NEON_CYAN)
    rect(a, 9 + 2, 1, 2, 7, PINK)
    rect(a, 9 + 5, 1, 2, 7, PINK)
    rect(a, 18 + 2, 2, 5, 5, TXT_DIM)
    rect(a, 36, 0, 3, 9, DISP)
    rect(a, 39 + 1, 3, 1, 3, NEON_CYAN)
    return a


def make_numbers(ex):
    a = new(108 if ex else 99, 13, DISP)
    for n in range(10):
        seven_seg(a, 9 * n, 0, DIGIT_SEGS[n])
    seven_seg(a, 90, 0, "")
    if ex:
        rect(a, 99, 0, 9, 13, DISP)
        seven_seg(a, 99, 0, "g")
        for r, c in SEG["f"] + SEG["b"] + SEG["e"] + SEG["c"] + SEG["a"] + SEG["d"]:
            px(a, 99 + c, r, DISP)
    return a


FONT_GRID = [
    list("abcdefghijklmnopqrstuvwxyz\"@") + [None, None, " "],
    list("0123456789") + ["\u2026", ".", ":", "(", ")", "-", "'", "!", "_", "+", "\\", "/", "[", "]", "^", "&",
                          "%", ",", "=", "$", "#"],
    ["\u00e5", "\u00f6", "\u00e4", "?", "*"] + [None] * 26,
]


def make_text():
    """Cyan letters with a dim magenta fringe on their right (kept inside each 5px cell, and
    always fewer pixels than the cyan, so the cyan stays the ink colour the app reads)."""
    a = new(155, 18, DISP)
    for row, chars in enumerate(FONT_GRID):
        for col, ch in enumerate(chars):
            if ch is None or ch == " ":
                continue
            key = ch if ch in FONT5 else ch.upper()
            g = FONT5[key]
            x0, y0 = col * 5, row * 6
            for r, line in enumerate(g):
                for k, c in enumerate(line):
                    if c == "#" and k + 1 < 5 and (k + 1 >= len(line) or line[k + 1] != "#"):
                        px(a, x0 + k + 1, y0 + r, lerp(DISP, FRINGE, 0.55))
            draw_text(a, FONT5, key, x0, y0, TXT)
    return a


# ------------------------------------------------------------------------------------------
# posbar.bmp (307 x 10), volume.bmp / balance.bmp (68 x 433)
# ------------------------------------------------------------------------------------------


def thumb(w, h, pressed):
    c = new(w, h)
    button(c, 0, 0, w, h, "cyan" if pressed else "pink", False)
    return c


def make_posbar(main):
    a = new(307, 10)
    a[0:10, 0:248] = main[72:82, 16:264]
    for x0, sel in ((248, False), (278, True)):
        c = thumb(29, 10, sel)
        for gx in (10, 13, 16):     # grip ridges
            rect(c, gx, 3, 1, 4, (110, 30, 130) if not sel else (10, 80, 130))
            rect(c, gx + 1, 3, 1, 4, (255, 236, 252))
        a[0:10, x0:x0 + 29] = c
    return a


def slider_thumb(pressed):
    c = thumb(14, 11, pressed)
    rect(c, 6, 3, 1, 5, (110, 30, 130) if not pressed else (10, 80, 130))
    rect(c, 7, 3, 1, 5, (255, 236, 252))
    return c


def make_volume(base):
    a = new(68, 433, (214, 110, 220))
    seat = base[57:70, 107:175]
    for i in range(28):
        y = i * 15
        a[y:y + 13, 0:68] = volume_strip(seat, (i + 1) / 28)
        a[y + 13:y + 15, 0:68] = base[70:72, 107:175]
    a[422:433, 0:14] = slider_thumb(True)
    a[422:433, 15:29] = slider_thumb(False)
    return a


def make_balance(base):
    a = new(68, 433, (214, 110, 220))
    seat = base[57:70, 177:215]
    for i in range(28):
        y = i * 15
        a[y:y + 13, 9:47] = balance_strip(seat, i / 27)
        a[y + 13:y + 15, 9:47] = base[70:72, 177:215]
        a[y:y + 15, 0:9] = base[57:72, 168:177]
        a[y:y + 15, 47:68] = base[57:72, 215:236]
    a[422:433, 0:14] = slider_thumb(True)
    a[422:433, 15:29] = slider_thumb(False)
    return a


# ------------------------------------------------------------------------------------------
# eqmain.bmp (275 x 315)
# ------------------------------------------------------------------------------------------

EQ_BANDS = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]
BAY = (14, 37, 248, 75)    # x, y, w, h of the sliders' dark glass bay (labels included)
EQ_HZ = 64
BAY_STOPS = [(0, (40, 12, 76)), (1, (16, 4, 36))]


def eq_titlebar(lit):
    a = bar(275, 14, lit)
    rect(a, 0, 0, 1, 14, (255, 214, 246) if lit else (236, 230, 242))
    rect(a, 274, 0, 1, 14, (44, 0, 64) if lit else (78, 66, 94))
    m, x0, x1 = title_mask("EQUALIZER", 275, 14, 137, 2)
    stripes(a, 6, x0 - 7, (5, 8), lit)
    stripes(a, x1 + 7, 258, (5, 8), lit)
    aberrated(a, m, lit)
    mini_button(a, 264, 3, "close", lit)
    return a


def eq_bg():
    a = sunset(275, 116, 14, EQ_HZ)
    grid(a, EQ_HZ, 137, step=18)
    palm(a, (4, EQ_HZ + 1), (8, 44), -3, 0.8, (36, 4, 62))
    palm(a, (271, EQ_HZ + 1), (267, 44), 3, 0.8, (36, 4, 62))
    x, y, w, h = BAY
    sunken(a, x, y, w, h, None)
    a[y:y + h, x:x + w] = rows_at(116, y, h, BAY_STOPS)[y:y + h]
    # faint scanlines at +12 / 0 / -12 dB (horizontal, so every slider column matches)
    for yy in (43, 68, 93):
        rect(a, x, yy, w, 1, (64, 26, 104))
    return a


def eq_frame(bay_col, n):
    """14x63: a sunken groove lit cyan-to-pink from the bottom up to the value (n of 0..27)."""
    a = bay_col.copy()
    sunken(a, 6, 3, 2, 57, (10, 2, 24))
    top = 3 + round((1 - n / 27) * 56)
    for r in range(top, 60):
        a[r, 6:8] = ramp([PINK, PURPLE, NEON_CYAN], (r - 3) / 56)
    return a


def make_eqmain():
    bg = eq_bg()
    a = new(275, 315, (214, 110, 220))
    a[0:116] = bg
    rect(a, 0, 0, 1, 116, (255, 214, 246))
    rect(a, 274, 0, 1, 116, (44, 0, 64))
    rect(a, 0, 115, 275, 1, (44, 0, 64))
    a[0:14, :] = eq_titlebar(True)
    sunken(a, 86, 17, 113, 19)
    rect(a, 41, 40, 1, 61, (90, 40, 140))
    for text, yy in (("+12DB", 41), ("+0DB", 66), ("-12DB", 91)):
        text_center(a, TINY, text, 59, yy, NEON_CYAN)
    bay_col = bg[38:101, 78:92]
    for x in [21] + [78 + 18 * i for i in range(10)]:
        a[38:101, x:x + 14] = eq_frame(bay_col, 14)
    text_center(a, TINY, "PREAMP", 28, 104, PINK)
    for i, text in enumerate(EQ_BANDS):
        text_center(a, TINY, text, 78 + 18 * i + 7, 104, PINK)

    def toggle(w, text, on, pressed):
        c = new(w, 12)
        style = "cyan" if on else "pink"
        button(c, 0, 0, w, 12, style, pressed)
        label(c, 0, 0, w, 12, text, style, pressed)
        return c
    a[18:30, 14:40] = toggle(26, "ON", False, False)
    a[18:30, 40:72] = toggle(32, "AUTO", False, False)
    for x, text, on, pressed in [
        (10, "ON", False, False), (36, "AUTO", False, False), (69, "ON", True, False), (95, "AUTO", True, False),
        (128, "ON", False, True), (154, "AUTO", False, True), (187, "ON", True, True), (213, "AUTO", True, True),
    ]:
        w = 26 if text == "ON" else 32
        a[119:131, x:x + w] = toggle(w, text, on, pressed)
    cell = eq_titlebar(True)[3:12, 264:273].copy()
    mini_button(cell, 0, 0, "close", True, pressed=True)
    a[125:134, 0:9] = cell
    a[134:148, :] = eq_titlebar(True)
    a[149:163, :] = eq_titlebar(False)
    for y, pressed in ((164, False), (176, True)):
        c = thumb(11, 11, pressed)
        rect(c, 3, 5, 5, 1, (110, 30, 130) if not pressed else (10, 80, 130))
        rect(c, 3, 6, 5, 1, (255, 236, 252))
        a[y:y + 11, 0:11] = c
    for n in range(28):
        a[164 + (n // 14) * 65:164 + (n // 14) * 65 + 63, 13 + (n % 14) * 15:13 + (n % 14) * 15 + 14] = \
            eq_frame(bay_col, n)
    for y, pressed in ((164, False), (176, True)):
        c = toggle(44, "PRESETS", False, pressed)
        a[y:y + 12, 224:268] = c
        if not pressed:
            a[18:30, 217:261] = c
    # graph: dark glass with a faint grid, the line colours, the preamp line
    rect(a, 0, 294, 113, 19, DISP)
    for x in range(0, 113, 12):
        for y in range(1, 19, 2):
            px(a, 2 + x, 294 + y, (52, 22, 90))
    for x in range(0, 113, 2):
        px(a, x, 294 + 9, (70, 30, 110))
    for r in range(19):
        px(a, 115, 294 + r, ramp([PINK, PURPLE, NEON_CYAN], r / 18))
    for x in range(113):
        px(a, x, 314, (255, 246, 150) if x % 3 != 2 else DISP)
    a[17:36, 86:199] = a[294:313, 0:113]
    return a


# ------------------------------------------------------------------------------------------
# pledit.bmp (280 x 186) and gen.bmp (194 x 109): the 20px-titled frames. Every piece that
# tiles is vertical-only (sides) or horizontal-only (bars): one magenta chrome material.
# ------------------------------------------------------------------------------------------

FACE = [(0, (226, 104, 214)), (1, (176, 60, 186))]       # the frames' chrome face
EDGE_HI, EDGE_LO = (255, 214, 246), (44, 0, 64)
RIM = (60, 220, 255)                                      # cyan rim round the content


def bar20(w, lit):
    return bar(w, 20, lit)


def side_profile(w, outer_left):
    """One row of a side tile: outer bevel, chrome face, inner bevel and a cyan rim."""
    cols = [lerp((236, 132, 226), (186, 70, 196), c / max(1, w - 1)) for c in range(w)]
    if outer_left:
        cols[0], cols[1] = EDGE_HI, (255, 170, 236)
        cols[-3], cols[-2], cols[-1] = (120, 30, 140), RIM, (20, 0, 40)
    else:
        cols[0], cols[1], cols[2] = (20, 0, 40), RIM, (255, 170, 236)
        cols[-2], cols[-1] = (120, 30, 140), EDGE_LO
    return np.array(cols, np.float32)


def side_tile(w, h, outer_left):
    return np.repeat(side_profile(w, outer_left)[None, :, :], h, axis=0)


def groove_v(t, x, w):
    """A sunken channel down a tile (the playlist's scrollbar groove)."""
    t[:, x] = (20, 0, 40)
    t[:, x + 1:x + w - 1] = (30, 8, 56)
    t[:, x + w - 1] = (255, 190, 244)


def bottom_base(w, h=38):
    """The bottom bar (horizontal-only): cyan rim and dark line on top, chrome face, dark base."""
    t = vgrad(h, FACE, w)
    rect(t, 0, 0, w, 1, (20, 0, 40))
    rect(t, 0, 1, w, 1, RIM)
    rect(t, 0, 2, w, 1, (255, 170, 236))
    rect(t, 0, h - 2, w, 1, (120, 30, 140))
    rect(t, 0, h - 1, w, 1, EDGE_LO)
    return t


def text_button(t, x, y, w, h, text):
    button(t, x, y, w, h, "pink", False)
    label(t, x, y, w, h, text, "pink", False)


def mini_transport(t, kind, x, y):
    cell = t[y:y + 10, x:x + 10]
    button(cell, 0, 0, 10, 10, "pink", False)
    m = icon_mask(kind, 10, 10, 5 + (0.3 if kind == "play" else 0), 5, 0.55)
    paint(cell, 0, 0, m, INK)


def grip(t, x, y, n):
    for k in range(n):
        for j in range(k + 1):
            gx, gy = x - 3 * k + 3 * j, y - 3 * j
            px(t, gx + 1, gy + 1, (60, 0, 80))
            px(t, gx, gy, (255, 236, 252))


def title_piece(w, text, lit, top=6):
    """A 20px bar with a spaced title centred and the racing lines either side."""
    t = bar20(w, lit)
    m, x0, x1 = title_mask(text, w, 20, w / 2, top, max_w=w - 12)
    # the lines run into its 4px end caps only: the app stretches column 5 (plain) under a label
    stripes(t, 0, 4, (8, 11), lit)
    stripes(t, w - 4, w, (8, 11), lit)
    aberrated(t, m, lit)
    return t, x0, x1


def make_pledit():
    a = new(280, 186, (214, 110, 220))
    for lit, y in ((True, 0), (False, 21)):
        t = bar20(25, lit)
        stripes(t, 0, 25, (8, 11), lit)
        a[y:y + 20, 127:152] = t
        t = bar20(25, lit)
        stripes(t, 3, 25, (8, 11), lit)
        rect(t, 0, 0, 1, 20, EDGE_HI if lit else (236, 230, 242))
        a[y:y + 20, 0:25] = t
        t, _, _ = title_piece(100, "PLAYLIST", lit)
        a[y:y + 20, 26:126] = t
        t = bar20(25, lit)
        stripes(t, 0, 11, (8, 11), lit)
        rect(t, 24, 0, 1, 20, EDGE_LO if lit else (78, 66, 94))
        mini_button(t, 14, 3, "close", lit)
        a[y:y + 20, 153:178] = t

    a[42:71, 0:12] = side_tile(12, 29, True)
    t = side_tile(20, 29, False)
    groove_v(t, 5, 10)
    a[42:71, 31:51] = t
    cell = bar20(25, True)[3:12, 14:23].copy()
    mini_button(cell, 0, 0, "close", True, pressed=True)
    a[42:51, 52:61] = cell
    for x, sel in ((52, False), (61, True)):
        c = new(8, 18)
        button(c, 0, 0, 8, 18, "cyan" if sel else "pink", False)
        for gy in (6, 8, 10):
            rect(c, 2, gy, 4, 1, (110, 30, 130) if not sel else (10, 80, 130))
        a[53:71, x:x + 8] = c

    t = bottom_base(125)
    t[:, 0:12] = side_tile(12, 38, True)
    for r in range(3):   # the left tile's inner bevel turns the corner into the bottom bar's top
        t[r, 9:12] = bottom_base(1)[r, 0]
    rect(t, 0, 37, 125, 1, EDGE_LO)
    rect(t, 0, 36, 125, 1, (120, 30, 140))
    rect(t, 0, 0, 1, 37, EDGE_HI)
    for bx, text in ((14, "ADD"), (43, "REM"), (72, "SEL"), (101, "MISC")):
        text_button(t, bx, 8, 22, 18, text)
    a[72:110, 0:125] = t

    t = bottom_base(150)
    t[:, 130:150] = side_tile(20, 38, False)
    for r in range(3):
        t[r, 130:133] = bottom_base(1)[r, 0]
    rect(t, 0, 37, 150, 1, EDGE_LO)
    rect(t, 0, 36, 149, 1, (120, 30, 140))
    sunken(t, 6, 9, 56, 8)
    for k, kind in enumerate(ICON_KINDS):
        mini_transport(t, kind, 3 + 10 * k, 22)
    sunken(t, 66, 22, 32, 8)
    text_button(t, 106, 8, 22, 18, "LIST")
    grip(t, 145, 32, 4)
    a[72:110, 126:276] = t

    a[0:38, 179:204] = bottom_base(25)
    return a


GEN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def make_gen():
    a = new(194, 109, (214, 110, 220))
    for lit, y in ((True, 0), (False, 21)):
        def piece(px0, fn):
            t = bar20(25, lit)
            fn(t)
            a[y:y + 20, px0:px0 + 25] = t

        def left(t):
            stripes(t, 3, 25, (8, 11), lit)
            rect(t, 0, 0, 1, 20, EDGE_HI if lit else (236, 230, 242))

        def left_end(t):
            stripes(t, 0, 19, (8, 11), lit)

        def right_end(t):
            stripes(t, 6, 25, (8, 11), lit)

        def filler(t):
            stripes(t, 0, 25, (8, 11), lit)

        def right(t):
            stripes(t, 0, 11, (8, 11), lit)
            mini_button(t, 14, 3, "close", lit)
            rect(t, 24, 0, 1, 20, EDGE_LO if lit else (78, 66, 94))

        piece(0, left)
        piece(26, left_end)
        piece(52, lambda t: None)
        piece(78, right_end)
        piece(104, filler)
        piece(130, right)

    def bottom(w, grip_, left_edge):
        t = bottom_base(w, 14)
        if left_edge:
            rect(t, 0, 0, 1, 14, EDGE_HI)
        else:
            rect(t, w - 1, 0, 1, 14, EDGE_LO)
        if grip_:
            grip(t, w - 4, 10, 3)
        return t

    a[42:56, 0:125] = bottom(125, False, True)
    a[57:71, 0:125] = bottom(125, True, False)
    a[72:86, 127:152] = bottom_base(25, 14)
    # the app widens the 8px right side to 11 by stretching its inner column, so both sides end
    # in a 4px dark mat round the picture
    for x, w, h, outer_left in ((127, 11, 29, True), (158, 11, 24, True), (139, 8, 29, False), (170, 8, 24, False)):
        t = side_tile(w, h, outer_left)
        if outer_left:
            face = side_profile(12, True)[3]
            for c, col in enumerate([EDGE_HI, (255, 170, 236), face, face, face, (120, 30, 140), RIM]
                                    + [(20, 0, 40)] * 4):
                t[:, c] = col
        a[42:42 + h, x:x + w] = t
    cell = bar20(25, True)[3:12, 14:23].copy()
    mini_button(cell, 0, 0, "close", True, pressed=True)
    a[42:51, 148:157] = cell

    # letters: each in its own cell (the bar's rows 4..10 under it) with a pixel of air either
    # side for the spaced-out look, 1px separators of x 0's colour
    for lit, y in ((True, 88), (False, 96)):
        rect(a, 0, y, 194, 7, SEP)
        strip = bar20(1, lit)[4:11, 0]
        x = 1
        for c in GEN_LETTERS:
            w = glyph_w(FONT5, c) + 2
            a[y:y + 7, x:x + w] = strip[:, None, :]
            cell = a[y:y + 7, x:x + w]
            m = np.zeros((7, w), np.float32)
            for r, row in enumerate(FONT5[c]):
                for k, ch in enumerate(row):
                    if ch == "#":
                        m[1 + r, 1 + k] = 1
            aberrated(cell, m, lit)
            x += w + 1
        assert x <= 194, x
    return a


# ------------------------------------------------------------------------------------------
# genex.bmp: Media Library colours along the top row, every other pixel from x 48
# ------------------------------------------------------------------------------------------

GENEX_COLOURS = [
    (22, 6, 44),       # item background
    (255, 176, 234),   # item text
    (36, 12, 66),      # window background
    (46, 4, 84),       # button text
    (240, 214, 255),   # window text
    (110, 50, 150),    # dividers, sunken borders
    (96, 44, 150),     # selection bar
    (60, 20, 100),     # list header background
    (130, 240, 255),   # list header text
    (236, 150, 236),   # header frame, light
    (120, 30, 140),    # header frame, dark
    (176, 70, 190),    # header frame, pressed
    (36, 12, 66),      # header dead area
    (60, 20, 100),     # scrollbar
    (236, 140, 232),   # scrollbar 2
    (90, 36, 130),     # scrollbar pressed
    (110, 236, 255),   # scrollbar pressed 2
    (30, 10, 56),      # scrollbar dead area
]


def make_genex():
    a = new(256, 64, (36, 12, 66))
    for i, c in enumerate(GENEX_COLOURS):
        px(a, 48 + 2 * i, 0, c)
    button(a, 0, 1, 47, 15, "pink", False)
    button(a, 0, 16, 47, 15, "pink", True)
    return a


# ------------------------------------------------------------------------------------------
# Text files
# ------------------------------------------------------------------------------------------

VISCOLOR = (
    [(DISP, "background"), ((54, 24, 90), "dots")]
    + [(ramp([SUN_YEL, (255, 160, 150), PINK, PURPLE, (90, 150, 255), CYAN], i / 15),
        f"spectrum {i + 1} (top)" if i == 0 else f"spectrum {i + 1}") for i in range(16)]
    + [((255, 220, 250), "oscilloscope 1"), ((255, 150, 226), "oscilloscope 2"), (PINK, "oscilloscope 3"),
       (PURPLE, "oscilloscope 4"), (CYAN, "oscilloscope 5"), ((255, 255, 255), "peaks")]
)

PLEDIT = dict(Normal="#FFA6E8", Current="#70F2FF", NormalBG="#160630", SelectedBG="#4E2484",
              MbBG="#160630", MbFG="#FFA6E8", Font="Arial")


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def write_text_files(name):
    with open(os.path.join(OUT, "viscolor.txt"), "w", newline="\r\n") as f:
        for (r, g, b), note in VISCOLOR:
            f.write(f"{r},{g},{b}, // {note}\n")
    with open(os.path.join(OUT, "pledit.txt"), "w", newline="\r\n") as f:
        f.write("[Text]\n" + "".join(f"{k}={v}\n" for k, v in PLEDIT.items()))
    with open(os.path.join(OUT, "readme.txt"), "w", newline="\r\n") as f:
        f.write(
            f"{name.replace('-', ' ')} - a skin in the vaporwave aesthetic, drawn from scratch.\n"
            "\n"
            "A classic (Winamp 2.x format) skin: a pink-to-purple-to-cyan sunset, a striped\n"
            "retro sun between palm silhouettes, a neon wireframe grid, magenta chrome with\n"
            "hard bevels, dark purple displays with cyan and pink text, and a marble bust in\n"
            "the corner. Every bitmap was drawn by a script (gen_skin.py); nothing was taken\n"
            "from any other skin or product, and it carries no logos or marks.\n\n"
            "License: CC0 1.0 Universal (public domain dedication).\n"
        )


# ------------------------------------------------------------------------------------------
# Build
# ------------------------------------------------------------------------------------------

SHEETS = {}


def build(name, dest):
    main, base = make_main()
    titlebar = make_titlebar(main)
    sheets = {
        "main.bmp": main,
        "titlebar.bmp": titlebar,
        "cbuttons.bmp": make_cbuttons(main),
        "shufrep.bmp": make_shufrep(),
        "posbar.bmp": make_posbar(main),
        "volume.bmp": make_volume(base),
        "balance.bmp": make_balance(base),
        "monoster.bmp": make_monoster(main),
        "playpaus.bmp": make_playpaus(),
        "numbers.bmp": make_numbers(False),
        "nums_ex.bmp": make_numbers(True),
        "text.bmp": make_text(),
        "pledit.bmp": make_pledit(),
        "eqmain.bmp": make_eqmain(),
        "gen.bmp": make_gen(),
        "genex.bmp": make_genex(),
    }
    # main.bmp also shows the toggles off where shufrep draws them
    sr = sheets["shufrep.bmp"]
    main[89:104, 164:211] = sr[0:15, 28:75]
    main[89:104, 210:238] = sr[0:15, 0:28]
    main[58:70, 219:242] = sr[61:73, 0:23]
    main[58:70, 242:265] = sr[61:73, 23:46]
    for n, arr in sheets.items():
        SHEETS[n[:-4]] = save(arr, n)
    write_text_files(name)
    names = list(sheets) + ["pledit.txt", "viscolor.txt", "readme.txt"]
    wsz = os.path.join(dest, f"{name}.wsz")
    with zipfile.ZipFile(wsz, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(OUT, n), "rb") as f:
                z.writestr(info, f.read())
    # genex.bmp completed for real Winamp and WACUP: all 24 colours, readable text, and the
    # standard 112x59 button and scrollbar layout (skins/genex_wacup.py).
    genex_wacup.process(wsz)
    return names, wsz
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
for _k, _v in {"<": "[", ">": "]", "{": "[", "}": "]"}.items():
    FONT_LOOKUP[_k] = FONT_LOOKUP[_v]


def draw_bitmap_text(dst, s, x, y):
    text = SHEETS["text"]
    for ch in s:
        row, col = FONT_LOOKUP.get(ch.lower(), FONT_LOOKUP[" "])
        blit(dst, text, (col * 5, row * 6, 5, 6), x, y)
        x += 5


def viscolors():
    return [c for c, _ in VISCOLOR]


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
    for x in range(0, 154, 5):
        w = min(5, 154 - x)
        blit(img, S["text"], (150, 0, w, 6), 111 + x, 24)
    draw_bitmap_text(img, state["title"][:30], 111, 24)
    draw_bitmap_text(img, "192", 111, 43)
    draw_bitmap_text(img, "44", 156, 43)
    cols = viscolors()
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
    lx, lw = 12, w - 32
    d.rectangle((lx, 20, lx + lw - 1, h - 39), fill=hex_rgb(PLEDIT["NormalBG"]))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 9)
    except OSError:
        font = ImageFont.load_default()
    for i, (txt, dur) in enumerate(rows):
        y = 23 + i * 15
        if y + 15 > h - 38:
            break
        if i == 2:
            d.rectangle((lx, y, lx + lw - 1, y + 14), fill=hex_rgb(PLEDIT["SelectedBG"]))
        col = hex_rgb(PLEDIT["Current"]) if i == 1 else hex_rgb(PLEDIT["Normal"])
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
    # a stand-in picture: a small sunset over the grid
    pw, ph = w - 22, h - 34
    hz = int(ph * 0.62)
    pic = sunset(pw, ph, 0, hz)
    retro_sun(pic, pw * 0.5, hz, ph * 0.38, gaps=[(hz - 9, 1), (hz - 6, 2), (hz - 3, 2)])
    grid(pic, hz, pw / 2, step=14)
    img.paste(Image.fromarray(np.clip(pic, 0, 255).astype(np.uint8)), (11, 20))
    return img


def preview(dest):
    rows = [("Neon Plaza - Palm Mall", "4:12"), ("Pastel Shoppe - Neon Lobby", "3:47"),
            ("Marble Hall - Fountain", "5:03"), ("Teal Dolphin - Lagoon", "2:58"),
            ("Chrome Sunset - Drive", "6:21"), ("Pastel Arcade - Token", "3:33"),
            ("Mall Atrium - Escalator", "4:40"), ("Grid Horizon - Dusk", "3:09"),
            ("Plaza Fountain - Coins", "5:51"), ("Late Night TV - Static", "4:05"),
            ("Pink Skyline - Elevator", "3:22")]
    bars = [12, 15, 14, 11, 13, 10, 9, 11, 8, 7, 9, 6, 5, 6, 4, 3, 4, 2, 3]
    A = dict(pressed=None, eq=True, pl=True, clutter="AV", shuffle=True, repeat=False, playing=True, stereo=True,
             pos=0.38, seek=False, volume=72, vdrag=False, balance=0, time=207, remaining=False,
             title="PASTEL SHOPPE - NEON LOBBY (1995)", bars=bars)
    B = dict(pressed="play", eq=False, pl=True, clutter="", shuffle=False, repeat=True, playing=False, stereo=False,
             pos=0.8, seek=True, volume=25, vdrag=True, balance=-60, time=95, remaining=True,
             title="PAUSED: MARBLE HALL (LIVE)", bars=[3, 2, 4, 1, 2, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
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
    out = Image.new("RGB", (275 * 2 + gap * 3, cols[0].height + gap * 2), (40, 24, 60))
    out.paste(cols[0], (gap, gap))
    out.paste(cols[1], (275 + 2 * gap, gap))
    out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
    out.save(os.path.join(dest, "preview.png"))


def main(argv=None):
    global OUT, TITLE
    ap = argparse.ArgumentParser(description="Build the Vaporwave Winamp 2.x skin.")
    ap.add_argument("--title", default=DEFAULT_TITLE, help="the main titlebar's text (default: %(default)s)")
    ap.add_argument("--name", default=DEFAULT_NAME, help="the .wsz's base name (default: %(default)s)")
    ap.add_argument("--out", default=HERE, help="folder for the .wsz and preview.png (default: this folder)")
    ap.add_argument("--list", action="store_true", help="print the theme and exit without building")
    args = ap.parse_args(argv)
    if args.list:
        print(f"{args.name}  (title: {fold_title(args.title)})")  # the one theme
        return
    TITLE = args.title
    dest = os.path.abspath(args.out)
    OUT = os.path.join(dest, "out")
    os.makedirs(OUT, exist_ok=True)
    names, wsz = build(args.name, dest)
    preview(dest)
    for n in names:
        p = os.path.join(OUT, n)
        if n.endswith(".bmp"):
            im = Image.open(p)
            print(f"{n:14s} {im.size[0]}x{im.size[1]} {im.mode}")
        else:
            print(f"{n:14s} {os.path.getsize(p)} bytes")
    print(wsz)


if __name__ == "__main__":
    main()
