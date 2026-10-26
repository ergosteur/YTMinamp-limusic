# YTMinamp Classic: the grey 3D desktop look

One classic skin from a procedural generator (`gen_skin.py`, keeping the sheet layouts of
`skins/ember/gen_skin.py`, which follow the app's sprite map in `ui/src/lib/skin/render/*.js` and
`crates/skin/src/*.rs`), in the generic grey 3D desktop style of the late 1990s. Everything is
drawn by the script, with hand-made fonts: a bold caption face (titles, "YTMinamp" in the main
titlebar, and gen.bmp's A-Z), a small UI face for labels, a 4x5 face for text.bmp. The
title-bar icon (the options button) is a small compact disc of its own; the About spot holds the
app's own icon (`src-tauri/icons/icon.png`), downscaled to 16px with a hard edge, the way icons
of the era sat on the face. No third-party logos or marks. CC0 1.0 (see the skin's own
readme.txt). It needs Pillow and numpy.

```sh
/usr/bin/python3 -I gen_skin.py            # build
/usr/bin/python3 -I gen_skin.py --list     # theme names
```

Outputs: `YTMinamp-Classic.wsz` and `preview-classic.png` here (each window active on the left,
inactive and pressed states on the right, 2x, on a teal backdrop); sheets in `out/classic/`
(ignored). Deterministic (fixed zip timestamps, no noise). The .wsz is finished by
`skins/genex_wacup.py`.

## Theme

- **YTMinamp Classic** (`classic`): face #c0c0c0, 3D light #dfdfdf, highlight #ffffff, shadow
  #808080, dark shadow #000000.
- Bevels in the classic DrawEdge order: window frames light-then-white outside-in; push buttons
  white outermost; pressed buttons a black outline round a grey one with the glyph 1px
  down-right; latched toggles (shuffle, repeat, EQ, PL, clutterbar letters) sunken with a white
  dither.
- Title bars: navy #000080 to blue #1084d0 when active, #808080 to #c0c0c0 inactive, with #c0c0c0
  text. Playlist and album-art title bars are solid (their tiles repeat, so no gradient); main
  and EQ get the gradient.
- The marquee title is drawn by the app in pledit.txt's font and Normal colour, so the title box
  and the kbps/kHz/mono/stereo row are white edit fields with black text; the time and analyzer
  sit in a black, CD-player style LED panel (green seven-segment digits).
- Trackbars: a 4px sunken groove, pointed raised thumbs (dithered while dragged), tick marks.
  The thumbs cover the groove completely, so their sprites need no groove behind them; the seek
  bar's 29px sprite paints the open groove either side of its 11px pointer, with the groove's
  ends drawn in main.bmp.
- EQ ON/AUTO are check boxes; PRESETS a push button; the graph a black LED readout.
- Playlist: black on white, navy #000080 current track, #c0c0e0 selection. Font: `Font=Arial`
  (the field takes one name; the app appends Arial anyway).

## Limits

- The playlist's scrollbar track is a flat white/face blend: a 1px dither can't tile across the
  29px side tiles.

## Sources

- No downloaded assets or marks. The emblem is the app's own icon, `src-tauri/icons/icon.png`.
