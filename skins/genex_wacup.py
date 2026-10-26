#!/usr/bin/python3
"""Finish a skin for real Winamp and WACUP, in place in its .wsz: a complete genex.bmp, and
plain-ASCII text files (Winamp reads readme.txt and the like as Windows-1252, so UTF-8's em dash
or (c) sign comes out as "â€”" or "Â©").

Winamp's SDK (wa_dlg.h) reads 24 colours from genex.bmp's top row, one every other pixel from
x = 48, and falls back to a default for any pixel that is (0,198,255) or equal to the pixel at
(111,0). It also draws the Media Library's buttons and scrollbars from images on the same sheet:

    button          (0,0) 47x15, pressed (0,15) 47x15   (4 px edges kept, centre stretched)
    scroll arrows   up, down, up pressed, down pressed: (0|14|28|42, 31) 14x14
                    left, right, pressed: (0|14|28|42, 45) 14x14
    vertical thumb  (56,31) 14x28, pressed (70,31) 14x28
    horiz. thumb    (84,31) 28x14, pressed (84,45) 28x14
    sheet           112x59, unused space (0,198,255)

The skins generated here wrote 18 colours on a wider sheet whose background (and so the pixel at
x = 111) was often one of those colours, and no scrollbar art: WACUP then defaulted the window
background and every selection colour, and selected rows and menus came out dark on dark. This
keeps the skin's 18 colours, derives the other six, fixes pairs that don't read (contrast below
4.5:1 for text), and redraws the sheet in the standard layout from the palette.

    /usr/bin/python3 -I genex_wacup.py SKIN.wsz [...]     rewrite each in place (deterministic)
    /usr/bin/python3 -I genex_wacup.py --check SKIN.wsz   report only
"""

import io
import re
import sys
import unicodedata
import zipfile

from PIL import Image, ImageDraw

W, H = 112, 59
CYAN = (0, 198, 255)
NAMES = [
    "itemBG", "itemFG", "wndBG", "buttonFG", "wndFG", "hilite", "selColor",
    "hdrBG", "hdrFG", "hdrTop", "hdrMid", "hdrBot", "hdrEmpty",
    "sbFG", "sbBG", "sbInvFG", "sbInvBG", "sbDead",
    "selbarFG", "selbarBG", "inactSelFG", "inactSelBG", "itemBG2", "itemFG2",
]
ZIP_DATE = (2000, 1, 1, 0, 0, 0)


def lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def readable(fg, bg, need=4.5):
    """`fg` if it reads on `bg`, else `fg` pushed toward black or white until it does."""
    if contrast(fg, bg) >= need:
        return fg
    target = (0, 0, 0) if lum(bg) > 0.18 else (255, 255, 255)
    for i in range(1, 21):
        c = mix(fg, target, i / 20)
        if contrast(c, bg) >= need:
            return c
    return target


def complete(old):
    """The 24 colours from the skin's first 18, with the missing six derived and text fixed."""
    c = dict(zip(NAMES, old[:18]))
    c["itemFG"] = readable(c["itemFG"], c["itemBG"])
    c["wndFG"] = readable(c["wndFG"], c["wndBG"])
    c["hdrFG"] = readable(c["hdrFG"], c["hdrBG"])
    # The button face is drawn from the window background here, so its text reads on that.
    c["buttonFG"] = readable(c["buttonFG"], button_face(c))
    # The selection bar must differ from the list, and its text read on it.
    sel = c["selColor"]
    if contrast(sel, c["itemBG"]) < 1.25:
        sel = mix(sel, (255, 255, 255) if lum(c["itemBG"]) < 0.18 else (0, 0, 0), 0.25)
        c["selColor"] = sel
    c["selbarBG"] = sel
    c["selbarFG"] = readable(c["itemFG"], sel)
    c["inactSelBG"] = mix(sel, c["itemBG"], 0.45)
    c["inactSelFG"] = readable(c["itemFG"], c["inactSelBG"])
    # Alternate rows: a whisper off the item background, same text.
    toward = (255, 255, 255) if lum(c["itemBG"]) < 0.18 else (0, 0, 0)
    c["itemBG2"] = mix(c["itemBG"], toward, 0.04)
    c["itemFG2"] = readable(c["itemFG"], c["itemBG2"])
    # No colour may equal the fallback marker.
    for k, v in c.items():
        if v == CYAN:
            c[k] = (0, 197, 255)
    return c


def button_face(c):
    return mix(c["wndBG"], c["hdrBG"], 0.5)


def bevel(d, box, face, light, dark):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=face)
    d.line([(x0, y0), (x1, y0)], fill=light)
    d.line([(x0, y0), (x0, y1)], fill=light)
    d.line([(x0, y1), (x1, y1)], fill=dark)
    d.line([(x1, y0), (x1, y1)], fill=dark)


def arrow(d, x, y, direction, colour):
    cx, cy = x + 7, y + 7
    pts = {
        "up": [(cx - 3, cy + 1), (cx + 3, cy + 1), (cx, cy - 2)],
        "down": [(cx - 3, cy - 1), (cx + 3, cy - 1), (cx, cy + 2)],
        "left": [(cx + 1, cy - 3), (cx + 1, cy + 3), (cx - 2, cy)],
        "right": [(cx - 1, cy - 3), (cx - 1, cy + 3), (cx + 2, cy)],
    }[direction]
    d.polygon(pts, fill=colour)


def draw_sheet(c):
    img = Image.new("RGB", (W, H), CYAN)
    d = ImageDraw.Draw(img)
    face = button_face(c)
    light = mix(face, (255, 255, 255), 0.35)
    dark = mix(face, (0, 0, 0), 0.45)
    # Buttons: normal, then pressed (darker, bevel inverted).
    bevel(d, (0, 0, 46, 14), face, light, dark)
    pressed = mix(face, (0, 0, 0), 0.15)
    bevel(d, (0, 15, 46, 29), pressed, dark, light)
    # Scroll arrows on the header colours, glyph in header text.
    hface, htext = c["hdrBG"], c["hdrFG"]
    hl, hd = mix(hface, (255, 255, 255), 0.35), mix(hface, (0, 0, 0), 0.45)
    hp = mix(hface, (0, 0, 0), 0.15)
    for row, dirs in ((31, ("up", "down")), (45, ("left", "right"))):
        for i, direction in enumerate(dirs):
            for k, (f, a, b) in enumerate(((hface, hl, hd), (hp, hd, hl))):
                x = 14 * i + 28 * k
                bevel(d, (x, row, x + 13, row + 13), f, a, b)
                arrow(d, x, row, direction, htext)
    # Thumbs on the scrollbar foreground, with a grip.
    tf = c["sbFG"] if contrast(c["sbFG"], c["sbBG"]) >= 1.3 else mix(c["sbBG"], htext, 0.35)
    tl, td = mix(tf, (255, 255, 255), 0.35), mix(tf, (0, 0, 0), 0.45)
    tp = mix(tf, (0, 0, 0), 0.15)
    grip = readable(htext, tf, 2.0)
    for k, (f, a, b) in enumerate(((tf, tl, td), (tp, td, tl))):
        x = 56 + 14 * k
        bevel(d, (x, 31, x + 13, 58), f, a, b)
        for gy in (41, 44, 47):
            d.line([(x + 4, gy), (x + 9, gy)], fill=grip)
        y = 31 + 14 * k
        bevel(d, (84, y, 111, y + 13), f, a, b)
        for gx in (94, 97, 100):
            d.line([(gx, y + 4), (gx, y + 9)], fill=grip)
    # The colour row, last so nothing covers it; x = 111 stays the marker on row 0.
    for i, name in enumerate(NAMES):
        img.putpixel((48 + 2 * i, 0), c[name])
    img.putpixel((111, 0), CYAN)
    return img


def old_colours(img):
    img = img.convert("RGB")
    return [img.getpixel((48 + 2 * i, 0)) for i in range(18)]


def report(name, c):
    pairs = [
        ("item text", "itemFG", "itemBG"), ("window text", "wndFG", "wndBG"),
        ("header text", "hdrFG", "hdrBG"), ("selected text", "selbarFG", "selbarBG"),
        ("inactive selected", "inactSelFG", "inactSelBG"),
    ]
    worst = min(contrast(c[a], c[b]) for _, a, b in pairs)
    return f"{name}: lowest text contrast {worst:.1f}:1"


# What NFKD can't spell in ASCII, spelled out; anything else left is dropped.
ASCII = {
    "\u2014": "-", "\u2013": "-", "\u2012": "-", "\u2010": "-", "\u2212": "-",
    "\u00a9": "(c)", "\u00ae": "(R)", "\u2122": "(TM)", "\u00d7": "x", "\u00b7": "-",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2026": "...",
    "\u00a0": " ", "\u2022": "*", "\u2726": "*", "\u2605": "*", "\u25b8": ">", "\u25be": "v",
    "\u2192": "->", "\u2190": "<-", "\u03a0": "N", "\u0394": "A", "\u00f8": "o", "\u00d8": "O",
    "\u00df": "ss", "\u00e6": "ae", "\u00c6": "AE",
}


def ascii_text(raw):
    """A text file's bytes as plain ASCII (read as UTF-8, else Windows-1252), CRLF kept as is."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    text = "".join(ASCII.get(ch, ch) for ch in text)
    text = unicodedata.normalize("NFKD", text)
    return text.encode("ascii", errors="ignore")


def tidy_readme(text):
    """A skin's readme.txt without the boilerplate that belongs in its collection's README (use,
    affiliation): the skin's name, what it's in the style of, and the credits stay."""
    text = re.sub(r";\s*(for\s+)?private use only", "", text, flags=re.I)
    text = re.sub(r"\s*(for\s+)?private use only\.?", "", text, flags=re.I)
    text = re.sub(r"\s*Not affiliated\s+(or endorsed\s+)?with[^.]*\.", "", text, flags=re.I)
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)
    text = re.sub(r"\ba personal (fan )?skin", lambda m: f"a {m.group(1) or ''}skin", text, flags=re.I)
    return re.sub(r"[ \t]+(\r?\n)", r"\1", text).strip() + "\r\n"


def process(path, check=False):
    z = zipfile.ZipFile(path)
    entries = [(i, z.read(i.filename)) for i in z.infolist()]
    z.close()
    genex = [i for i, _ in entries if i.filename.lower().split("/")[-1] == "genex.bmp"]
    if not genex:
        return f"{path}: no genex.bmp"
    data = dict((i.filename, b) for i, b in entries)
    img = Image.open(io.BytesIO(data[genex[0].filename]))
    c = complete(old_colours(img))
    if check:
        return report(path, c)
    out = io.BytesIO()
    draw_sheet(c).save(out, format="BMP")
    data[genex[0].filename] = out.getvalue()
    for name in data:
        if name.lower().endswith(".txt"):
            data[name] = ascii_text(data[name])
        if name.lower().split("/")[-1] == "readme.txt":
            data[name] = tidy_readme(data[name].decode("ascii")).encode("ascii")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, _ in entries:
            zi = zipfile.ZipInfo(info.filename, ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, data[info.filename])
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    return report(path, c)


if __name__ == "__main__":
    args = sys.argv[1:]
    check = "--check" in args
    for p in [a for a in args if a != "--check"]:
        print(process(p, check))
