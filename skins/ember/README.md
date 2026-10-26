# Ember

An original classic Winamp 2.x skin, generated procedurally by `gen_skin.py`: dark graphite body,
copper trim, amber display, hand-made pixel fonts, "YTMinamp" in the main titlebar. The app ships
it (`src-tauri/ytminamp-build.rs`). Nothing is taken from another skin; no logos or
trademarks. CC0 1.0 (see the skin's own readme.txt).

    /usr/bin/python3 gen_skin.py

writes the sheets into `out/` (ignored), zips them flat into `YTMinamp-Ember.wsz`, and draws `preview.png`
(the main window, EQ, playlist and a gen.bmp frame at their real positions, 2x). Deterministic:
the grain's noise has a fixed seed. Needs Pillow and numpy (the system Python has both).

Layouts follow ytminamp's own sprite map (`ui/src/lib/skin/render/sprites.js`, `equalizer.js`,
`playlist.js`, `albumArt.js`, `crates/skin/src/genex.rs`). Each build of the app copies it into
the skins folder (`~/.local/share/com.ytminamp.desktop/skins/` on Linux).
