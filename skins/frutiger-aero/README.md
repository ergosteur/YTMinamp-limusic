# Frutiger Aero: the glossy 2004-2012 look

One classic skin from a procedural generator (`gen_skin.py`, based on `skins/ember/gen_skin.py`
and keeping its sheet layouts, which follow the app's sprite map in `ui/src/lib/skin/render/*.js`
and `crates/skin/src/*.rs`). It is generic: no product's logos or marks, and nothing in it comes
from another skin. Everything is drawn by the script: gradients, bokeh, glass and gloss, hand-made
pixel fonts, and Open Sans Semibold (`/usr/share/fonts/open-sans`, falling back to Noto Sans or
DejaVu) for the window titles, "YTMinamp" in the main one. The app ships it, as it does Ember
(`src-tauri/ytminamp-build.rs`). CC0 1.0 (see the skin's own readme.txt). It needs Pillow and numpy.

```sh
/usr/bin/python3 -I gen_skin.py
```

Outputs: `YTMinamp-Frutiger-Aero.wsz` and `preview.png` here (main, EQ, playlist and a gen.bmp frame put
together from the sprites at their real positions, focused and unfocused, at 2x); sheets in
`out/` (ignored). Deterministic: bokeh positions come from a seeded RNG and the zip entries have a
fixed date. Each .wsz is finished by `skins/genex_wacup.py`.

## Themes

- **Frutiger Aero** (one theme, 2004-2012 aesthetic):
  - Body: a sky-to-aqua gradient with soft bokeh bubbles, a grassy two-layer hill along the
    bottom, and a low sun with a lens flare. Frosted glass panels with a white top gloss sit over
    it.
  - Titlebars: Aero-style glass with a hard gloss line at half height, grey when the window is
    unfocused. The titlebar buttons are small glossy orbs; the close button is red.
  - Transport: glossy aqua orbs with white glyphs. Play is a bigger orb (22px) that runs 2px above
    and below its 18px cell. Its pressed state darkens only the middle, so the rim outside the cell
    (which main.bmp holds) still matches.
  - Sliders: glass tubes filled with liquid that runs from green to aqua, with glossy bubble
    thumbs. A thumb's cell is drawn over the tube's cross-section (liquid to its left, clear glass
    to its right), so its corners blend in as it moves.
  - Displays: dark aqua glass with white/cyan text and a gloss band above the content rows.
    text.bmp's space cell is the plain display colour.
  - Toggles (shuffle, repeat, EQ, PL, EQ ON/AUTO, clutterbar letters): frosted glass pills that
    turn green when on.
  - viscolor: green at the bottom through aqua to white at the top; white peaks.
  - Playlist: a light, airy list with dark slate text, an aqua current track and an aqua
    selection. The Media Library palette (genex) is light to match. Font: Arial.

## Limits

- None noted.

## Sources

- No downloaded assets or marks. Open Sans is the system copy (`/usr/share/fonts/open-sans`),
  used to render the window titles into the bitmaps; it is not shipped in the .wsz.
