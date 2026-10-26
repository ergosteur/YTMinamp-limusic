# YTMinamp Material Music: Material design, 2015

One classic skin from a procedural generator (`gen_skin.py`, based on `skins/ember/gen_skin.py`
and keeping its sheet layouts, which follow the app's sprite map in `ui/src/lib/skin/render/*.js`
and `crates/skin/src/*.rs`), in the Material design style of 2015 with a deep orange accent.
Everything is drawn by the script: anti-aliased shapes, soft card shadows, hand-made pixel fonts,
and Noto Sans (the system copy) for the window titles, "YTMinamp" in the main one, and the time
digits. The About spot holds the app's own icon (`src-tauri/icons/icon.png`) recoloured in
Material oranges: its disc runs deep orange 700 to 500 (#e64a19 to #ff5722), with the upper-left
half folded over in amber (#ff9800 blended in) like a lighter sheet of paper; the white mark and
the yellow bolt stay. No third-party logos or marks. CC0 1.0 (see the skin's own readme.txt). It
needs Pillow and numpy.

```sh
/usr/bin/python3 -I gen_skin.py            # build
/usr/bin/python3 -I gen_skin.py --list     # theme names
```

Outputs: `YTMinamp-Material-Music.wsz` and `preview-material.png` here (main, EQ, playlist and a
gen.bmp frame put together from the sprites at their real positions, focused and unfocused, at
2x); sheets in `out/material/` (ignored). Deterministic (fixed zip timestamps, no noise). The
.wsz is finished by `skins/genex_wacup.py`.

## Theme

- **YTMinamp Material Music** (`material`): a light #fafafa body with white cards and soft
  shadows (the displays, the control card along the bottom of the main window, the EQ panel).
- Title bars: deep orange #ff5722 app bars with white titles and a shadow below, #e0e0e0 with
  grey titles when unfocused. Every window, the main one included, gets the same bar.
- Play is an orange floating action button; the other transport icons are grey with a grey
  ripple when pressed.
- Shuffle and repeat are icons, orange when on; EQ/PL are tabs with an orange indicator; ON is a
  switch, AUTO a checkbox, and PRESETS and the playlist buttons are flat orange text buttons.
- Sliders are a 2px track with an orange fill and dot thumb.
- The analyzer and EQ graph run in deep oranges; text.bmp's ink is #212121.
- Playlist: #212121 on white, orange current track, #ffccbc selection. pledit.txt names Noto Sans
  (the app falls back to Arial).

## Limits

- The balance slider can't show which side it's on, so its track stays neutral. Only the centre
  mark changes: accent-coloured when centred. The seek bar has only its thumb.
- text.bmp, gen.bmp letters and small labels are pixel fonts (uppercase only).

## Sources

- No downloaded assets or marks. The emblem is the app's own icon, `src-tauri/icons/icon.png`,
  recoloured. Noto Sans is the system copy, used to render titles and digits into the bitmaps;
  it is not shipped in the .wsz.
