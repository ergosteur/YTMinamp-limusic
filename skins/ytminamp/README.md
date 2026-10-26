# YTMinamp Dark and Light: the house look

Two classic skins from one procedural generator (`gen_skin.py`, based on `skins/ember/gen_skin.py`
and keeping its sheet layouts, which follow the app's sprite map in `ui/src/lib/skin/render/*.js`
and `crates/skin/src/*.rs`), a theme each: the app's own look, flat and modern, in the colours of
its icon. Its red leads (slider fills and knobs, lit toggles, the round play button), its yellow
follows (the current track on the dark theme, the analyzer's tips, the pressed glyphs, the light
theme's selection). The About spot holds the app's icon itself (`src-tauri/icons/icon.png`),
downscaled to 16px. Everything else is drawn by the script: flat panels, anti-aliased shapes,
Noto Sans (the system copy; Medium and SemiBold) for the lettering, "YTMinamp" in the main
titlebar, and a 5x6 pixel font for text.bmp. No third-party logos or marks. CC0 1.0 (see the
skin's own readme.txt). It needs Pillow and numpy.

```sh
/usr/bin/python3 -I gen_skin.py                    # both
/usr/bin/python3 -I gen_skin.py ytminamp-dark      # some (ytminamp-dark, ytminamp-light)
/usr/bin/python3 -I gen_skin.py --list             # theme names
```

Outputs: `YTMinamp-Dark.wsz`, `YTMinamp-Light.wsz` and `preview-<theme>.png` here (main, EQ,
playlist and a gen.bmp frame put together from the sprites at their real positions, focused and
unfocused, at 2x); sheets in `out/<theme>/` (ignored). Deterministic (fixed zip timestamps, no
noise). Each .wsz is finished by `skins/genex_wacup.py`.

## Themes

Both share:

- Flat controls in place of bevels: rounded panels for the displays, anti-aliased round knobs,
  3px rails with the red filled up to the knob (volume, EQ from the 0 dB line).
- A red play disc with a white glyph; the other transport glyphs plain. Shuffle and repeat are
  icons on a red-tinted pill when on.
- A "player bar" band behind the transport, with the seek rail on its top edge. The seek thumb
  carries the progress: a tail fading from grey into red behind the knob.
- Window titles: "YTMinamp", "Equalizer", "Up next", "ALBUM ART".
- The analyzer runs red at the bottom to yellow at the top (viscolor.txt).
- The displays, text.bmp's background and viscolor's background are one panel colour. The app
  draws the song title in TrueType in text.bmp's ink colour; the generator asserts that ink
  contrasts with the title box. Playlist font: Arial.

- **YTMinamp Dark** (`ytminamp-dark`): a warm near-black body (#0e0c0c), #1f1b1b panels and
  player bar, red #ee1c2c. Playlist: white text, yellow #ffc21e current track, dark red
  #3e1418 selection.
- **YTMinamp Light** (`ytminamp-light`): a white body, warm #f5f1ef panels and player bar, red
  #e3121f. Playlist: near-black text, red #c8101e current track, pale yellow #ffedb8 selection.

## Limits

- The seek bar can't show a played/unplayed split in this format (posbar.bmp is one static rail
  and a moving thumb), so the thumb carries it.

## Sources

- No downloaded assets or marks. The emblem is the app's own icon, `src-tauri/icons/icon.png`.
  Noto Sans is the system copy, used to render the lettering into the bitmaps; it is not shipped
  in the .wsz.
