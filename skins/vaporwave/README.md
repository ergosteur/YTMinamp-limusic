# Vaporwave: sunset, grid and marble

One classic skin from a procedural generator (`gen_skin.py`, based on `skins/frutiger-aero/gen_skin.py`
and through it on `skins/ember/gen_skin.py`, keeping their sheet layouts, which follow the app's
sprite map in `ui/src/lib/skin/render/*.js` and `crates/skin/src/*.rs`). It is generic: no
product's logos or marks, and nothing in it comes from another skin. Everything is drawn by the
script: gradients, anti-aliased shapes (the sun, the palms, the bust, the grid) and hand-made
pixel fonts, including a 7px one for the spaced-out titles. No system fonts are rasterised. CC0
1.0 (see the skin's own readme.txt). It needs Pillow and numpy.

```sh
/usr/bin/python3 -I gen_skin.py
/usr/bin/python3 -I gen_skin.py --title TEXT --name NAME --out DIR
/usr/bin/python3 -I gen_skin.py --list
```

Outputs: `YTMinamp-Vaporwave.wsz` and `preview.png` here (main, EQ, playlist and a gen.bmp frame
put together from the sprites at their real positions, focused and unfocused, at 2x); sheets in
`out/` (ignored). `--title` replaces "YTMinamp" in the main titlebar (full-width letters are
folded to ASCII and drawn spaced out like the default), `--name` the .wsz's base name (the
readme's title follows it), `--out` the folder for the .wsz, the preview and `out/`.
Deterministic: no randomness, and the zip entries have a fixed date. Each .wsz is finished by
`skins/genex_wacup.py`.

## Themes

- **Vaporwave** (one theme):
  - Main window: a sky running from pink (#FF80D6) through purple (#BA6AF6) to pale cyan at the
    horizon, a striped retro sun (yellow to magenta, cut by gaps that widen toward the horizon)
    setting between two palm silhouettes, and a neon wireframe floor (magenta rungs, cyan rails
    converging on the middle). A marble bust in profile, on a small plinth, stands in the About
    spot at the bottom right.
  - Chrome: magenta, with hard two-pixel 90s bevels (light top and left, dark bottom and right).
    Buttons have a "chrome horizon" face, light above a hard break and deeper below. Titlebars
    are a vertical magenta gradient with two neon racing lines (cyan over pink) either side of
    a spaced-out title; grey-lilac when the window is unfocused.
  - Titles: a 7px pixel font set full width, white with a cyan ghost one pixel to the left and a
    dark drop: "YTMinamp", "EQUALIZER", "PLAYLIST"; gen.bmp's letters use the same treatment
    with a pixel of air either side.
  - Transport: raised chrome keys with dark glyphs split into a cyan and a magenta ghost.
  - Toggles (shuffle, repeat, EQ, PL, EQ ON/AUTO, clutterbar letters): pink chrome, cyan chrome
    when on.
  - Sliders: thin sunken grooves lit from cyan to pink, with raised chrome thumbs (cyan while
    dragged). The volume and balance grooves sit over the sky, so the frames are cut from it.
  - Displays: dark purple glass (#1A0834) in a sunken bevel. Time digits are pink seven-segment
    with a cyan ghost; text.bmp is cyan with a dim magenta fringe, so the app's TrueType song
    title (drawn in text.bmp's ink colour) is cyan.
  - EQ: the same sky and grid with a palm at each side, the sliders in a dark glass bay with
    faint +12/0/-12 dB lines.
  - viscolor: cyan at the bottom through purple and pink to pale yellow at the top.
  - Playlist: #FFA6E8 on #160630, #70F2FF current, #4E2484 selection. Font: Arial. The frame
    is the magenta chrome with a cyan rim round the list; the album art frame has a 4px dark mat.

## Limits

- The sun and palms show only where the controls leave the sky free, under the left display
  and either side of the seek bar; the seek groove crosses the sun.
- The playlist and gen frames tile, so they carry the chrome but not the scene.

## Sources

- No downloaded assets, marks or fonts.
