# VFD: a vacuum fluorescent display head unit

Two classic skins from one procedural generator (`gen_skin.py`, keeping the sheet layouts of
`skins/ember/gen_skin.py`, which follow the app's sprite map in `ui/src/lib/skin/render/*.js` and
`crates/skin/src/*.rs`). They are generic: no product's logos, model numbers or marks, only
generic hi-fi print ("SPECTRUM ANALYZER", "AUTO STORE", "AUTO REVERSE CASSETTE DECK", RDS legends).
Everything is drawn by the script: gradients, anti-aliased shapes, hand-made pixel fonts, and a
bold italic sans (Liberation Sans Bold Italic, falling back to DejaVu Sans Bold Oblique) for the
faceplate print, "YTMinamp" in the main titlebar. CC0 1.0 (see each skin's readme.txt). It needs
Pillow and numpy.

```sh
/usr/bin/python3 -I gen_skin.py                  # both
/usr/bin/python3 -I gen_skin.py vfd-silver       # one
/usr/bin/python3 -I gen_skin.py --list
```

Outputs: `YTMinamp-VFD.wsz`, `YTMinamp-VFD-Silver.wsz` and `preview-<theme>.png` here (main, EQ,
playlist and a gen.bmp frame put together from the sprites at their real positions, focused and
unfocused, at 2x); sheets in `out/<theme>/` (ignored). Deterministic: fixed seeds and a fixed zip
date. Each .wsz is finished by `skins/genex_wacup.py`.

Options for a variant: `--title TEXT` prints TEXT in the main titlebar instead of "YTMinamp",
`--name NAME` sets the .wsz base name (the silver one adds `-Silver`; the readme title follows),
and `--out DIR` writes the .wsz files and previews to DIR (sheets in `DIR/out/`).

## Themes

Both share the VFD content: black glass (#040A0B) with teal phosphor (#3CF2D2) and dim ghosts of
every unlit segment, amber-orange (#FF8A1E) for the bar caps, lozenges, thumbs and active
indicators. 5x7 dot-matrix time digits over ghost dots; the song title and the small readouts
are teal. text.bmp is a character display's font: each cell a 4x5 block of ghost dots with the
letter lit, so the bitmap title (Options) reads as a row of character cells. The volume and balance are segment bars, the EQ
ten bands of segment columns capped in orange, the EQ graph a dotted teal zero line with an orange
curve. viscolor: teal bars with amber tops, orange peaks, ghost dots. Toggles (shuffle, repeat,
EQ ON/AUTO, PRESETS, the clutterbar letters) are translucent aqua keys with an orange LED when on.
The About spot is a rotary knob: black knurled skirt, a lit teal ring, an orange pointer.

- **VFD** (`vfd`): a black gloss faceplate in a sculpted silver surround (waisted down the sides
  of the main window and EQ, straight on the tiled playlist and gen windows), one wide VFD window,
  grey rubber transport keys, a silver eject key and seek thumb, orange lozenges for EQ and PL.
  "YTMinamp" in white bold italic, "SPECTRUM ANALYZER" print to its right.
- **VFD Silver** (`vfd-silver`): a satin silver faceplate with faint horizontal brush streaks
  (vertical-only variation), darker silver bevels down the sides, the keys on the silver and only
  the displays as recessed VFD glass; volume and balance are slots with lit segments; EQ and PL
  are rubber keys with LEDs; print in dark ink.

Playlist (both): #3CF2D2 on #040A0B, #FF8A1E current, #0E3E39 selection. Font: Arial.

## Limits

- The balance slider can't show which side it leans to and the seek bar can't show progress, as
  with every classic skin.

## Sources

- No downloaded assets or marks. Liberation Sans is the system copy, used to render the faceplate
  print into the bitmaps; it is not shipped in the .wsz.
