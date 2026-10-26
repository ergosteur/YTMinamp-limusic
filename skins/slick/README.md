# YTMinamp Slick: light and clean

One classic skin from a procedural generator (`gen_skin.py`, based on `skins/ember/gen_skin.py`
and keeping its sheet layouts, which follow the app's sprite map in `ui/src/lib/skin/render/*.js`
and `crates/skin/src/*.rs`): a light, flat, modern player with a pink-red accent. Everything is
drawn by the script: flat panels, anti-aliased shapes, Adwaita Sans (the system copy; an Inter
derivative) for the lettering, "YTMinamp" in the main titlebar, and a 5x6 pixel font for
text.bmp. The About spot holds the app's own icon (`src-tauri/icons/icon.png`) with its disc
recoloured to the accent, at 16px. No third-party logos or marks. CC0 1.0 (see the skin's own
readme.txt). It needs Pillow and numpy.

```sh
/usr/bin/python3 -I gen_skin.py            # build
/usr/bin/python3 -I gen_skin.py --list     # theme names
```

Outputs: `YTMinamp-Slick.wsz` and `preview-slick.png` here (main, EQ, playlist and a gen.bmp
frame put together from the sprites at their real positions, focused and unfocused, at 2x);
sheets in `out/slick/` (ignored). Deterministic (fixed zip timestamps, no noise). The .wsz is
finished by `skins/genex_wacup.py`.

## Theme

- **YTMinamp Slick** (`slick`): a #f5f5f7 body, titlebars in a soft #fbfbfd-to-#e8e8ed gradient
  with a hairline under them, white display cards with a #dcdce1 hairline, #1d1d1f/#6e6e73 text.
- A frosted grey player bar with a hairline behind the transport. Plain filled transport glyphs,
  double-arrow skips, pink-red #f2304f when pressed.
- Flat controls in place of bevels: anti-aliased white round knobs, 3px rails with the accent
  filled up to the knob (volume, EQ from the 0 dB line).
- Shuffle and repeat are icons on a pink-tinted pill when on; EQ, PL, ON and AUTO are accent
  pills.
- The seek thumb carries the progress: a tail fading from grey into the accent behind the knob.
- Window titles: "YTMinamp", "Equalizer", "Up Next", "ARTWORK".
- The analyzer runs deep red at the bottom to pink at the top.
- Playlist: #1d1d1f on white, #e0213f current track, #fde0e4 selection. Font: Arial.

## Limits

- The seek bar can't show a played/unplayed split in this format (posbar.bmp is one static rail
  and a moving thumb), so the thumb carries it.

## Sources

- No downloaded assets or marks. The emblem is the app's own icon, `src-tauri/icons/icon.png`,
  recoloured. Adwaita Sans is the system copy, used to render the lettering into the bitmaps;
  it is not shipped in the .wsz.
