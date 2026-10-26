# Pixel Pet: a virtual-pet keychain toy

One classic skin from a procedural generator (`gen_skin.py`, based on `skins/ember/gen_skin.py`
and keeping its sheet layouts, which follow the app's sprite map in `ui/src/lib/skin/render/*.js`
and `crates/skin/src/*.rs`), in the style of the late-90s egg-shaped LCD pet toys. It is generic:
no product's names, logos, marks or characters, and nothing in it comes from another skin. Every
pixel is drawn by the script: rectangles, pixel masks, hand-made pixel fonts and pixel art,
including the chunky lettering of "YTMinamp" in the main titlebar. CC0 1.0 (see the skin's own
readme.txt). It needs Pillow and numpy.

```sh
/usr/bin/python3 -I gen_skin.py
/usr/bin/python3 -I gen_skin.py --list
/usr/bin/python3 -I gen_skin.py --title TEXT --name NAME --out DIR [--readme FILE]
```

Outputs: `YTMinamp-Pixel-Pet.wsz` and `preview.png` here (main, EQ, playlist and a gen.bmp frame
put together from the sprites at their real positions, focused and unfocused, at 2x; the title
drawn in a TrueType font in text.bmp's ink, as the app draws it); sheets in `out/` (ignored), and
a taller preview for checking the tiled frames in `out/scratch/`. `--title` sets the main
titlebar's lettering, `--name` the .wsz's base name (readme.txt's title follows it), `--out`
where the .wsz and preview go, and `--readme` a plain-ASCII readme.txt to ship instead of the
generated one. Deterministic: no randomness, and the zip entries have a fixed date. Each .wsz is
finished by `skins/genex_wacup.py`.

## Themes

- **Pixel Pet** (one theme):
  - Shell: glossy candy-pink plastic (#F38AB4) with a plum outline and gloss along the top edges.
    The material varies only from top to bottom, so the tiled playlist and gen frames join up.
  - Titlebars: a silver ball chain (3px balls every 5px, so it runs on across the 25px frame
    tiles), hanging from a split ring beside the main window's chunky cream-and-plum lettering and
    ending in a clasp. The other windows' titles sit on small LCD nameplates. Unfocused, the chain
    and lettering fade to pink.
  - Displays: the toy's greenish-grey LCD (#9AA88A) with dark pixels (#2A3020), set into a
    recessed bezel. Along their top run the eight care icons (food, light, play, medicine, bath,
    meter, discipline, call), two lit and the rest as faint ghost pixels; the time's seven-segment
    digits show their unlit segments the same way. text.bmp's space cell is the plain LCD colour.
  - The pet: an original creature, a round little thing wearing headphones, standing beside the
    kHz readout with a note over its head. The gen frame's preview stand-in shows it large.
  - Transport: round lemon candy buttons with plum glyphs and a gloss spot; pressed, they darken
    and the glyph shifts.
  - Sliders: the seek bar is an LCD strip whose thumb is the pet walking along the ground (it hops
    while dragged); the volume is a row of seven hearts that fill up; balance fills out from the
    centre. Thumbs are lemon capsules.
  - Toggles (shuffle, repeat, EQ, PL, EQ ON/AUTO): cream pills with a tiny LCD square that goes
    dark when on.
  - The About spot: a cream egg with lemon spots and a zigzag crack.
  - viscolor: dark LCD pixels on the LCD, with ghost dots.
  - Playlist: #2A3020 on #9AA88A, #8C1A54 current, #BFCBAF selection. Font: Arial. The Media
    Library palette (genex) is LCD items in a pale pink window.

## Limits

- No speckles or printed pattern on the shell: the playlist and gen frames are tiled pieces and
  can't carry a 2D pattern without seams, so the plastic is plain on every window.
- Titlebar lettering exists for A-Z, 0-9, a few signs and the lowercase letters it uses; other
  lowercase letters fall back to capitals, and text wider than 200px is cut.
- The ball chain's spacing can jump by a pixel or two where a title piece meets the chain tiles,
  since the app places the title pieces at positions that depend on the window's width.

## Sources

- None: no downloaded assets, fonts or marks. The preview's title uses a system TrueType font
  only to show how the app draws it; nothing of it is in the .wsz.
