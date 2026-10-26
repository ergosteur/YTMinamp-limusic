# Breeze: light and dark

Two classic skins from one procedural generator (`gen_skin.py`, based on `skins/ember/gen_skin.py`
and keeping its sheet layouts, which follow the app's sprite map in `ui/src/lib/skin/render/*.js`
and `crates/skin/src/*.rs`), a theme each, in the style of the Breeze desktop theme. Everything is
drawn by the script, with the time digits, labels and titles in hand-made pixel fonts (a
mixed-case UI font, 5px capitals for text.bmp and gen.bmp) and "YTMinamp" in the main titlebar.
The About spot holds the app's own icon (`src-tauri/icons/icon.png`), downscaled to 16px. No
third-party logos or marks. CC0 1.0 (see the skin's own readme.txt). It needs Pillow and numpy.

```sh
/usr/bin/python3 -I gen_skin.py                     # both
/usr/bin/python3 -I gen_skin.py breeze-dark         # some (breeze-light, breeze-dark)
/usr/bin/python3 -I gen_skin.py --accent=#e93d58    # another accent colour
/usr/bin/python3 -I gen_skin.py --list              # theme names
```

Outputs: `YTMinamp-Breeze-Light.wsz`, `YTMinamp-Breeze-Dark.wsz` and `preview-<theme>.png` here
(main, EQ, playlist and a gen.bmp frame put together from the sprites at their real positions,
focused and unfocused, at 2x); sheets in `out/<theme>/` (ignored). Deterministic (fixed zip
timestamps, no noise). Each .wsz is finished by `skins/genex_wacup.py`.

## Themes

Both share the Breeze widget style:

- Colours from the Breeze Light and Breeze Dark colour schemes: Window, Button, View and Header
  backgrounds, Normal/Inactive text, Link, Negative. Frames and outlines are the window colour
  mixed 20-30% towards the text, as Breeze draws them.
- Accent: Breeze blue #3daee9, or `--accent`.
- Titlebars use the Header colour, title centred, plain glyph buttons (menu, minimise chevron,
  shade chevron, close); pressed shows a round backdrop, the close button's red #da4453 with a
  white cross.
- Buttons: flat, 1px rounded outline, accent outline and tint when pressed or checked (shuffle,
  repeat, EQ, PL). Shuffle/repeat are icons. EQ On/Auto are check boxes.
- Sliders: thin groove, accent fill (volume, EQ), round outlined handles.
- Displays and the playlist use the View colours. pledit.txt names Noto Sans for the title and
  playlist.

- **Breeze Light** (`breeze-light`): Playlist: View text on the View background, Link-coloured
  current track, #B5E0F7 selection (the accent mixed into the View background).
- **Breeze Dark** (`breeze-dark`): Playlist: View text on the View background, accent-coloured
  current track, #255670 selection.

## Limits

- The seek bar has no fill: posbar.bmp can't show progress.

## Sources

- Breeze's design and colour schemes (LGPL), used as reference for the colours and widget
  shapes; no artwork is copied.
- The emblem is the app's own icon, `src-tauri/icons/icon.png`.
