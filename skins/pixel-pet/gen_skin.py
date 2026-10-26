#!/usr/bin/python3
"""Pixel Pet: a classic Winamp 2.x skin in the style of the late-90s egg-shaped LCD virtual-pet
keychain toys, drawn procedurally.

A glossy candy-pink plastic shell with lemon-yellow round buttons and a silver ball chain along
the titlebars; the displays are the toy's greenish-grey reflective LCD (dark pixels, faint ghost
segments), with the eight care icons along the top and an original pixel creature (a round
little thing wearing headphones) beside the bitrate readout. The seek bar's thumb is the
creature walking along the LCD; the volume slider is a row of hearts.

Everything is drawn here from code (rectangles, pixel masks, hand-made pixel fonts and pixel
art). Writes the bitmaps and text files into out/, zips them flat into YTMinamp-Pixel-Pet.wsz,
and draws preview.png (the windows assembled from the sprites at their real positions, 2x).
Started from skins/ember/gen_skin.py's layouts.

    /usr/bin/python3 -I gen_skin.py                    build
    /usr/bin/python3 -I gen_skin.py --list             print the theme, build nothing
    --title TEXT    the main titlebar's lettering (default "YTMinamp")
    --name NAME     the .wsz's base name (default YTMinamp-Pixel-Pet); readme.txt's title follows
    --out DIR       where the .wsz and preview.png go (default: beside this script); sheets in DIR/out/
    --readme FILE   a plain-ASCII readme.txt to ship instead of the generated one
"""

import argparse
import os
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # skins/genex_wacup.py, which finishes each .wsz
import genex_wacup  # noqa: E402

THEME = "pixel-pet"
SKIN = "YTMinamp-Pixel-Pet"
TITLE = "YTMinamp"
OUT = os.path.join(HERE, "out")

# ------------------------------------------------------------------------------------------
# Palette
# ------------------------------------------------------------------------------------------

SHELL = (243, 138, 180)        # candy-pink plastic
SHELL_HI = (255, 206, 226)     # gloss
SHELL_MID = (250, 170, 202)
SHELL_LO = (206, 92, 140)      # shaded edges
SHELL_DK = (132, 38, 84)       # outline
PLUM = (112, 26, 70)           # print on the shell
PLUM_DIM = (160, 84, 122)
CREAM = (255, 250, 240)
PINK_PALE = (255, 222, 234)

LCD = (154, 168, 138)          # #9AA88A, the reflective LCD
LCD_INK = (42, 48, 32)         # #2A3020, lit pixels
LCD_GHOST = (137, 151, 121)    # unlit segments and icons, faint
LCD_SHADE = (126, 140, 110)    # the LCD's inner shadow under the bezel
LCD_MID = (88, 100, 72)        # secondary print on the LCD
LCD_DIM = (110, 122, 94)       # unfocused title text

LEMON = (255, 220, 92)         # the round buttons
LEMON_HI = (255, 250, 214)
LEMON_MID = (252, 204, 70)
LEMON_LO = (222, 160, 40)
LEMON_DK = (150, 92, 24)
LEMON_PRESS = (236, 182, 52)

SILVER = (206, 208, 220)
SILVER_HI = (252, 252, 255)
SILVER_LO = (128, 128, 146)
SILVER_DK = (88, 86, 104)
CHAIN_DIM = (214, 168, 190)    # the chain, unfocused
CHAIN_DIM_LO = (186, 120, 152)

SEP = (255, 0, 255)            # gen.bmp letter separators (never shown)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ramp(stops, t):
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    i = min(n - 1, int(t * n))
    return lerp(stops[i], stops[i + 1], t * n - i)


# ------------------------------------------------------------------------------------------
# Canvas helpers (numpy, H x W x 3, int)
# ------------------------------------------------------------------------------------------


def new(w, h, col=SHELL):
    a = np.zeros((h, w, 3), dtype=np.int32)
    a[:, :] = col
    return a


def rect(a, x, y, w, h, col):
    if w > 0 and h > 0:
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(a.shape[1], x + w), min(a.shape[0], y + h)
        if x1 > x0 and y1 > y0:
            a[y0:y1, x0:x1] = col


def px(a, x, y, col):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        a[y, x] = col


def sprite(a, rows, x, y, col, key="#"):
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch in key:
                px(a, x + c, y + r, col(ch) if callable(col) else col)


def save(a, name):
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
    img.save(os.path.join(OUT, name))
    return img


# ------------------------------------------------------------------------------------------
# Pixel fonts (all designed for this skin)
# ------------------------------------------------------------------------------------------

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
    "M": G("#...#", "##.##", "#.#.#", "#...#", "#...#"),
    "N": G("#..#", "##.#", "#.##", "#..#", "#..#"),
    "O": G(".##.", "#..#", "#..#", "#..#", ".##."),
    "P": G("###.", "#..#", "###.", "#...", "#..."),
    "Q": G(".##.", "#..#", "#..#", "#.#.", ".#.#"),
    "R": G("###.", "#..#", "###.", "#.#.", "#..#"),
    "S": G(".###", "#...", ".##.", "...#", "###."),
    "T": G("###", ".#.", ".#.", ".#.", ".#."),
    "U": G("#..#", "#..#", "#..#", "#..#", ".##."),
    "V": G("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": G("#...#", "#...#", "#.#.#", "##.##", "#...#"),
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

# Chunky lettering for the main titlebar: 2px stems, capitals 8 rows high, lowercase on a 6-row
# x-height (rows 2-7) with descenders to row 9. Drawn cream with a plum outline, like the
# bubbly print on a toy's shell. Lowercase letters not drawn here fall back to capitals.
CHUNKY = {
    "A": G(".####.", "##..##", "##..##", "##..##", "######", "##..##", "##..##", "##..##"),
    "B": G("#####.", "##..##", "##..##", "#####.", "##..##", "##..##", "##..##", "#####."),
    "C": G(".####.", "##..##", "##....", "##....", "##....", "##....", "##..##", ".####."),
    "D": G("#####.", "##..##", "##..##", "##..##", "##..##", "##..##", "##..##", "#####."),
    "E": G("#####", "##...", "##...", "####.", "##...", "##...", "##...", "#####"),
    "F": G("#####", "##...", "##...", "####.", "##...", "##...", "##...", "##..."),
    "G": G(".####.", "##..##", "##....", "##....", "##.###", "##..##", "##..##", ".#####"),
    "H": G("##..##", "##..##", "##..##", "######", "##..##", "##..##", "##..##", "##..##"),
    "I": G("####", ".##.", ".##.", ".##.", ".##.", ".##.", ".##.", "####"),
    "J": G("...##", "...##", "...##", "...##", "...##", "##.##", "##.##", ".###."),
    "K": G("##..##", "##.##.", "####..", "###...", "####..", "##.##.", "##..##", "##..##"),
    "L": G("##...", "##...", "##...", "##...", "##...", "##...", "##...", "#####"),
    "M": G("##...##", "###.###", "#######", "##.#.##", "##...##", "##...##", "##...##", "##...##"),
    "N": G("##..##", "###.##", "######", "##.###", "##..##", "##..##", "##..##", "##..##"),
    "O": G(".####.", "##..##", "##..##", "##..##", "##..##", "##..##", "##..##", ".####."),
    "P": G("#####.", "##..##", "##..##", "##..##", "#####.", "##....", "##....", "##...."),
    "Q": G(".####.", "##..##", "##..##", "##..##", "##..##", "##.###", "##..##", ".###.#"),
    "R": G("#####.", "##..##", "##..##", "##..##", "#####.", "##.##.", "##..##", "##..##"),
    "S": G(".####.", "##..##", "##....", ".####.", "....##", "....##", "##..##", ".####."),
    "T": G("######", "..##..", "..##..", "..##..", "..##..", "..##..", "..##..", "..##.."),
    "U": G("##..##", "##..##", "##..##", "##..##", "##..##", "##..##", "##..##", ".####."),
    "V": G("##..##", "##..##", "##..##", "##..##", "##..##", "##..##", ".####.", "..##.."),
    "W": G("##...##", "##...##", "##...##", "##...##", "##.#.##", "#######", "###.###", "##...##"),
    "X": G("##..##", "##..##", ".####.", "..##..", ".####.", "##..##", "##..##", "##..##"),
    "Y": G("##..##", "##..##", "##..##", ".####.", "..##..", "..##..", "..##..", "..##.."),
    "Z": G("######", "....##", "...##.", "..##..", ".##...", "##....", "##....", "######"),
    "0": G(".####.", "##..##", "##.###", "######", "###.##", "##..##", "##..##", ".####."),
    "1": G("..##.", ".###.", "####.", "..##.", "..##.", "..##.", "..##.", "#####"),
    "2": G(".####.", "##..##", "....##", "...##.", "..##..", ".##...", "##....", "######"),
    "3": G(".####.", "##..##", "....##", "..###.", "....##", "....##", "##..##", ".####."),
    "4": G("...##.", "..###.", ".####.", "##.##.", "######", "...##.", "...##.", "...##."),
    "5": G("######", "##....", "##....", "#####.", "....##", "....##", "##..##", ".####."),
    "6": G(".####.", "##....", "##....", "#####.", "##..##", "##..##", "##..##", ".####."),
    "7": G("######", "....##", "...##.", "...##.", "..##..", "..##..", "..##..", "..##.."),
    "8": G(".####.", "##..##", "##..##", ".####.", "##..##", "##..##", "##..##", ".####."),
    "9": G(".####.", "##..##", "##..##", "##..##", ".#####", "....##", "....##", ".####."),
    "-": G("....", "....", "....", "####", "....", "....", "....", "...."),
    ".": G("..", "..", "..", "..", "..", "..", "##", "##"),
    "!": G("##", "##", "##", "##", "##", "..", "##", "##"),
    "'": G("##", "##", "#.", "..", "..", "..", "..", ".."),
    "&": G(".###..", "##.##.", "##.##.", ".###..", "##.###", "##.##.", "##.##.", ".##.##"),
    " ": G("...", "...", "...", "...", "...", "...", "...", "..."),
    "i": G("##", "..", "##", "##", "##", "##", "##", "##"),
    "n": G("......", "......", "#####.", "##..##", "##..##", "##..##", "##..##", "##..##"),
    "a": G("......", "......", ".####.", "....##", ".#####", "##..##", "##..##", ".#####"),
    "m": G(".......", ".......", "######.", "##.#.##", "##.#.##", "##.#.##", "##.#.##", "##.#.##"),
    "p": G("......", "......", "#####.", "##..##", "##..##", "##..##", "##..##", "#####.", "##....",
           "##...."),
    "e": G("......", "......", ".####.", "##..##", "######", "##....", "##..##", ".####."),
    "o": G("......", "......", ".####.", "##..##", "##..##", "##..##", "##..##", ".####."),
    "t": G(".##..", ".##..", "#####", ".##..", ".##..", ".##..", ".##..", "..###"),
    "s": G("......", "......", ".#####", "##....", ".####.", "....##", "....##", "#####."),
    "r": G(".....", ".....", "##.##", "####.", "##...", "##...", "##...", "##..."),
    "l": G("##", "##", "##", "##", "##", "##", "##", "##"),
    "u": G("......", "......", "##..##", "##..##", "##..##", "##..##", "##..##", ".#####"),
}


def chunky_glyph(c):
    if c in CHUNKY:
        return CHUNKY[c]
    if c.upper() in CHUNKY:
        return CHUNKY[c.upper()]
    return None


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
        if shadow is not None:
            sprite(a, g, x + 1, y + 1, shadow)
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    px(a, x + k, y + r, col(r) if callable(col) else col)
        x += len(g[0]) + gap
    return x


def text_center(a, font, s, cx, y, col, gap=1, shadow=None):
    draw_text(a, font, s, cx - text_w(font, s, gap) // 2, y, col, gap, shadow)


def chunky_mask(s, gap=1):
    """The lettering as a boolean mask, 10 rows (capitals 0-7, descenders 8-9)."""
    glyphs = [chunky_glyph(c) for c in s]
    glyphs = [g for g in glyphs if g is not None]
    w = sum(len(g[0]) for g in glyphs) + gap * max(0, len(glyphs) - 1)
    m = np.zeros((10, max(1, w)), dtype=bool)
    x = 0
    for g in glyphs:
        for r, row in enumerate(g):
            for k, ch in enumerate(row):
                if ch == "#":
                    m[r, x + k] = True
        x += len(g[0]) + gap
    return m


def dilate(m):
    h, w = m.shape
    p = np.zeros((h + 2, w + 2), dtype=bool)
    p[1:-1, 1:-1] = m
    out = np.zeros_like(p)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out |= np.roll(np.roll(p, dy, 0), dx, 1)
    return out


def draw_chunky(a, s, x, y, lit, max_w=None):
    """Bubble lettering at (x, y) (the outline starts at x-1, y-1); returns its width."""
    m = chunky_mask(s)
    if max_w is not None and m.shape[1] > max_w:
        m = m[:, :max_w]
    ring = dilate(m)
    shadow = np.zeros_like(ring)
    shadow[1:, :] = ring[:-1, :]
    fill_top, fill_bot = (CREAM, PINK_PALE) if lit else ((248, 226, 236), (236, 204, 218))
    line = PLUM if lit else PLUM_DIM
    sh = SHELL_LO if lit else lerp(SHELL_LO, SHELL, 0.5)
    H, W = ring.shape
    for r in range(H):
        for c in range(W):
            X, Y = x - 1 + c, y - 1 + r
            if shadow[r, c] and not ring[r, c]:
                px(a, X, Y, sh)
    for r in range(H):
        for c in range(W):
            X, Y = x - 1 + c, y - 1 + r
            if ring[r, c]:
                mr, mc = r - 1, c - 1
                inside = 0 <= mr < m.shape[0] and 0 <= mc < m.shape[1] and m[mr, mc]
                if inside:
                    px(a, X, Y, lerp(fill_top, fill_bot, min(1.0, max(0.0, (mr - 3) / 4))))
                else:
                    px(a, X, Y, line)
    return m.shape[1]


# ------------------------------------------------------------------------------------------
# Pixel art: the pet, its icons, the egg
# ------------------------------------------------------------------------------------------

# The pet: a round little creature wearing headphones (an original design). 17x15.
PET_IDLE = G(
    ".....#######.....",
    "...##.......##...",
    "..#...........#..",
    ".#....#####....#.",
    ".#..##.....##..#.",
    "##.#.........#.##",
    "####.........####",
    "####..#...#..####",
    "####..#...#..####",
    "####.........####",
    ".#.#..#...#..#.#.",
    "....#..###..#....",
    ".....##...##.....",
    "......#####......",
    ".....##...##.....",
)
# eyes shut, singing
PET_SING = G(
    ".....#######.....",
    "...##.......##...",
    "..#...........#..",
    ".#....#####....#.",
    ".#..##.....##..#.",
    "##.#.........#.##",
    "####.........####",
    "####.##...##.####",
    "####.........####",
    "####...###...####",
    ".#.#...###...#.#.",
    "....#...#...#....",
    ".....##...##.....",
    "......#####......",
    "....##.....##....",
)
# The pet, small, for the seek bar's thumb. 9x8.
MINI_PET = G(
    "..#####..",
    ".#.....#.",
    "##.#.#.##",
    "##.....##",
    "##.###.##",
    ".#.....#.",
    "..#####..",
    "..#...#..",
)
MINI_PET_HOP = G(
    "..#####..",
    ".#.....#.",
    "##.....##",
    "##.#.#.##",
    "##.....##",
    ".#.###.#.",
    "..#####..",
    ".#.....#.",
)
NOTE_8TH = G("..##", "..#.", "..#.", "###.", "##..")
NOTE_16TH = G(".###", ".#.#", ".#..", "##..", "#...")

# The LCD's care icons, 7x6 each: top row food, light, play, medicine; then bath, meter,
# discipline, call.
ICONS = {
    "food": G("#.#..#.", "#.#.##.", "###.##.", ".#..##.", ".#...#.", ".#...#."),
    "light": G("..###..", ".#...#.", ".#...#.", "..#.#..", "..###..", "..###.."),
    "play": G("..###..", ".#####.", "##..###", "###..##", ".#####.", "..###.."),
    "medicine": G("...##..", "..#..#.", ".#.#.#.", "#.#.#..", "#..#...", ".##...."),
    "bath": G(".##....", "#.##...", ".##....", ".#....#", ".######", "..####."),
    "meter": G(".##.##.", "#######", "#######", ".#####.", "..###..", "...#..."),
    "discipline": G(".#####.", "#..#..#", "#..#..#", "#.....#", "#..#..#", ".#####."),
    "call": G("...#...", "..###..", ".#####.", ".#####.", "#######", "...#..."),
}
ICON_ORDER = ["food", "light", "play", "medicine", "bath", "meter", "discipline", "call"]
ICON_LIT = {"play", "meter"}

HEART = G(".##.##.", "#######", "#######", ".#####.", "..###..", "...#...")
HEART_OUT = G(".##.##.", "#..#..#", "#.....#", ".#...#.", "..#.#..", "...#...")

# The emblem (the About spot): an egg about to hatch. 13x15.
EGG = G(
    ".....###.....",
    "....#ooo#....",
    "...#ooooo#...",
    "..#ooooooo#..",
    "..#ooooooo#..",
    ".#ooooooooo#.",
    ".#ooooooooo#.",
    "#ooooooooooo#",
    "#ooooooooooo#",
    "#ooooooooooo#",
    "#ooooooooooo#",
    "#ooooooooooo#",
    ".#ooooooooo#.",
    "..##ooooo##..",
    "....#####....",
)
EGG_CRACK = [(c, 7 + (0, 1, 2, 1)[(c - 1) % 4]) for c in range(1, 12)]
EGG_SPOTS = [(5, 4), (9, 11), (3, 11)]


# ------------------------------------------------------------------------------------------
# Shared pieces: bezels, LCD windows, buttons, the ball chain
# ------------------------------------------------------------------------------------------


def bevel_out(a, x, y, w, h, hi=SHELL_HI, lo=SHELL_LO):
    rect(a, x, y, w, 1, hi)
    rect(a, x, y, 1, h, hi)
    rect(a, x, y + h - 1, w, 1, lo)
    rect(a, x + w - 1, y, 1, h, lo)


def lcd_window(a, x, y, w, h, col=LCD, shade=True):
    """An LCD window with interior (x, y, w, h): a recessed bezel ring around it (dark plastic
    top and left, gloss bottom and right, corners rounded), the inner shadow along the top."""
    rect(a, x - 1, y - 1, w + 2, 1, SHELL_DK)
    rect(a, x - 1, y - 1, 1, h + 2, SHELL_DK)
    rect(a, x - 1, y + h, w + 2, 1, SHELL_HI)
    rect(a, x + w, y - 1, 1, h + 2, SHELL_HI)
    px(a, x - 1, y - 1, SHELL_LO)
    px(a, x + w, y + h, SHELL_MID)
    px(a, x + w, y - 1, SHELL_LO)
    px(a, x - 1, y + h, SHELL_LO)
    rect(a, x, y, w, h, col)
    if shade:
        rect(a, x, y, w, 1, LCD_SHADE)
        rect(a, x, y, 1, h, lerp(LCD_SHADE, col, 0.5))


def circle_mask(w, h, cx, cy, r):
    yy, xx = np.mgrid[0:h, 0:w]
    return (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2 <= r * r


def candy_button(a, x, y, w, h, pressed=False, r=None, lit=True, bg=None):
    """A round lemon button filling (x, y, w, h) (an ellipse if w != h): plum outline, gloss at
    the top left, shade at the bottom. bg: callable (col, row) -> colour for the corners."""
    if r is None:
        r = min(w, h) / 2
    yy, xx = np.mgrid[0:h, 0:w]
    sx, sy = (w / 2) / r, (h / 2) / r
    d = np.sqrt(((xx + 0.5 - w / 2) / sx) ** 2 + ((yy + 0.5 - h / 2) / sy) ** 2)
    inside = d <= r
    outline = inside & (d > r - 1.0)
    if lit:
        top, bot, line = (LEMON_HI, LEMON_LO, LEMON_DK)
        if pressed:
            top, bot = (LEMON_MID, LEMON_PRESS)
    else:
        top, bot, line = ((246, 240, 226), (210, 196, 180), (150, 130, 128))
    for j in range(h):
        for i in range(w):
            if not inside[j, i]:
                if bg is not None:
                    px(a, x + i, y + j, bg(i, j))
                continue
            if outline[j, i]:
                col = line
            else:
                t = (j + 0.5) / h
                col = lerp(top, bot, max(0.0, min(1.0, (t - 0.15) / 0.8)))
                if not pressed:
                    # gloss: a soft spot at the upper left
                    gx, gy = (i + 0.5 - w * 0.36) / (w * 0.22), (j + 0.5 - h * 0.30) / (h * 0.18)
                    if gx * gx + gy * gy < 1.0:
                        col = lerp(col, (255, 255, 255), 0.75)
                    elif d[j, i] > r - 2.0 and j > h * 0.55:
                        col = lerp(col, LEMON_LO, 0.6)
            px(a, x + i, y + j, col)
    return inside


def mini_button(a, x, y, kind, lit=True, pressed=False):
    """9x9 titlebar button: a small lemon candy button with a plum glyph."""
    bg = a[y:y + 9, x:x + 9].copy()
    candy_button(a, x, y, 9, 9, pressed=pressed, lit=lit, bg=lambda i, j: tuple(bg[j, i]))
    ink = PLUM if lit else PLUM_DIM
    o = 1 if pressed else 0
    X, Y = x + o, y + o
    if kind == "options":
        rect(a, X + 3, Y + 3, 3, 3, ink)
        for dx, dy in [(3, 3), (5, 3), (3, 5), (5, 5)]:
            px(a, X + dx, Y + dy, lerp(ink, LEMON, 0.5))
    elif kind == "minimize":
        rect(a, X + 2, Y + 5, 5, 1, ink)
    elif kind == "shade":
        rect(a, X + 2, Y + 3, 5, 1, ink)
        rect(a, X + 2, Y + 5, 5, 1, lerp(ink, LEMON, 0.45))
    elif kind == "close":
        for i in range(5):
            px(a, X + 2 + i, Y + 2 + i, ink)
            px(a, X + 6 - i, Y + 2 + i, ink)


def chain(a, x0, x1, cy, lit, phase=0):
    """A ball chain from x0 to x1 (exclusive), centred on row cy: 3px balls every 5px joined by a
    1px link. The period divides 25, so it runs on seamlessly across the 25px frame tiles."""
    hi, mid, lo, dk = (SILVER_HI, SILVER, SILVER_LO, SILVER_DK) if lit else \
        (lerp(CHAIN_DIM, CREAM, 0.5), CHAIN_DIM, CHAIN_DIM_LO, CHAIN_DIM_LO)
    for x in range(x0, x1):
        k = (x - phase) % 5
        if k == 0:
            px(a, x, cy - 1, mid)
            px(a, x, cy, mid)
            px(a, x, cy + 1, lo)
        elif k == 1:
            px(a, x, cy - 1, hi)
            px(a, x, cy, mid)
            px(a, x, cy + 1, lo)
            px(a, x, cy + 2, lerp(SHELL_LO, SHELL, 0.4))
        elif k == 2:
            px(a, x, cy - 1, mid)
            px(a, x, cy, lo)
            px(a, x, cy + 1, dk)
            px(a, x, cy + 2, lerp(SHELL_LO, SHELL, 0.4))
        else:
            px(a, x, cy, lo if lit else CHAIN_DIM)


def key_ring(a, x, y, lit):
    """A small split ring (7x9) the chain hangs from."""
    hi, mid, lo = (SILVER_HI, SILVER, SILVER_DK) if lit else (CREAM, CHAIN_DIM, CHAIN_DIM_LO)
    ring = G("..###..", ".#...#.", "#.....#", "#.....#", "#.....#", "#.....#", "#.....#", ".#...#.",
             "..###..")
    for r, row in enumerate(ring):
        for c, ch in enumerate(row):
            if ch == "#":
                col = hi if (r < 3 or c < 2) else (lo if (r > 5 or c > 4) else mid)
                px(a, x + c, y + r, col)


def clasp(a, x, y, lit):
    """The chain's clasp: a 6x4 barrel."""
    hi, mid, lo = (SILVER_HI, SILVER, SILVER_DK) if lit else (CREAM, CHAIN_DIM, CHAIN_DIM_LO)
    rect(a, x, y, 6, 1, hi)
    rect(a, x, y + 1, 6, 1, mid)
    rect(a, x, y + 2, 6, 1, lerp(mid, lo, 0.5))
    rect(a, x, y + 3, 6, 1, lo)
    px(a, x + 2, y, mid)
    px(a, x + 2, y + 3, SILVER_DK if lit else CHAIN_DIM_LO)


def bar_shading(a, x, y, w, h, top_line=True):
    """The plastic of a window's top bar: an outline row, two gloss rows, then plain shell."""
    rect(a, x, y, w, h, SHELL)
    if top_line:
        rect(a, x, y, w, 1, SHELL_DK)
        rect(a, x, y + 1, w, 1, SHELL_HI)
        rect(a, x, y + 2, w, 1, SHELL_MID)
    else:
        rect(a, x, y, w, 1, SHELL_HI)
        rect(a, x, y + 1, w, 1, SHELL_MID)


def left_edge(a, x, y, h):
    rect(a, x, y, 1, h, SHELL_DK)
    rect(a, x + 1, y, 1, h, SHELL_HI)


def right_edge(a, x, y, h):
    rect(a, x, y, 1, h, SHELL_LO)
    rect(a, x + 1, y, 1, h, SHELL_DK)


def plate(a, x, y, w, lit, h=9):
    """An LCD nameplate (rows y..y+h-1): bezel ring, LCD inside."""
    lcd_window(a, x + 1, y + 1, w - 2, h - 2, LCD if lit else lerp(LCD, SHELL_MID, 0.25), shade=False)


TITLE_LIT = LCD_INK
TITLE_DIM = LCD_DIM


# ------------------------------------------------------------------------------------------
# titlebar.bmp (344 x 87)
# ------------------------------------------------------------------------------------------

CLUTTER_SLOTS = [("O", 3, 8), ("A", 11, 7), ("I", 18, 7), ("D", 25, 8), ("V", 33, 7)]


def clutter_bar(lit_letters):
    a = new(8, 43, SHELL)
    rect(a, 0, 0, 8, 43, SHELL_LO)
    rect(a, 0, 0, 8, 1, SHELL_DK)
    rect(a, 0, 0, 1, 43, SHELL_DK)
    rect(a, 7, 0, 1, 43, SHELL_HI)
    rect(a, 0, 42, 8, 1, SHELL_HI)
    for letter, y, h in CLUTTER_SLOTS:
        on = letter in lit_letters
        if on:
            rect(a, 1, y, 6, h, LEMON)
            rect(a, 1, y, 6, 1, LEMON_HI)
            rect(a, 1, y + h - 1, 6, 1, LEMON_LO)
        gy = y + (h - 5) // 2
        draw_text(a, TINY, letter, 2, gy, PLUM if on else PINK_PALE)
    return a


def main_titlebar(lit, title):
    a = new(275, 14, SHELL)
    bar_shading(a, 0, 0, 275, 14)
    left_edge(a, 0, 0, 14)
    right_edge(a, 273, 0, 14)
    m = chunky_mask(title)
    ww = min(m.shape[1], 200)
    wx = (275 - ww) // 2
    # ring + chain left of the lettering, chain + clasp to its right, clear of the buttons
    key_ring(a, wx - 12, 3, lit)
    chain(a, 18, wx - 12, 7, lit, phase=3)
    chain(a, wx + ww + 4, 233, 7, lit, phase=wx + ww + 4)
    clasp(a, 233, 6, lit)
    draw_chunky(a, title, wx, 2, lit, max_w=200)
    mini_button(a, 6, 3, "options", lit)
    mini_button(a, 244, 3, "minimize", lit)
    mini_button(a, 254, 3, "shade", lit)
    mini_button(a, 264, 3, "close", lit)
    return a


def make_titlebar(title):
    a = new(344, 87, SHELL)
    for kind, x, y, py_ in [("options", 0, 0, 9), ("minimize", 9, 0, 9), ("close", 18, 0, 9)]:
        b = new(9, 9)
        mini_button(b, 0, 0, kind, True)
        a[y:y + 9, x:x + 9] = b
        b = new(9, 9)
        mini_button(b, 0, 0, kind, True, pressed=True)
        a[py_:py_ + 9, x:x + 9] = b
    b = new(9, 9)
    mini_button(b, 0, 0, "shade", True)
    a[18:27, 0:9] = b
    b = new(9, 9)
    mini_button(b, 0, 0, "shade", True, pressed=True)
    a[18:27, 9:18] = b
    a[0:14, 27:302] = main_titlebar(True, title)
    a[15:29, 27:302] = main_titlebar(False, title)
    # window-shade bars (not used by every player; copies of the titlebars)
    a[29:43, 27:302] = main_titlebar(True, title)
    a[42:56, 27:302] = main_titlebar(False, title)
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

SEG = {
    # 1px horizontals (rows 0, 6, 12), 2px verticals; numbers.bmp's minus is digit 2's row 6.
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


def seven_seg(a, x, y, lit_segs, ghost=True):
    rect(a, x, y, 9, 13, LCD)
    for s, cells in SEG.items():
        on = s in lit_segs
        if on or ghost:
            for r, c in cells:
                px(a, x + c, y + r, LCD_INK if on else LCD_GHOST)


# The LCD windows on main.bmp (interiors).
LEFT_LCD = (22, 15, 83, 47)     # time, play state, visualizer; icons along its top
RIGHT_LCD = (110, 15, 158, 41)  # title, kbps/kHz, mono/stereo, the pet; icons along its top
SEEK_LCD = (16, 72, 248, 10)    # posbar.bmp draws all ten rows
PET_POS = (188, 38)
ICON_Y = 16


def icon_x(i):
    if i < 4:
        x0, w = LEFT_LCD[0], LEFT_LCD[2]
    else:
        x0, w = RIGHT_LCD[0], RIGHT_LCD[2]
        i -= 4
    return x0 + round(w * (i + 0.5) / 4) - 3


def draw_icons(a):
    for i, name in enumerate(ICON_ORDER):
        sprite(a, ICONS[name], icon_x(i), ICON_Y, LCD_INK if name in ICON_LIT else LCD_GHOST)


def draw_pet(a, x, y):
    sprite(a, PET_IDLE, x, y, LCD_INK)
    sprite(a, NOTE_8TH, x + 18, y - 1, LCD_INK)
    sprite(a, NOTE_16TH, x - 6, y + 2, LCD_GHOST)  # a faded note: LCD ghosting


def emblem(a, x, y):
    for r, row in enumerate(EGG):
        for c, ch in enumerate(row):
            if ch == "#":
                px(a, x + c, y + r, PLUM)
            elif ch == "o":
                # cream, shaded pink towards the lower right
                shade = (c - 6.0) * 0.55 + (r - 7.0) * 0.75 > 4.0
                px(a, x + c, y + r, PINK_PALE if shade else CREAM)
    px(a, x + 4, y + 2, (255, 255, 255))
    px(a, x + 3, y + 3, (255, 255, 255))
    for sx, sy in EGG_SPOTS:
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            px(a, x + sx + dx, y + sy + dy, LEMON_MID if (dx, dy) == (0, 0) else LEMON)
    for c, r in EGG_CRACK:
        px(a, x + c, y + r, PLUM)


def main_bg():
    """The shell, the LCD windows and their print, without the sprites drawn over them."""
    a = new(275, 116, SHELL)
    # outline and gloss of the shell
    rect(a, 0, 115, 275, 1, SHELL_DK)
    rect(a, 1, 114, 273, 1, SHELL_LO)
    left_edge(a, 0, 0, 116)
    right_edge(a, 273, 0, 116)
    px(a, 1, 114, SHELL_LO)
    # LCD windows
    lcd_window(a, *LEFT_LCD)
    lcd_window(a, *RIGHT_LCD)
    draw_icons(a)
    for x in (48, 60, 78, 90):
        seven_seg(a, x, 26, "")
    for yy in (29, 34):
        rect(a, 73, yy, 2, 2, LCD_INK)
    draw_text(a, TINY, "KBPS", 128, 43, LCD_MID)
    draw_text(a, TINY, "KHZ", 168, 43, LCD_MID)
    draw_pet(a, *PET_POS)
    # slider seats and the seek window
    lcd_window(a, 108, 58, 66, 11)
    lcd_window(a, 178, 58, 36, 11)
    lcd_window(a, *SEEK_LCD)
    return a


def make_main(title):
    a = main_bg()
    a[0:14, :] = main_titlebar(True, title)
    a[22:65, 10:18] = clutter_bar("")
    emblem(a, 253, 91)
    return a


# ------------------------------------------------------------------------------------------
# cbuttons.bmp (136 x 36): the round candy buttons
# ------------------------------------------------------------------------------------------


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


def transport_glyph(a, kind, cx, cy, col):
    if kind == "previous":
        rect(a, cx - 4, cy - 2, 1, 5, col)
        tri_left(a, cx - 3, cy - 2, 5, col)
        tri_left(a, cx, cy - 2, 5, col)
    elif kind == "play":
        tri_right(a, cx - 1, cy - 3, 7, col)
    elif kind == "pause":
        rect(a, cx - 2, cy - 3, 2, 7, col)
        rect(a, cx + 1, cy - 3, 2, 7, col)
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


TRANSPORT = [("previous", 0, 23, 18, 16, 88), ("play", 23, 23, 18, 39, 88), ("pause", 46, 23, 18, 62, 88),
             ("stop", 69, 23, 18, 85, 88), ("next", 92, 22, 18, 108, 88)]


def transport_cell(main, kind, w, h, dx, dy, pressed):
    c = main[dy:dy + h, dx:dx + w].copy()
    bw = 18 if h >= 18 else 16
    bx = (w - bw) // 2
    by = (h - bw) // 2
    bg = c.copy()
    # a soft drop shadow on the shell under the button
    for j in range(h):
        for i in range(w):
            d = ((i + 0.5 - w / 2) ** 2 + (j - 0.5 - h / 2) ** 2) ** 0.5
            if d <= bw / 2 and not pressed:
                c[j, i] = lerp(tuple(bg[j, i]), SHELL_LO, 0.55)
    bg2 = c.copy()
    candy_button(c, bx, by, bw, bw, pressed=pressed, bg=lambda i, j: tuple(bg2[by + j, bx + i]))
    o = 1 if pressed else 0
    transport_glyph(c, kind, w // 2 + o, h // 2 + o - (1 if h < 18 else 0) + (0 if bw == 18 else 1), PLUM)
    return c


def make_cbuttons(main):
    a = new(136, 36, SHELL)
    for kind, x, w, h, dx, dy in TRANSPORT:
        a[0:h, x:x + w] = transport_cell(main, kind, w, h, dx, dy, False)
        a[18:18 + h, x:x + w] = transport_cell(main, kind, w, h, dx, dy, True)
    a[0:16, 114:136] = transport_cell(main, "eject", 22, 16, 136, 89, False)
    a[16:32, 114:136] = transport_cell(main, "eject", 22, 16, 136, 89, True)
    return a


# ------------------------------------------------------------------------------------------
# shufrep.bmp (92 x 85): pill buttons with a little LCD indicator
# ------------------------------------------------------------------------------------------


def pill(a, x, y, w, h, pressed, bg):
    """A rounded cream pill with a plum outline (corners left as bg)."""
    for j in range(h):
        for i in range(w):
            # rounded corners, radius ~3
            cx = min(i, w - 1 - i)
            cy = min(j, h - 1 - j)
            corner = cx < 2 and cy < 2 and (cx + cy) < 2
            if corner:
                px(a, x + i, y + j, bg[j, i])
                continue
            edge = cx == 0 or cy == 0 or (cx + cy) == 2 and cx < 2 and cy < 2
            if edge:
                px(a, x + i, y + j, PLUM)
            else:
                t = j / max(1, h - 1)
                if pressed:
                    col = lerp((246, 196, 214), (255, 226, 236), t)
                else:
                    col = lerp((255, 250, 246), (250, 206, 222), t)
                    if j == 1:
                        col = (255, 255, 255)
                px(a, x + i, y + j, col)


def toggle(a, x, y, w, h, label, on, pressed, bg):
    pill(a, x, y, w, h, pressed, bg)
    o = 1 if pressed else 0
    # the indicator: a tiny LCD square, its pixel dark when on
    lx, ly = x + 3 + o, y + (h - 5) // 2 + o
    rect(a, lx, ly, 5, 5, LCD)
    rect(a, lx, ly, 5, 1, LCD_SHADE)
    rect(a, lx + 1, ly + 1, 3, 3, LCD_INK if on else LCD_GHOST)
    tw = text_w(TINY, label)
    tx = x + 9 + (w - 11 - tw) // 2 + o
    ty = y + (h - 5) // 2 + o
    draw_text(a, TINY, label, tx, ty, PLUM)


def make_shufrep(main):
    a = new(92, 85, SHELL)
    rep_bg = main[89:104, 210:238]
    shu_bg = main[89:104, 164:211]
    eq_bg = main[58:70, 219:242]
    pl_bg = main[58:70, 242:265]
    for row, (on, pressed) in enumerate([(False, False), (False, True), (True, False), (True, True)]):
        y = row * 15
        toggle(a, 0, y, 28, 15, "REP", on, pressed, rep_bg)
        toggle(a, 28, y, 47, 15, "SHUFFLE", on, pressed, shu_bg)
    for x, label, pressed, bg in [(0, "EQ", False, eq_bg), (23, "PL", False, pl_bg), (46, "EQ", True, eq_bg),
                                  (69, "PL", True, pl_bg)]:
        toggle(a, x, 61, 23, 12, label, False, pressed, bg)
        toggle(a, x, 73, 23, 12, label, True, pressed, bg)
    return a


# ------------------------------------------------------------------------------------------
# monoster.bmp, playpaus.bmp, numbers.bmp, nums_ex.bmp, text.bmp: LCD segments
# ------------------------------------------------------------------------------------------


def make_monoster():
    a = new(56, 24, LCD)
    for y, on in ((0, True), (12, False)):
        col = LCD_INK if on else LCD_GHOST
        text_center(a, TINY, "STEREO", 14, y + 3, col)
        text_center(a, TINY, "MONO", 29 + 13, y + 3, col)
    return a


def make_playpaus():
    a = new(48, 9, LCD)
    tri_right(a, 2, 1, 7, LCD_INK)                     # playing
    rect(a, 9 + 2, 1, 2, 7, LCD_INK)                   # paused
    rect(a, 9 + 5, 1, 2, 7, LCD_INK)
    rect(a, 18 + 2, 2, 5, 5, LCD_INK)                  # stopped
    rect(a, 36, 0, 3, 9, LCD)                          # not working
    rect(a, 39 + 1, 3, 1, 3, LCD_INK)                  # working: a dot in its 3px slice
    return a


def make_numbers(ex):
    a = new(108 if ex else 99, 13, LCD)
    for n in range(10):
        seven_seg(a, 9 * n, 0, DIGIT_SEGS[n])
    seven_seg(a, 90, 0, "")                            # blank cell: ghost segments
    if ex:
        seven_seg(a, 99, 0, "g", ghost=False)          # minus: the middle segment alone
    return a


FONT_GRID = [
    list("abcdefghijklmnopqrstuvwxyz\"@") + [None, None, " "],
    list("0123456789") + ["…", ".", ":", "(", ")", "-", "'", "!", "_", "+", "\\", "/", "[", "]", "^", "&", "%",
                          ",", "=", "$", "#"],
    ["å", "ö", "ä", "?", "*"] + [None] * 26,
]


def make_text():
    # No ghosting here: the app takes the commonest non-background colour as the title's ink.
    a = new(155, 18, LCD)
    for row, chars in enumerate(FONT_GRID):
        for col, ch in enumerate(chars):
            if ch is None or ch == " ":
                continue
            key = ch if ch in FONT5 else ch.upper()
            g = FONT5[key]
            draw_text(a, FONT5, key, col * 5 + (1 if len(g[0]) <= 3 else 0), row * 6, LCD_INK)
    return a


# ------------------------------------------------------------------------------------------
# posbar.bmp (307 x 10), volume.bmp / balance.bmp (68 x 433)
# ------------------------------------------------------------------------------------------

SEEK_GROUND = 8


def seek_track(w):
    a = new(w, 10, LCD)
    rect(a, 0, 0, w, 1, LCD_SHADE)
    for x in range(w):
        px(a, x, SEEK_GROUND, LCD_MID if x % 2 == 0 else LCD_GHOST)
    return a


def make_posbar():
    a = new(307, 10, LCD)
    a[:, 0:248] = seek_track(248)
    for x0, pose in ((248, MINI_PET), (278, MINI_PET_HOP)):
        t = seek_track(29)
        # keep the ground's dots in step with the track's at even thumb positions
        a[:, x0:x0 + 29] = t
        dy = -1 if pose is MINI_PET_HOP else 0
        sprite(a, pose, x0 + 10, SEEK_GROUND - 8 + dy, LCD_INK)
        if pose is MINI_PET_HOP:
            sprite(a, G("#.", ".#", "#."), x0 + 21, 2, LCD_INK)   # a little motion mark
            sprite(a, G(".#", "#.", ".#"), x0 + 6, 2, LCD_INK)
    return a


def capsule(a, x, y, w, h, pressed, bg):
    """A lemon capsule (stadium) filling (x, y, w, h); bg(i, j) gives the corner colours."""
    r = h / 2
    for j in range(h):
        for i in range(w):
            cxp = min(max(i + 0.5, r), w - r)
            d = ((i + 0.5 - cxp) ** 2 + (j + 0.5 - r) ** 2) ** 0.5
            if d > r:
                px(a, x + i, y + j, bg(i, j))
                continue
            if d > r - 1.0:
                col = LEMON_DK
            else:
                t = (j + 0.5) / h
                top, bot = (LEMON_MID, LEMON_PRESS) if pressed else (LEMON_HI, LEMON_LO)
                col = lerp(top, bot, max(0.0, min(1.0, (t - 0.15) / 0.8)))
                if not pressed and j == 2 and 2 < i < w - 3:
                    col = lerp(col, (255, 255, 255), 0.7)
            px(a, x + i, y + j, col)


def track_seat(w):
    """The volume/balance track: 13 rows; an LCD strip in a bezel ring (rows 1-11)."""
    a = new(w, 13, SHELL)
    lcd_window(a, 1, 2, w - 2, 9)
    return a


def make_volume(main):
    a = new(68, 433, SHELL)
    seat = track_seat(68)
    for i in range(28):
        y = i * 15
        a[y:y + 13, :] = seat
        a[y + 13:y + 15, :] = main[70:72, 107:175]
        level = (i + 1) / 28
        fill_px = 2 + level * 63
        for k in range(7):
            hx = 3 + 9 * k
            for r, row in enumerate(HEART):
                for c, ch in enumerate(row):
                    X = hx + c
                    if ch == "#":
                        full = X < fill_px
                        if full:
                            px(a, X, y + 4 + r, LCD_INK)
                        elif HEART_OUT[r][c] == "#":
                            px(a, X, y + 4 + r, LCD_MID)
                        else:
                            px(a, X, y + 4 + r, LCD_GHOST)
    thumbs(a, seat)
    return a


def thumbs(a, seat):
    # thumbs (14x11 at the track's rows 1..11): corners take the seat's plain colour per row
    plain = [tuple(seat[1 + j, 1]) if 0 < j < 10 else tuple(seat[1 + j, 0]) for j in range(11)]
    for x, pressed in ((0, True), (15, False)):
        capsule(a, x, 422, 14, 11, pressed, lambda i, j: plain[j])


def make_balance(main):
    a = new(68, 433, SHELL)
    seat = track_seat(38)
    for i in range(28):
        y = i * 15
        a[y:y + 13, 9:47] = seat
        a[y + 13:y + 15, 9:47] = main[70:72, 177:215]
        t = i / 27
        reach = round(16 * t)
        for x in range(2, 36):
            d = x - 18.5
            hgt = 1 + round(4 * min(abs(d), 16) / 16)
            top = y + 9 - hgt
            on = abs(d) <= reach + 0.5 and i > 0
            rect(a, 9 + x, top, 1, hgt, LCD_INK if on else LCD_GHOST)
        rect(a, 9 + 18, y + 3, 2, 1, LCD_INK)
    thumbs(a, track_seat(68))
    return a


# ------------------------------------------------------------------------------------------
# eqmain.bmp (275 x 315)
# ------------------------------------------------------------------------------------------

EQ_BANDS = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]


def name_plate_bar(w, h, lit, title, font=FONT5, plate_y=2, plate_h=None):
    """A 14px (EQ) top bar: chain either side of an LCD nameplate."""
    a = new(w, h, SHELL)
    bar_shading(a, 0, 0, w, h)
    left_edge(a, 0, 0, h)
    right_edge(a, w - 2, 0, h)
    tw = text_w(font, title)
    ph = plate_h or (h - 4)
    pw = tw + 10
    px0 = (w - pw) // 2
    chain(a, 6, px0 - 3, h // 2, lit, phase=1)
    chain(a, px0 + pw + 3, w - 16, h // 2, lit, phase=px0 + pw + 3)
    plate(a, px0, plate_y, pw, lit, ph)
    draw_text(a, font, title, px0 + 5, plate_y + (ph - 5) // 2, TITLE_LIT if lit else TITLE_DIM)
    return a


def eq_titlebar(lit):
    a = name_plate_bar(275, 14, lit, "EQUALIZER", plate_y=2, plate_h=10)
    mini_button(a, 264, 3, "close", lit)
    return a


def eq_slider_frame(a, x, y, n):
    """14x63 LCD slot whose bar rises with the value (n of 0..27)."""
    rect(a, x, y, 14, 63, SHELL)
    lcd_window(a, x + 1, y + 1, 12, 61)
    v = n / 27
    top = round((1 - v) * 51) + 6
    for r in range(3, 60):
        on = r >= top
        rect(a, x + 5, y + r, 4, 1, LCD_INK if on else LCD_GHOST)
        if r % 2 == 0:
            rect(a, x + 5, y + r, 4, 1, LCD if not on else lerp(LCD_INK, LCD, 0.35))
    # the zero mark
    rect(a, x + 2, y + 31, 2, 1, LCD_MID)
    rect(a, x + 10, y + 31, 2, 1, LCD_MID)


def make_eqmain():
    a = new(275, 315, SHELL)
    # background window
    rect(a, 0, 115, 275, 1, SHELL_DK)
    rect(a, 1, 114, 273, 1, SHELL_LO)
    left_edge(a, 0, 0, 116)
    right_edge(a, 273, 0, 116)
    a[0:14, :] = eq_titlebar(True)
    # graph window
    lcd_window(a, 86, 17, 113, 19)
    for lbl, yy in (("+12", 40), ("0", 66), ("-12", 92)):
        text_center(a, TINY, lbl, 59, yy, PLUM)
        rect(a, 43, yy + 2, 4, 1, PLUM_DIM)
        rect(a, 71, yy + 2, 4, 1, PLUM_DIM)
    text_center(a, TINY, "DB", 59, 79, PLUM_DIM)
    text_center(a, TINY, "DB", 59, 53, PLUM_DIM)
    for x in [21] + [78 + 18 * i for i in range(10)]:
        eq_slider_frame(a, x, 38, 14)
    text_center(a, TINY, "PRE", 28, 104, PLUM)
    for i, lbl in enumerate(EQ_BANDS):
        text_center(a, TINY, lbl, 78 + 18 * i + 7, 104, PLUM)
    bg = a.copy()
    # under the window: buttons
    b = bg[3:12, 264:273].copy()
    mini_button(b, 0, 0, "close", True, pressed=True)
    a[125:134, 0:9] = b
    for x, label, on, pressed in [
        (10, "ON", False, False), (36, "AUTO", False, False), (69, "ON", True, False), (95, "AUTO", True, False),
        (128, "ON", False, True), (154, "AUTO", False, True), (187, "ON", True, True), (213, "AUTO", True, True),
    ]:
        w = 26 if label == "ON" else 32
        dx = 14 if label == "ON" else 40
        toggle(a, x, 119, w, 12, label, on, pressed, bg[18:30, dx:dx + w])
    a[134:148, :] = eq_titlebar(True)
    a[149:163, :] = eq_titlebar(False)
    # slider thumbs: corners are the slot's LCD
    for yy, pressed in ((164, False), (176, True)):
        candy_button(a, 0, yy, 11, 11, pressed=pressed, bg=lambda i, j: LCD)
    for n in range(28):
        eq_slider_frame(a, 13 + (n % 14) * 15, 164 + (n // 14) * 65, n)
    for y, pressed in ((164, False), (176, True)):
        pill(a, 224, y, 44, 12, pressed, bg[18:30, 217:261])
        o = 1 if pressed else 0
        text_center(a, TINY, "PRESETS", 224 + 22 + o, y + 3 + o, PLUM)
    # graph
    rect(a, 0, 294, 113, 19, LCD)
    for x in range(0, 113, 12):
        for y in range(1, 19, 2):
            px(a, 2 + x, 294 + y, LCD_GHOST)
    for x in range(0, 113, 2):
        px(a, x, 294 + 9, LCD_GHOST)
    for r in range(19):
        px(a, 115, 294 + r, LCD_INK)
    for x in range(113):
        px(a, x, 314, LCD_MID if x % 3 != 2 else LCD)
    return a


# ------------------------------------------------------------------------------------------
# pledit.bmp (280 x 186) and gen.bmp (194 x 109): the 20px-titled frames
# ------------------------------------------------------------------------------------------

CHAIN_Y20 = 8
PLATE_Y = 3


def bar20(w):
    a = new(w, 20, SHELL)
    bar_shading(a, 0, 0, w, 20)
    return a


def side_tile_left(w, h, ring_x):
    t = new(w, h, SHELL)
    left_edge(t, 0, 0, h)
    rect(t, ring_x, 0, 1, h, SHELL_DK)
    rect(t, ring_x - 1, 0, 1, h, SHELL_MID)
    return t


def make_pledit():
    a = new(280, 186, SHELL)
    for lit, y in ((True, 0), (False, 21)):
        # top tile
        t = bar20(25)
        chain(t, 0, 25, CHAIN_Y20, lit)
        rect(t, 0, 19, 25, 1, SHELL_DK)
        a[y:y + 20, 127:152] = t
        # top-left corner
        t = bar20(25)
        left_edge(t, 0, 0, 20)
        chain(t, 4, 25, CHAIN_Y20, lit)
        rect(t, 11, 19, 14, 1, SHELL_DK)
        rect(t, 10, 19, 1, 1, SHELL_MID)
        a[y:y + 20, 0:25] = t
        # title
        t = bar20(100)
        title = "PLAYLIST"
        plate(t, 18, PLATE_Y, 64, lit, 9)
        text_center(t, FONT5, title, 50, PLATE_Y + 2, TITLE_LIT if lit else TITLE_DIM)
        chain(t, 0, 15, CHAIN_Y20, lit)
        chain(t, 85, 100, CHAIN_Y20, lit)
        rect(t, 0, 19, 100, 1, SHELL_DK)
        a[y:y + 20, 26:126] = t
        # top-right corner: close button, the scrollbar groove's top
        t = bar20(25)
        right_edge(t, 23, 0, 20)
        chain(t, 0, 12, CHAIN_Y20, lit)
        mini_button(t, 14, 3, "close", lit)
        rect(t, 0, 19, 5, 1, SHELL_DK)
        rect(t, 5, 19, 1, 1, SHELL_HI)
        # groove top cap
        rect(t, 9, 14, 10, 1, SHELL_DK)
        rect(t, 9, 14, 1, 6, SHELL_DK)
        rect(t, 18, 14, 1, 6, SHELL_HI)
        rect(t, 10, 15, 8, 5, LCD)
        rect(t, 10, 15, 8, 1, LCD_SHADE)
        a[y:y + 20, 153:178] = t

    # left side tile
    t = side_tile_left(12, 29, 11)
    a[42:71, 0:12] = t
    # right side tile: list edge, scrollbar groove at 5..12, outer edge
    t = new(20, 29, SHELL)
    rect(t, 0, 0, 1, 29, SHELL_HI)
    rect(t, 4, 0, 1, 29, SHELL_DK)
    rect(t, 5, 0, 8, 29, LCD)
    rect(t, 13, 0, 1, 29, SHELL_HI)
    rect(t, 8, 0, 2, 29, LCD_GHOST)
    right_edge(t, 18, 0, 29)
    a[42:71, 31:51] = t
    # close pressed, scroll handles
    t = a[3:12, 167:176].copy()
    mini_button(t, 0, 0, "close", True, pressed=True)
    a[42:51, 52:61] = t
    for x, sel in ((52, False), (61, True)):
        capsule_v(a, x, 53, 8, 18, sel, lambda i, j: LCD)

    def bottom_base(w):
        t = new(w, 38, SHELL)
        rect(t, 0, 37, w, 1, SHELL_DK)
        rect(t, 0, 36, w, 1, SHELL_LO)
        rect(t, 0, 0, w, 1, SHELL_HI)
        return t

    t = bottom_base(125)
    left_edge(t, 0, 0, 37)
    rect(t, 11, 0, 1, 1, SHELL_DK)
    rect(t, 2, 0, 9, 1, SHELL)
    rect(t, 10, 0, 1, 1, SHELL_MID)
    for bx, lbl in ((14, "ADD"), (43, "REM"), (72, "SEL"), (101, "MISC")):
        pill(t, bx, 9, 22, 13, False, t[9:22, bx:bx + 22].copy())
        text_center(t, TINY, lbl, bx + 11, 13, PLUM)
    a[72:110, 0:125] = t

    t = bottom_base(150)
    right_edge(t, 148, 0, 37)
    rect(t, 131, 0, 17, 1, SHELL)
    rect(t, 130, 0, 1, 1, SHELL_HI)
    rect(t, 134, 0, 10, 1, SHELL_HI)       # the scrollbar groove's bottom
    # running time readout
    lcd_window(t, 7, 10, 54, 7)
    # mini transport
    icons = ["previous", "play", "pause", "stop", "next", "eject"]
    for k, kind in enumerate(icons):
        bx = 3 + 10 * k
        bgc = t[22:32, bx:bx + 10].copy()
        candy_button(t, bx, 22, 10, 10, bg=lambda i, j, b=bgc: tuple(b[j, i]))
        mini_transport_icon(t, kind, bx, 22)
    # mini time
    lcd_window(t, 66, 23, 31, 6)
    rect(t, 84, 22 + 2, 1, 1, LCD_INK)
    rect(t, 84, 22 + 5, 1, 1, LCD_INK)
    # LIST button
    pill(t, 106, 9, 22, 13, False, t[9:22, 106:128].copy())
    text_center(t, TINY, "LIST", 117, 13, PLUM)
    # resize grip
    for k in range(4):
        for j in range(k + 1):
            gx, gy = 144 - 3 * k + 3 * j, 30 - 3 * j
            px(t, gx, gy, SHELL_DK)
            px(t, gx + 1, gy + 1, SHELL_HI)
    a[72:110, 126:276] = t

    t = bottom_base(25)
    a[0:38, 179:204] = t
    return a


def capsule_v(a, x, y, w, h, pressed, bg):
    """A vertical lemon capsule (the scrollbar handle)."""
    b = new(h, w, SHELL)
    capsule(b, 0, 0, h, w, pressed, lambda i, j: bg(j, i))
    a[y:y + h, x:x + w] = b.transpose(1, 0, 2)
    for gy in (y + 7, y + 9):
        rect(a, x + 2, gy, w - 4, 1, LEMON_DK)


def mini_transport_icon(a, kind, x, y):
    ink = PLUM
    cx, cy = x + 5, y + 5
    if kind == "previous":
        rect(a, cx - 3, cy - 2, 1, 5, ink)
        tri_left(a, cx - 2, cy - 2, 5, ink)
    elif kind == "play":
        tri_right(a, cx - 1, cy - 2, 5, ink)
    elif kind == "pause":
        rect(a, cx - 2, cy - 2, 1, 5, ink)
        rect(a, cx + 1, cy - 2, 1, 5, ink)
    elif kind == "stop":
        rect(a, cx - 2, cy - 2, 4, 4, ink)
    elif kind == "next":
        tri_right(a, cx - 1, cy - 2, 5, ink)
        rect(a, cx + 2, cy - 2, 1, 5, ink)
    elif kind == "eject":
        for r in range(2):
            rect(a, cx - 1 - r, cy - 2 + r, 2 * r + 2, 1, ink)
        rect(a, cx - 2, cy + 1, 4, 1, ink)


GEN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def make_gen():
    a = new(194, 109, SHELL)
    for lit, y in ((True, 0), (False, 21)):
        def piece(px0, fn):
            t = bar20(25)
            fn(t)
            a[y:y + 20, px0:px0 + 25] = t

        def left(t):
            left_edge(t, 0, 0, 20)
            chain(t, 4, 25, CHAIN_Y20, lit)
            rect(t, 11, 19, 14, 1, SHELL_DK)
            rect(t, 10, 19, 1, 1, SHELL_MID)

        def left_end(t):
            chain(t, 0, 20, CHAIN_Y20, lit)
            plate(t, 22, PLATE_Y, 8, lit)
            rect(t, 0, 19, 25, 1, SHELL_DK)

        def centre(t):
            rect(t, 0, PLATE_Y, 25, 1, SHELL_DK)
            rect(t, 0, PLATE_Y + 1, 25, 7, LCD if lit else lerp(LCD, SHELL_MID, 0.25))
            rect(t, 0, PLATE_Y + 8, 25, 1, SHELL_HI)
            rect(t, 0, 19, 25, 1, SHELL_DK)

        def right_end(t):
            centre(t)
            rect(t, 3, PLATE_Y, 22, 9, SHELL)
            rect(t, 2, PLATE_Y, 1, 9, SHELL_HI)
            px(t, 2, PLATE_Y, SHELL_LO)
            chain(t, 5, 25, CHAIN_Y20, lit)

        def fill(t):
            chain(t, 0, 25, CHAIN_Y20, lit)
            rect(t, 0, 19, 25, 1, SHELL_DK)

        def right(t):
            chain(t, 0, 12, CHAIN_Y20, lit)
            mini_button(t, 14, 3, "close", lit)
            right_edge(t, 23, 0, 20)
            rect(t, 0, 19, 14, 1, SHELL_DK)
            rect(t, 14, 19, 1, 1, SHELL_HI)

        piece(0, left)
        piece(26, left_end)
        piece(52, centre)
        piece(78, right_end)
        piece(104, fill)
        piece(130, right)

    # bottom caps and fill (14 tall)
    def bottom(w, grip, left_side):
        t = new(w, 14, SHELL)
        rect(t, 0, 13, w, 1, SHELL_DK)
        rect(t, 0, 12, w, 1, SHELL_LO)
        rect(t, 0, 0, w, 1, SHELL_HI)
        if left_side:
            left_edge(t, 0, 0, 13)
            rect(t, 2, 0, 8, 1, SHELL)
            rect(t, 10, 0, 1, 1, SHELL_DK)
        else:
            right_edge(t, w - 2, 0, 13)
            rect(t, w - 10, 0, 8, 1, SHELL)
        if grip:
            for k in range(3):
                for j in range(k + 1):
                    gx, gy = w - 5 - 3 * k + 3 * j, 9 - 3 * j
                    px(t, gx, gy, SHELL_DK)
                    px(t, gx + 1, gy + 1, SHELL_HI)
        return t

    a[42:56, 0:125] = bottom(125, False, True)
    a[57:71, 0:125] = bottom(125, True, False)
    t = new(25, 14, SHELL)
    rect(t, 0, 13, 25, 1, SHELL_DK)
    rect(t, 0, 12, 25, 1, SHELL_LO)
    rect(t, 0, 0, 25, 1, SHELL_HI)
    a[72:86, 127:152] = t
    # sides
    for x, w, h, outer_left in ((127, 11, 29, True), (158, 11, 24, True), (139, 8, 29, False), (170, 8, 24, False)):
        if outer_left:
            t = side_tile_left(w, h, 10)
        else:
            t = new(w, h, SHELL)
            right_edge(t, w - 2, 0, h)
        a[42:42 + h, x:x + w] = t
    t = a[3:12, 144:153].copy()
    mini_button(t, 0, 0, "close", True, pressed=True)
    a[42:51, 148:157] = t

    # letters: each row starts at x 1, letters in their own cells, 1px separators of x 0's colour
    for lit, y in ((True, 88), (False, 96)):
        rect(a, 0, y, 194, 7, SEP)
        x = 1
        for c in GEN_LETTERS:
            w = glyph_w(FONT5, c) + 1
            rect(a, x, y, w, 7, LCD if lit else lerp(LCD, SHELL_MID, 0.25))
            draw_text(a, FONT5, c, x, y + 1, TITLE_LIT if lit else TITLE_DIM)
            x += w + 1
        assert x <= 194, x
    return a


# ------------------------------------------------------------------------------------------
# genex.bmp: Media Library colours along the top row, every other pixel from x 48
# ------------------------------------------------------------------------------------------

GENEX_COLOURS = [
    LCD,                # item background
    LCD_INK,            # item text
    (252, 214, 228),    # window background
    PLUM,               # button text
    PLUM,               # window text
    SHELL_LO,           # dividers, sunken borders
    (84, 96, 66),       # selection bar
    SHELL,              # list header background
    PLUM,               # list header text
    SHELL_HI,           # header frame, light
    SHELL_DK,           # header frame, dark
    SHELL_LO,           # header frame, pressed
    (252, 214, 228),    # header dead area
    LEMON,              # scrollbar
    LCD,                # scrollbar 2
    LEMON_LO,           # scrollbar pressed
    LCD_SHADE,          # scrollbar pressed 2
    (236, 190, 208),    # scrollbar dead area
]


def make_genex():
    a = new(256, 64, SHELL)
    for i, c in enumerate(GENEX_COLOURS):
        px(a, 48 + 2 * i, 0, c)
    return a


# ------------------------------------------------------------------------------------------
# Text files
# ------------------------------------------------------------------------------------------

VISCOLOR = (
    [(LCD, "background"), (LCD_GHOST, "dots")]
    + [(ramp([(30, 34, 22), LCD_INK, (66, 76, 52)], i / 15), f"spectrum {i + 1} (top)" if i == 0 else
        f"spectrum {i + 1}") for i in range(16)]
    + [(LCD_INK, "oscilloscope 1"), ((52, 60, 40), "oscilloscope 2"), ((62, 72, 48), "oscilloscope 3"),
       ((74, 84, 58), "oscilloscope 4"), ((86, 98, 68), "oscilloscope 5"), ((24, 28, 18), "peaks")]
)

PLEDIT = dict(Normal="#2A3020", Current="#8C1A54", NormalBG="#9AA88A", SelectedBG="#BFCBAF",
              MbBG="#9AA88A", MbFG="#2A3020", Font="Arial")


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def readme_text(name):
    title = name.replace("-", " ").replace("_", " ")
    line = f"{title} - a virtual-pet keychain toy, drawn from scratch."
    return (
        f"{line}\n"
        f"{'=' * len(line)}\n\n"
        "A classic (Winamp 2.x format) skin in the style of the late-90s egg-shaped\n"
        "LCD pet toys: glossy candy-pink plastic, round lemon buttons, a silver ball\n"
        "chain, and a greenish-grey LCD with the care icons and an original pixel\n"
        "creature in headphones. The seek bar is the creature taking a walk, and the\n"
        "volume is a row of hearts. Every bitmap was drawn by a script (gen_skin.py);\n"
        "nothing was taken from any other skin or product, and it carries no logos or\n"
        "marks.\n\n"
        "License: CC0 1.0 Universal (public domain dedication).\n"
        "https://creativecommons.org/publicdomain/zero/1.0/\n"
    )


def write_text_files(name, readme_path):
    with open(os.path.join(OUT, "viscolor.txt"), "w", newline="\r\n") as f:
        for (r, g, b), note in VISCOLOR:
            f.write(f"{r},{g},{b}, // {note}\n")
    with open(os.path.join(OUT, "pledit.txt"), "w", newline="\r\n") as f:
        f.write("[Text]\n" + "".join(f"{k}={v}\n" for k, v in PLEDIT.items()))
    if readme_path:
        with open(readme_path, encoding="ascii") as f:
            text = f.read()
    else:
        text = readme_text(name)
    text.encode("ascii")
    with open(os.path.join(OUT, "readme.txt"), "w", newline="\r\n") as f:
        f.write(text)


# ------------------------------------------------------------------------------------------
# Build
# ------------------------------------------------------------------------------------------

SHEETS = {}


def build(title, name, dest, readme_path):
    main = make_main(title)
    sheets = {
        "main.bmp": main,
        "titlebar.bmp": make_titlebar(title),
        "cbuttons.bmp": make_cbuttons(main),
        "shufrep.bmp": make_shufrep(main),
        "posbar.bmp": make_posbar(),
        "volume.bmp": make_volume(main),
        "balance.bmp": make_balance(main),
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
    # main.bmp also shows the buttons and toggles (off) where their sprites go
    cb, sr = sheets["cbuttons.bmp"], sheets["shufrep.bmp"]
    for kind, x, w, h, dx, dy in TRANSPORT:
        main[dy:dy + h, dx:dx + w] = cb[0:h, x:x + w]
    main[89:105, 136:158] = cb[0:16, 114:136]
    main[89:104, 164:211] = sr[0:15, 28:75]
    main[89:104, 210:238] = sr[0:15, 0:28]
    main[58:70, 219:242] = sr[61:73, 0:23]
    main[58:70, 242:265] = sr[61:73, 23:46]
    main[72:82, 16:264] = sheets["posbar.bmp"][:, 0:248]
    main[57:70, 107:175] = sheets["volume.bmp"][0:13, :]
    main[57:70, 177:215] = sheets["balance.bmp"][0:13, 9:47]
    for n, arr in sheets.items():
        SHEETS[n[:-4]] = save(arr, n)
    write_text_files(name, readme_path)
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
    return names


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
for _k, _v in {"<": "[", ">": "]", "{": "[", "}": "]"}.items():
    FONT_LOOKUP[_k] = FONT_LOOKUP[_v]


def draw_bitmap_text(dst, s, x, y):
    text = SHEETS["text"]
    for ch in s:
        row, col = FONT_LOOKUP.get(ch.lower(), FONT_LOOKUP[" "])
        blit(dst, text, (col * 5, row * 6, 5, 6), x, y)
        x += 5


def text_ink():
    """text.bmp's ink as the app finds it: the commonest colour that isn't the background."""
    t = np.array(SHEETS["text"]).reshape(-1, 3)
    bg = tuple(t[0])
    cols, counts = np.unique(t, axis=0, return_counts=True)
    order = [(c, tuple(col)) for col, c in zip(cols, counts) if tuple(col) != bg]
    return max(order)[1]


def ttf(size):
    for name in ("/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


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
    # title: the space cell across the box, then the title in a TrueType font in text.bmp's ink,
    # clipped to rows 22..35, as the app draws it
    for x in range(0, 154, 5):
        w = min(5, 154 - x)
        blit(img, S["text"], (150, 0, w, 6), 111 + x, 24)
    layer = Image.new("RGB", (154, 14), (0, 0, 0))
    mask = Image.new("L", (154, 14), 0)
    ImageDraw.Draw(mask).text((0, 24 + 3 + 2 - 22), state["title"], fill=255, font=ttf(11), anchor="ls")
    layer.paste(Image.new("RGB", (154, 14), text_ink()), (0, 0))
    img.paste(layer, (111, 22), mask)
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
    font = ttf(9)
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
    piece = lambda px0: (px0, ty, 25, 20)  # noqa: E731
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
    # a stand-in picture: the LCD with the pet, large
    pw, ph = w - 22, h - 34
    pic = new(pw, ph, LCD)
    big = new(17, 15, LCD)
    sprite(big, PET_SING, 0, 0, LCD_INK)
    k = max(1, min(pw // 30, ph // 22))
    big = np.kron(big, np.ones((k, k, 1), dtype=np.int32))
    oy, ox = (ph - big.shape[0]) // 2, (pw - big.shape[1]) // 2
    pic[oy:oy + big.shape[0], ox:ox + big.shape[1]] = big
    img.paste(Image.fromarray(np.clip(pic, 0, 255).astype(np.uint8)), (11, 20))
    return img


def preview(dest, title, tall=False):
    rows = [("Pocket Friend - Feed Me Twice", "4:12"), ("Egg Timer - Hatch Day", "3:47"),
            ("Beep Beep - Attention Please", "5:03"), ("Lights Out - Bedtime", "2:58"),
            ("Bath Bubbles - Squeaky Duck", "6:21"), ("Heart Meter - Four Out of Four", "3:33"),
            ("Ball Game - Left or Right", "4:40"), ("Ball Chain - Keyring", "3:09"),
            ("Recess - Backpack Clip", "5:51"), ("Tiny Pixels - Big Feelings", "4:05"),
            ("Battery Tab - Pull to Start", "3:22")]
    bars = [12, 15, 14, 11, 13, 10, 9, 11, 8, 7, 9, 6, 5, 6, 4, 3, 4, 2, 3]
    A = dict(pressed=None, eq=True, pl=True, clutter="AV", shuffle=True, repeat=False, playing=True, stereo=True,
             pos=0.38, seek=False, volume=72, vdrag=False, balance=0, time=207, remaining=False,
             title="Pixel Pet - Feed Me Twice (Hatch Day Mix)", bars=bars)
    B = dict(pressed="play", eq=False, pl=True, clutter="", shuffle=False, repeat=True, playing=False, stereo=False,
             pos=0.8, seek=True, volume=25, vdrag=True, balance=-60, time=95, remaining=True,
             title="Paused: Lights Out (Bedtime)", bars=[3, 2, 4, 1, 2, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    EA = dict(pressed=None, on=True, auto=False, preamp=50, drag=None,
              bands=[75, 68, 56, 49, 49, 33, 30, 30, 49, 49])
    EB = dict(pressed="close", on=False, auto=True, preamp=70, drag=3,
              bands=[51, 51, 59, 65, 65, 100, 59, 51, 0, 51])
    cols = []
    ph, gh = (464, 280) if tall else (232, 140)
    for lit, st, est in ((True, A, EA), (False, B, EB)):
        h = 116 + 116 + ph + gh
        col = Image.new("RGB", (275, h))
        col.paste(preview_main(lit, st), (0, 0))
        col.paste(preview_eq(lit, est), (0, 116))
        col.paste(preview_playlist(lit, 275, ph, rows, pressed_close=not lit, drag=not lit), (0, 232))
        col.paste(preview_gen(lit, 275, gh, "album art", pressed_close=not lit), (0, 232 + ph))
        cols.append(col)
    gap = 12
    out = Image.new("RGB", (275 * 2 + gap * 3, cols[0].height + gap * 2), (92, 70, 84))
    out.paste(cols[0], (gap, gap))
    out.paste(cols[1], (275 + 2 * gap, gap))
    out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
    if tall:
        os.makedirs(os.path.join(OUT, "scratch"), exist_ok=True)
        out.save(os.path.join(OUT, "scratch", "preview-tall.png"))
    else:
        out.save(os.path.join(dest, "preview.png"))


def main():
    global OUT
    ap = argparse.ArgumentParser(description="Build the Pixel Pet skin.")
    ap.add_argument("--list", action="store_true", help="print the theme and build nothing")
    ap.add_argument("--title", default=TITLE, help='the main titlebar\'s lettering (default "YTMinamp")')
    ap.add_argument("--name", default=SKIN, help="the .wsz's base name (readme.txt's title follows)")
    ap.add_argument("--out", default=HERE, help="where the .wsz and preview.png go; sheets in OUT/out/")
    ap.add_argument("--readme", default=None, help="a plain-ASCII readme.txt to ship instead")
    ap.add_argument("themes", nargs="*", help=f"theme names to build (there is one: {THEME})")
    args = ap.parse_args()
    if args.list:
        print(THEME)
        return 0
    for t in args.themes:
        if t != THEME:
            ap.error(f"unknown theme {t!r} (there is one: {THEME})")
    dest = os.path.abspath(args.out)
    OUT = os.path.join(dest, "out")
    os.makedirs(OUT, exist_ok=True)
    names = build(args.title, args.name, dest, args.readme)
    preview(dest, args.title)
    preview(dest, args.title, tall=True)
    for n in names:
        p = os.path.join(OUT, n)
        if n.endswith(".bmp"):
            im = Image.open(p)
            print(f"{n:14s} {im.size[0]}x{im.size[1]} {im.mode}")
        else:
            print(f"{n:14s} {os.path.getsize(p)} bytes")
    print(os.path.join(dest, f"{args.name}.wsz"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
