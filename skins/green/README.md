# YTMinamp Green: green on near-black

One classic skin from a procedural generator (`gen_skin.py`, based on `skins/ember/gen_skin.py`
and keeping its sheet layouts, which follow the app's sprite map in `ui/src/lib/skin/render/*.js`
and `crates/skin/src/*.rs`): a dark, flat, modern player with a green accent. Everything is drawn
by the script: flat panels, anti-aliased shapes, Adwaita Sans (the system copy; an Inter
derivative) for the lettering, "YTMinamp" in the main titlebar, and a 5x6 pixel font for
text.bmp. The About spot holds the app's own icon (`src-tauri/icons/icon.png`) with its red disc
recoloured green, at 16px. No third-party logos or marks. CC0 1.0 (see the skin's own
readme.txt). It needs Pillow and numpy.

```sh
/usr/bin/python3 -I gen_skin.py            # build
/usr/bin/python3 -I gen_skin.py --list     # theme names
```

Outputs: `YTMinamp-Green.wsz` and `preview-green.png` here (main, EQ, playlist and a gen.bmp
frame put together from the sprites at their real positions, focused and unfocused, at 2x);
sheets in `out/green/` (ignored). Deterministic (fixed zip timestamps, no noise). The .wsz is
finished by `skins/genex_wacup.py`.

## Theme

- **YTMinamp Green** (`green`): a #121212 body, black titlebars and player bar, #1f1f1f display
  panels, #b3b3b3 secondary text.
- Flat controls in place of bevels: rounded panels, anti-aliased white round knobs, 3px rails
  with green #2bd16a filled up to the knob (volume, EQ from the 0 dB line).
- A round white play button with a black glyph; the other transport glyphs grey, white when
  pressed.
- Shuffle and repeat are icons that turn green, with a green dot under them, when on. EQ, PL,
  ON and AUTO are green pills when on.
- The seek thumb carries the progress: a tail fading from grey into green behind the knob.
- Window titles: "YTMinamp", "Equalizer", "Queue", "NOW PLAYING".
- The analyzer runs dark green at the bottom to light green at the top.
- Playlist: #b3b3b3 on #121212, green current track, #2a2a2a selection. Font: Arial.

## Limits

- The seek bar can't show a played/unplayed split in this format (posbar.bmp is one static rail
  and a moving thumb), so the thumb carries it.

## Sources

- No downloaded assets or marks. The emblem is the app's own icon, `src-tauri/icons/icon.png`,
  recoloured. Adwaita Sans is the system copy, used to render the lettering into the bitmaps;
  it is not shipped in the .wsz.
