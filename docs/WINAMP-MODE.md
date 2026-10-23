# Winamp skin mode

ytminamp is Limusic plus one feature: a window that plays through Limusic's own playback stack
but looks and behaves like classic Winamp 2.x, drawn from a real `.wsz` skin file.

It follows the same pattern as Limusic's mini player (`src-tauri/src/mini.rs`): a second window
that loads the same SPA, which branches on the window label. There is no second copy of playback
state — the Winamp window reads the same `playback` store and calls the same commands as the rest
of the app. Opening it hides the main window; ✕ in the skin's titlebar (or a WM close) brings it
back through `tray::show_main`, the same path the mini player uses.

## Where things live

| Piece | Path |
|---|---|
| `.wsz` parser (zip, BMP incl. RLE8/RLE4, `region.txt`, `viscolor.txt`, `pledit.txt`) | `crates/skin` |
| Check a folder of skins: `cargo run -p skin --example check_skins -- <dir>` | `crates/skin/examples` |
| Window open/close/resize, skins folder, remembered skin | `src-tauri/src/winamp.rs` |
| Tauri commands (`open_winamp`, `close_winamp`, `resize_winamp`, `*_wsz_skin(s)`, `open_skins_dir`) | `src-tauri/src/commands.rs` |
| Svelte host component (window label `winamp`) | `ui/src/lib/components/WinampSkin.svelte` |
| Canvas renderer, sprite tables, hit-testing | `ui/src/lib/skin/` |
| Right-click / options-button menu, laid out like WACUP's | `ui/src/lib/skin/menu.js` |
| Keyboard shortcuts | `ui/src/lib/skin/keys.js` |
| Remembered UI state | `ui/src/lib/skin/prefs.js` |
| Docked panel layout (search, album art, playlist) and hit-testing | `ui/src/lib/skin/layout.js` |
| Analyzer audio capture + FFT | `src-tauri/src/viz.rs` |
| Titlebar button | `ui/src/lib/components/Titlebar.svelte` |
| Test skins | `fixtures/skins/` |

Sprite coordinates in `ui/src/lib/skin/render/sprites.js` come from
[Webamp](https://github.com/captbaritone/webamp)'s `skinSprites.ts` / CSS (MIT) — numeric layout
facts, not copied code.

## Touch points in upstream files

Kept small so upstream merges stay easy. If a merge conflicts, these are the places:

- `src-tauri/src/lib.rs` — `mod winamp`, command registration, the `only_ui` window allowlist, and
  the close-request handler (`mini::LABEL | winamp::LABEL`).
- `src-tauri/src/tray.rs` — `show_main` also closes the Winamp window.
- `crates/player/src/lib.rs` — `Player::audio_info` (kbps/kHz/channels for the display),
  `set_extra_af` / `af_command` / `af_metadata` (the EQ and analyzer filters), `set_keep_open`
  (Stop after current).
- `src-tauri/src/lastfm.rs` — `unappimage` made `pub(crate)` so opening the skins folder can use it.
- `src-tauri/capabilities/default.json` — `winamp` in the window list (without it the window
  can't listen to events and nothing updates).
- `src-tauri/tauri.conf.json` — product name/identifier, and **updater endpoints emptied** so
  this fork can never self-update to vanilla Limusic; `tauri.macos.conf.json` repeats the title.
- `ui/src/lib/updater.svelte.ts` — `look()` is ours (`skin/updates.js`: YTMinamp's own GitHub
  releases, download link only); `SettingsDialog.svelte` hides the beta channel.
- `ui/src/lib/components/Titlebar.svelte`, `SettingsDialog.svelte` — the name and full version from
  `skin/brand.js`; the Winamp-mode button with the app icon.
- `ui/src/routes/+layout.svelte` — the `isWinamp` branch.
- `ui/src/lib/api.ts`, `ui/src/lib/player.svelte.ts` — command wrappers.

## Spectrum analyzer

libmpv hands out no samples, but its audio runs through ffmpeg's filter graph, and a filter's
measurements come back as frame metadata (mpv's `af-metadata/<label>` property). So the first
time the Winamp window opens, `src-tauri/src/viz.rs` appends a labelled filter, `@viz`, to the end
of the player's chain (`Player::set_extra_af` in `crates/player`), after the EQ (see
[Equalizer](#equalizer)), and leaves it there for the session; it's read only while the Winamp
window is open:

```
aformat=stereo, asplit → [music] + [mono copy] → asplit into 19 → bandpass per bar
→ amerge(music, 19 bands) → astats (RMS per channel, per frame) → pan back to the music's two channels
```

What you hear passes through untouched; the band levels ride along as metadata, read about 60
times a second (mpv runs the graph as its audio output asks for more: about 60 Hz on PipeWire,
47 on PulseAudio). It's the same on Linux, Windows and macOS, and it shows only this app's audio.
It costs roughly 7% of one core, mostly `astats` measuring 21 channels, from the first time the
Winamp window opens until the app quits.

The 19 bands sit on the 19 bars Winamp draws (75 columns in fours, with Webamp's mostly-logarithmic
column mapping: 69 Hz to 20 kHz), and each band's level is scaled to what Winamp's own FFT
(Nullsoft vis_classic, via Webamp's port) shows for it. The factors were measured with pink
noise against a port of that FFT, and agree within a few percent on white noise. mpv filters
ahead of its output buffer, so the levels are held back 0.2 s to line up with what you hear.
Falloff and peak hold run per frame in `ui/src/lib/skin/render/visualizer.js`, coloured from the
skin's `viscolor.txt` (stock Winamp palette for missing slots). Click the analyzer to turn it
off/on.

If mpv refuses the filter (a libmpv whose ffmpeg lacks one of them), no levels arrive and the
analyzer plays test patterns while music plays rather than sitting empty: sweeps at different
speeds, a travelling wave, random bars, a staircase, a pulse, a new one every six seconds
(`ui/src/lib/skin/testPattern.js`).

Limits: 19 bands, not a full FFT (exactly what the classic analyzer shows, but no oscilloscope
mode, which needs the waveform).

## MilkDrop (Butterchurn)

Main menu ▸ Visualisation ▸ MilkDrop window, or Ctrl+Shift+K (Winamp's start/stop visualization
plug-in key), opens `MilkdropWindow.svelte` in a window of its own (`winamp-milkdrop`):
[Butterchurn](https://github.com/jberg/butterchurn), the WebGL port of MilkDrop Webamp uses,
playing the [butterchurn-presets](https://github.com/jberg/butterchurn-presets) pack, both MIT and
loaded only when the window opens. mpv plays outside the webview, so there's no WebAudio to
analyse, nor any samples from mpv: `viz.rs` makes a waveform from the 19 band levels (a tone per
band at its level, phases carried on between frames) and sends it as `winamp-wave` (1024 bytes,
silence at 128, only while the window is open). Butterchurn's `render()` takes it directly (no
AudioContext at all), and its bass/mid/treble, which most presets react to, follow the music.
Only the shape of the wave drawn is made up. With no levels at all, the window makes up its own
signal while music plays.

It sits in the skin's generic frame, titled MILKDROP; fullscreen drops the frame. Presets
change automatically with a blend, every 20 seconds unless the right-click menu says otherwise
(off, 10 s to 5 min). N / P next and previous, L the preset browser (MilkDrop's own key: a
filterable list over the picture in the skin's playlist colours; click or Enter picks, Esc
(wherever the focus is) closes it; L types in its filter box), F or a double-click fullscreen, Esc leaves it. Drag to move, the frame's corner to resize
(remembered). Two on-screen texts, each shown on change (for five seconds), always, or never from
the right-click menu: the preset's name (bottom left) and the track's artist, title and time
(top left, on every track change). **Album art overlay** draws the playing track's cover over the
picture, fitted whole and 35% opaque (clicks go through it). The other Winamp keys work here too;
all the settings are remembered.

## Playlist editor

The PL button docks Winamp's playlist editor under the main window (the window grows by 232 px),
drawn from `pledit.bmp` with `pledit.txt`'s colours and font, showing Limusic's real queue.
Double-click plays a track, the wheel or scrollbar handle scrolls, the bottom-right mini
transport works, ✕ undocks it. Code: `ui/src/lib/skin/render/playlist.js`.

### Playlist buttons

One short menu each, kept to what Limusic's queue can do (`ui/src/lib/skin/playlistActions.js`):

| Button | Does |
|---|---|
| ADD | **Search YouTube Music** (opens search; if it's open, focuses its box and flashes it), **Browse library…** (Limusic's Library page in the full window, Winamp mode staying open: `navigate.js`), or **Open YouTube URL…**: a small dialog (`OpenUrlWindow.svelte`; Enter or OK) that takes any link Limusic's `parseYtLink` reads (youtu.be, youtube.com, music.youtube.com) and plays it: a song now, a playlist or album in place of the queue, an artist's radio |
| REM | Remove the selected track, or clear the queue |
| SEL | Select all, none, or invert the selection, as in Winamp (Ctrl/Shift+click selects several) |
| MISC | Sort what plays next by title or artist, or reverse it |
| LIST | **Load ▸** a playlist (local and YouTube Music sections; replaces the queue), or **Save ▸** the queue as one, in the YouTube Music library (signed in) or only on this machine. Some skins label it LOAD LIST |

LIST and the main menu's Play ▸ never wait on YouTube Music: they show the playlists as last
fetched and refresh them behind the menu for next time (`libraryPlaylists` in
`playlistActions.js`). The Winamp window fetches them when it opens; until that comes back, a menu
shows the local playlists (SQLite, instant) and `[Retrieving playlists]` under YouTube Music.

Only upcoming tracks can be removed or moved: the playing row and the history stay put, the
same rule as Limusic's queue panel. A saved queue is named for when it was saved.

## Search (eject)

Eject toggles a search panel, like the PL button toggles the playlist. It docks directly under the main window (above the playlist when both are
open), drawn with the playlist editor's chrome. The text box is a real HTML `<input>` laid over
the canvas, so typing, paste and IME input work. Enter searches YouTube Music songs; arrows pick
a result; Enter (or double-click) plays it now, with YouTube Music's radio after it, like a click
in Limusic; Shift+Enter adds it to the queue; right-click a result for Play / Play next / Add to
queue; Esc closes the panel.

**What it searches for** is the **Songs ▾** button at the right end of the box
(`searchKinds.js`, remembered as `searchKind`): Songs, Videos, Albums, Artists, Playlists, or All
(Limusic's own searches: `search`, `searchVideos`, `searchCards`, `searchAll`). All comes in
sections (Top result, Songs, Albums, Artists, Playlists) under header rows that can't be picked.
Albums, artists and playlists read "Title — details"; double-click (or Play) does what a click
does in Limusic, short of opening a page: an album or playlist replaces the queue, an artist starts
its radio. Play next and Add to queue take an album's or playlist's tracks; artists can't be
queued. Ratings, the library and playlists take only the song rows; File info shows any row, with
its own YouTube Music link.

Its bottom bar counts the results ("20 RESULTS"). Its buttons, after the playlist's:

| Button | Does |
|---|---|
| ADD | Play / Play next / Add to queue for the selected results, as the right-click menu does |
| REM | Clear results, Clear search box |
| SEL | Select all / none / Invert selection |
| MISC | Sort the results by title, artist or length, or reverse them |
| LIST | Recent searches (the last ten, remembered as `searchHistory`): pick one to run it again |

### Selecting rows, the mini time

The playlist and search lists select the way OS lists do (`ui/src/lib/skin/selection.js`): a
click picks a row, Ctrl+click toggles one, Shift+click selects the range from the last click,
Ctrl+Shift+click adds that range. Delete removes every selected track still to come; the search
menus act on every selected result (played first then the rest next, or queued in order).

Both panels show the playing time in the small box beside their mini transport buttons, in the
skin's text font (Webamp's MiniTime: elapsed, or remaining with a minus). Unlike Winamp's it
doesn't blink while paused, since the main window's clock here doesn't either. Click it to
switch, as with the main window's clock.

## Context menus

Modelled on real Winamp's (WACUP's) menus, in their order and wording, keeping what applies:

| Right-click | Menu |
|---|---|
| A playlist row | Play; Remove selected (Delete), Crop to selected (Ctrl+Delete); View file info... (Alt+3); Rate items ▸ |
| A search result | Play, Play next, Add to queue; View file info... (Alt+3); Rate items ▸ |
| The song title | View file info... (Alt+3 or double-click), Lyrics; Jump to file... (J, our search); Autoscroll songname; Rating ▸ |
| The analyzer | Start/Stop plug-in (Ctrl+Shift+K, MilkDrop); Run the plug-in on start-up; the plug-in list (MilkDrop); Spectrum analyser / Off |
| The Stop button | Stop (V), Stop w/ fadeout (Shift+V), Stop after current (Ctrl+V; Ctrl+click Stop does it too) |
| File info | Bigger text, Smaller text, Normal size; Copy link, Open in browser |
| The album art | View file info... (Alt+3); Show full-size artwork (the biggest YouTube serves, in the browser); Show album name (a strip under the picture, any script, remembered as `artCaption`, in every window); Placement ▸; Copy link, Open in YouTube Music |
| Anywhere else | The main menu: About; Play ▸; View file info... (the playing track); Media Library (Limusic's window, shown or hidden), the panels; Options ▸, Playback ▸, Visualisation ▸, Skins ▸, Window Settings ▸; Back to Limusic, Exit |

Hovering a song title (a playlist or search row, or the main window's title) shows it in full:
title, then artist, album and length, a line each.

A right-click inside a selection acts on all of it; outside, it selects that row first. Rate
items ▸ (Rating ▸ on the title) holds Like / Dislike / No rating, Add to (or Remove from) library,
and Add to existing playlist ▸, all Limusic's own (`setRating`, `toggleSongLibrary`,
`addSongsToPlaylists`), so they show in Limusic too. The library move needs the token YouTube
sends with a row, so it's greyed out for rows without one; On Repeat and Liked Music aren't
offered as playlists to add to. The Winamp
logo at the bottom right opens About.

**File info** (`FileInfoWindow.svelte`, window `winamp-fileinfo`): the cover, title, artist,
album, release (Album, EP or Single, and the year), track number ("3 of 12"), length, play count,
who added or queued it, and the video ID, with Copy link and Open in browser. A song also gets a
like heart (Limusic's `toggleRating`, no dislike here) and its library state with Add to / Remove
from library (Limusic's `toggleSongLibrary`), when YouTube sent the token for it with the row or
the song's album page row. It leaves that out for a song already in one of your playlists (its
own apps show no "Save to library" then either), so without one File info shows nothing; its artist and
album open their pages in Limusic's window. A song with a
linked album gets those from the album's page (fetched once per album); a music video has no
album, so it shows what its row carries. Its right-click menu (Bigger text, Smaller text, Normal
size), Ctrl+= / Ctrl+- / Ctrl+0, Ctrl+wheel or a pinch zoom the text, the window growing with it
(remembered as `fileInfoZoom`). Pinches arrive as Safari's gesture events on macOS and as
Ctrl+wheel on Windows (`pixels.js` `onPinch`); lyrics take them too. The track reaches the window
through localStorage (`showFileInfo` in `skinApi.js`), which every window shares, so an open File
info window follows the next one shown.

**Stop after current** (Playback ▸, the Stop button's right-click menu, Ctrl+click on Stop, or
Ctrl+V) pauses at the end of the playing track instead of going on: mpv's `keep-open=always`
(`winamp::stop_after_current`), so nothing of the next track is heard; crossfade is suspended
while it's set. It's spent once it fires ("Stopped after current" in the title), and Play then goes
on to the next track. **Stop w/ fadeout** (Shift+V) brings the volume down over a second and a
half, stops, and puts the volume back.

## Clutterbar, double size, always on top

The main menu's **Always start in Winamp mode** (winamp.json's `startInWinamp`) opens the app in
Winamp mode instead of the full window: Rust's `show_main`, which the page calls once to reveal
the hidden main window at launch, opens the Winamp window instead. "Start minimized to tray"
still wins.

The O A I D V strip left of the time display (sprites from `titlebar.bmp`): **O** opens the main
menu, **A** keeps every Winamp window above others (`winamp::set_always_on_top`, new windows too),
**I** shows album art, **D** is double size, **V** turns the analyzer on or off. Letters light
while their thing is on. Double size zooms the Winamp window's webview to 2x on top of the DPI fix
(`pixels.js`), so every coordinate inside stays the same and the canvas is drawn with
`image-rendering: pixelated`; menus open at the click by multiplying it by the zoom. The floating
windows follow it (all but MilkDrop's, which has no pixel art to double): the Winamp window
publishes it in localStorage and an event (`announceDoubleSize`), and each window zooms itself and
asks for twice its size (`followDoubleSize`, `doubleFactor`).

## Keyboard shortcuts

`keys.js`, in every Winamp window, never while typing in a text box, and only keys Limusic's own
shortcuts (which run in these windows too) leave free: its Ctrl+D/F/S/R/M/Q, Ctrl+, Ctrl+. and
Space keep their meaning.

| Keys | |
|---|---|
| Z X C V B | Previous, Play, Pause, Stop, Next |
| Shift+V, Ctrl+V | Stop with fadeout, Stop after current |
| ← → | Back / forward 5 seconds (held: keeps going) |
| ↑ ↓ | Volume |
| S, R | Shuffle, repeat |
| J or Ctrl+J, Ctrl+L | Search (opens the panel and puts the cursor in its box), Open YouTube URL |
| Alt+E, Alt+G, Alt+A, Alt+Y, Alt+K | Playlist editor, equalizer, album art, lyrics, search panel (show/hide) |
| Alt+L | Media Library (Limusic window): shows Limusic's own window where it was, or hides it again (Winamp mode stays open) |
| Ctrl+A, Ctrl+2, Ctrl+T | Always on top, double size (Winamp's Ctrl+D is Limusic's previous track), time remaining |
| Delete, Ctrl+Delete, Enter | Remove the selected playlist tracks, crop to them (remove every other upcoming one), play the selected one |
| Alt+3 | File info: the selected row when the playlist or search panel is the active window, otherwise what's playing |
| Ctrl+= (or +, numpad +), Ctrl+-, Ctrl+0 | Lyrics text bigger, smaller, back to normal (while they're showing); the same keys Limusic zooms its own window with |
| Ctrl+Shift+K | MilkDrop window |

A floating panel forwards them to the Winamp window (`winamp-key`), bar Delete/Enter on its own
playlist.

## Equalizer

`render/equalizer.js`: Winamp's EQ window from `eqmain.bmp`, docked under the main window (or
floating), with ON/AUTO, the preamp and ten bands, the response curve (a natural cubic spline,
coloured from the skin's colour strip), and PRESETS with Winamp's built-in presets. It's real:
`src-tauri/src/viz.rs` puts an `@eq` filter into mpv's chain (a `volume` preamp, then a
one-octave `equalizer` per band at Winamp's 60 Hz-16 kHz, ±12 dB), and every slider move retunes
it live through mpv's `af-command` (`Player::af_command`), so nothing rebuilds and nothing clicks.
OFF flattens it. AUTO (loading a preset per track) is remembered but not acted on.

PRESETS lists your own presets first (click to load), then Winamp's built-in ones in a submenu,
**Save current as preset...** (a small naming dialog in the skin's frame, `EqPresetWindow.svelte`,
window `winamp-eqsave`; an existing name is replaced), **Delete preset** and **Reset (flat)**.
Your presets are kept in `winamp.json` as `eqPresets` (name, preamp and ten bands, 0-100 like
the sliders). The dialog writes them straight away (`flushPrefs`) rather than in the usual
batch, since it closes at once.

The EQ and the analyzer's filter go in the first time the Winamp window opens and stay until the
app quits, so the EQ goes on sounding the same in the full Limusic window, and switching back
and forth never rebuilds the chain. After a restart a saved EQ applies from the first time the
Winamp window opens. A crossfade's second deck copies the chain as first built, so the EQ is sent
again twice a second to put it right.

## Lyrics

`render/lyrics.js` + `lyrics.js`: the playing track's lyrics (Limusic's `getLyrics`, the same
request its own lyrics view makes) in the generic frame titled LYRICS, in the playlist font and
colours. Timed lyrics light the sung line and keep it centred; the wheel scrolls by hand until the
next track. Docked, lyrics sit to the right of the whole stack, as tall as the classic main + EQ +
playlist (464 px) or the stack if taller, 275 px wide until dragged wider or narrower from their
right edge (150–1200 px); album art can't take the right side then. Or floating, resizable.
Ctrl+wheel over them (or the keys above) sizes the text, 75–300%, in every window at once
(`zoomLyrics` in `skinApi.js`, broadcast as `winamp-lyrics-zoom`). The width and text size are
remembered. Each line's romanization and translation (Limusic's, from `romanize.rs` and the
lyrics providers) show under it, smaller, when switched on from the panel's right-click menu.
Those are Limusic's own two switches (the same localStorage keys as `LyricsView.svelte`): on in
one place is on in both. Translations start on and romanization off, as in Limusic.

When the lyrics found are the wrong ones, the panel's footer has Limusic's own source picker
(`LyricsSourcePicker.svelte` in `WinampLyricsFooter.svelte`, laid over a strip
`render/lyrics.js` keeps at the bottom): "Lyrics from ..." opens every provider's answer side by
side, to pin one, nudge the timing, or search with a corrected title. In a small floating lyrics
window its popover can be cut off by the window's edge, so the right-click menu has the same in
native form: **Lyrics source ▸** (Automatic, or one provider: `chooseLyricsSource`) and
**Timing ▸** (a quarter second earlier or later, or reset: `setLyricsOffset`). Both are kept per
song by Limusic, so they apply in its own lyrics view too.

## Remembered state

`winamp.json`'s `ui` object (`prefs.js`, `winamp::merge_ui_prefs`): where each panel is, the EQ,
double size, always on top, the time display, the analyzer, each floating window's size. Each
window saves the keys it changes and Rust merges per key.

## Album art

The clutterbar's **I**, Alt+A, or right-click → **Album Art** shows the playing track's cover: hidden, left or right of the
player (at its height), below the stack (at its width), or in a floating window (the default). Winamp
5's Album Art window is drawn with the generic window frame (`gen.bmp`); most older skins don't
have one, so they get the playlist editor's frame instead (`pledit.bmp`: its top bar with the
window's own title in place of the playlist's, its side tiles without the scrollbar groove, and
only the plain bottom edge, none of its buttons). Either way it's titled ALBUM ART (just ART when
it's too narrow). The other generic windows (lyrics, MilkDrop, Open URL, File info, EQ preset)
use the same frame. A skin that's missing other sheets (`cbuttons.bmp`, `numbers.bmp`, ...) gets
the base skin's, as in Winamp. The cover is always square:
video thumbnails (16:9) are cropped to a centred square. Double-clicking docked art moves it on
(right → below → left); dragging it moves the window. Docked left, the main window and the stack
shift right inside the window: on Wayland an app can't move its own window, so the player itself
jumps right on screen. Code: `ui/src/lib/skin/render/albumArt.js`, `ui/src/lib/skin/art.js`.

## Titlebars

Like Winamp, the active window's titlebar is lit and the rest are dimmed: main window
(`titlebar.bmp` y 0 / 15), playlist editor and search (`pledit.bmp` y 0 / 21), equalizer
(`eqmain.bmp` y 134 / 149), generic frames (`gen.bmp` y 0 / 21). Several of Winamp's windows
share the one Winamp window here, so the active one is the one last clicked; a floating panel's
is lit while its window has focus, and nothing is lit while the app isn't focused
(`ui/src/lib/skin/focus.js`).

Generic frames (album art, lyrics, MilkDrop, Open URL) carry their title in `gen.bmp`'s own
alphabet, A-Z in a lit row (y 88) and a dim one (y 96), each letter its own width, separated by
1 px columns of the colour at x 0: measured per skin, as Webamp does. The title sits on the
titlebar's centre fill between its end caps. A `gen.bmp` without those letters, or a skin with no
`gen.bmp` (the playlist editor's frame then), falls back to `text.bmp`'s letters.

## Floating panels

Album art, the playlist editor and search can each float in a window of their own
(`winamp-art`, `winamp-playlist`, `winamp-search`; `winamp::open_panel`), from the right-click
menu or by double-clicking a docked panel's titlebar. A floating panel's titlebar double-click
docks it back; its ✕ hides it. Drag the bottom-right corner to resize: the playlist and search
in Winamp's 25×29 px steps (from 275×116), album art keeping its picture square. The Winamp
window owns where each panel lives; floating windows ask it to dock, hide or toggle panels
through `winamp-panel-dock` / `winamp-panel-toggle` events, and Rust tells it when one closes
(`winamp-panel-closed`, Alt+F4 included). No snapping yet, and on Wayland the compositor decides
where a floating window opens. Search results don't carry over between docked and floating.
Code: `ui/src/lib/components/AlbumArtWindow.svelte`, `FloatingListPanel.svelte`.

## Name and icon

People see **YTMinamp (limusic)**: tray, window titles, media controls, notifications, the About
box and the desktop entry (`packaging/linux/ytminamp.desktop`, a Tauri desktop template). One
constant, `src-tauri/src/brand.rs`, so each upstream file showing a name changes by one
identifier. Its `ID`, `ytminamp`, is also the tray and MPRIS (media controls) id and the
`.desktop` name sleep inhibition reports, so YTMinamp and Limusic can run side by side. Package
and file names stay `ytminamp` (`productName`): a name with spaces and brackets doesn't belong
there. Limusic's own UI keeps its name; it's still Limusic.

The icon, `packaging/icon/ytminamp.svg`, is YouTube Music's red play disc with Winamp's lightning
bolt in the play button. `src-tauri/icons/` is generated from it:

```bash
magick -background none -density 900 rsvg:packaging/icon/ytminamp.svg -resize 1024x1024 /tmp/ytminamp-1024.png
podman run --rm -v "$PWD":/src:Z -v /tmp:/icon:Z -w /src ytminamp-fedora-build tauri icon /icon/ytminamp-1024.png -o src-tauri/icons
rm -rf src-tauri/icons/android src-tauri/icons/ios
```

## Title, kbps, kHz

The title area shows "Artist - Title" in the playlist editor's font (`pledit.txt`) instead of
`text.bmp`, so it can show any script (`text.bmp` has only ASCII). It scrolls when it's too long.
kbps, kHz and mono/stereo come from mpv's decoded stream (`audio-bitrate`,
`audio-params/samplerate`, `audio-params/channel-count`), read through `Player::audio_info` (a
small addition to `crates/player`) and polled once a second by the Winamp window.

## Shuffle and repeat

The skin's shuffle and repeat buttons drive Limusic's own queue modes. Winamp's repeat is
on/off, Limusic's is off/all/one, so the button cycles all three and lights for both "all" and
"one"; the marquee shows the new mode for two seconds, as Winamp 5 does.

## Skins

Right-click anywhere on the skin (or click the titlebar's options button, top left) for Winamp's
main menu. On Linux it's a GTK menu built in Rust (`winamp::popup_menu`) that pops up and returns
at once, a pick coming back as a `winamp-menu` event. Not Tauri's menu API there: its popup is
modal (muda spins the GTK loop until the menu reports closing), a menu Wayland dismisses can
never report it, and while that loop spins Tauri delivers no events and the popup holds a lock —
the whole UI froze that way, twice. Windows and macOS use Tauri's menu (see `menu.js`). **Skins** lists every `.wsz`/`.zip` in `<app data>/skins`
(`~/.local/share/com.ytminamp.desktop/skins` on Linux) plus the built-in skin. **Load skin…**
checks the file parses, copies it into that folder and switches to it. The choice is remembered
in `<app data>/winamp.json` (not in Limusic's settings, to keep upstream untouched); a skin that
has since gone missing or broken falls back to the built-in one.

## Window shape

`region.txt` is a list of polygons Winamp ORs together (rounded corners are typically several
overlapping rectangles, each a step in). The canvas gets a CSS `clip-path: path(...)`
with every polygon wound the same way, so the nonzero rule unions them, plus a rectangle for the
docked playlist.

## Pixel-exact rendering

WebKitGTK scales page content by the desktop's font DPI / text-scaling factor, so a 275 px canvas
in a 275 px window can come out ~4.5% (or much more) too big: the skin overflows the window and
every click lands in the wrong place. `WinampSkin.svelte` measures the real CSS-px-to-screen-px
ratio on open and cancels it with the webview zoom. Don't remove that.

## Development

```bash
cd ui && pnpm install && cd ..
TAURI_FRONTEND_PATH=ui cargo tauri dev
```

`TAURI_FRONTEND_PATH=ui` matters: the repo also contains Limusic's marketing site (`website/`),
and tauri-cli's frontend auto-detection can pick that instead, leaving you staring at the wrong
Vite server.

### A native Fedora binary (no Nix)

```bash
scripts/build-fedora.sh      # rootless podman, Fedora 44 image → dist/ytminamp
./dist/ytminamp
scripts/build-fedora.sh rpm  # the same, plus dist/ytminamp-<version>-<N>.x86_64.rpm
```

N is the build number (see [Releases](#releases)). Cargo's build directory is a podman volume
per checkout (`ytminamp-target-<directory name>`): every checkout mounts at the same path in the
container, and a shared one would hand one checkout another's newer build of a crate.

It links against the distro's own webkit2gtk4.1 and mpv-libs (both present on a
stock Fedora 44 desktop). App data lives under the `com.ytminamp.desktop` identifier, separate
from an installed Limusic. The default skin, Winamp 2.91's own, is compiled in
(`src-tauri/skins/base-2.91.wsz`).

### Driving the GUI from scripts

Wayland compositors drop synthetic (XTest) input, so automated testing runs the app on a private
Xvfb display. With Nix, the flake's `gui-test` dev shell has the tools:

```bash
nix develop .#gui-test --command Xvfb :99 -screen 0 1280x800x24 &
DISPLAY=:99 GDK_BACKEND=x11 TAURI_FRONTEND_PATH=ui nix develop --command cargo tauri dev
nix develop .#gui-test --command env DISPLAY=:99 xdotool mousemove 50 97 click 1
nix develop .#gui-test --command env DISPLAY=:99 import -window root shot.png
```

Don't destroy windows with `xdotool windowclose` there — with no window manager GTK hits an X
error and the app aborts.

## Not done yet

- Shade mode; oscilloscope; EQ AUTO (per-track presets); Jump to time.
- A Media Library window of its own: Limusic's window stands in (Media Library, Alt+L).
- Snapping floating windows together.
- Search typeahead.
- Fractional desktop scaling (e.g. 125%) blurs the skin evenly: GTK3 renders the window at 1x and
  the compositor scales it. Pixel art can't be both sharp and evenly sized at 1.25x.

## Publishing

Development happens in a private repository with the full history; the public fork,
[ergosteur/YTMinamp-limusic](https://github.com/ergosteur/YTMinamp-limusic), gets a squashed
snapshot per sync on its `ytminamp` branch (its `master` stays upstream Limusic).
`scripts/publish-github.sh` exports the committed tree (`git archive`, so nothing uncommitted
or ignored can leak), mirrors it into a clone of the fork and commits; it never pushes. Private
files (the backlog, notes for coding agents) are left out of both the tree and the commit message
(only commits that change something published contribute theirs), and it refuses to publish if
either names a private host or address; `PUBLISH_MESSAGE=<file>` supplies a message instead.
Edit in the private repository: the clone is overwritten on every sync.

### Releases

Tags are `v<Limusic version>-ytminamp.<N>` (`v1.3.0-ytminamp.3`: built on Limusic 1.3.0, our
third). The app's own `version` stays Limusic's; `scripts/set-ytminamp-release.py N` puts N
everywhere else a version shows:

| Where | Becomes | Why |
|---|---|---|
| RPM Release field | `ytminamp-1.3.0-3` | dnf sees each build as an upgrade |
| MSI version | `1.3.3` (patch × 1000 + N; Limusic 1.3.1 build 1 would be `1.3.1001`) | Windows Installer compares only major.minor.build, the build at most 65535 |
| About box | `1.3.0 (ytminamp.3)` | `ui/src/lib/skin/release.js` |
| Release file names | `ytminamp_1.3.0-ytminamp.3_x64-setup.exe` | renamed by the upload step |

The workflows refuse a tag that doesn't match N in all of those. N starts again from 1 when the
Limusic version changes. On Windows the setup .exe upgrades in place either way.

Builds are unsigned and there's no updater (its endpoints are emptied in `tauri.conf.json`), so a
release is just installers:

1. `scripts/set-ytminamp-release.py N`, commit. Publish and push the `ytminamp` branch, then
   `gh release create <tag> --target <sha> --prerelease` on the fork.
2. `gh workflow run ytminamp-{linux,windows,macos}.yml --ref ytminamp -f tag=<tag>`: AppImage +
   deb, NSIS + MSI, Apple Silicon DMG, each attached to the release by its own run.
3. The RPM is built here, `scripts/build-fedora.sh rpm`, and attached with
   `gh release upload`.

The three workflows are generated from upstream's release workflows by
`scripts/make-release-workflows.py` (tag check, no signing or `latest.json`, our names, a plain
upload step), so upstream's platform fixes carry over: re-run it after merging upstream changes
to those files, never edit the generated ones.

## Credits

ytminamp stands on other people's work:

- **[Limusic](https://github.com/SimoHypers/limusic)** by SimoHypers: the whole player this is a
  fork of (YouTube Music client, playback, library, everything outside Winamp mode).
  GPL-3.0-or-later, and so is this fork.
- **[Webamp](https://github.com/captbaritone/webamp)** by Jordan Eldredge and contributors (MIT):
  the reference for how classic skins are laid out. Sprite coordinates and window layout
  (`skinSprites.ts` and its CSS) are transcribed into `ui/src/lib/skin/render/sprites.js`,
  `playlist.js` and `albumArt.js`; the title marquee follows its `Marquee.tsx`; the analyzer's bar
  drawing (`visualizer.js`) ports its `VisPainter.ts`, and the FFT in `src-tauri/src/viz.rs`
  ports its `FFTNullsoft.ts`. Webamp's documentation of Winamp 2.9's behaviour is what made
  pixel-accurate rendering possible without guessing.
- **[vis_classic](https://github.com/WACUP/vis_classic)**, the Classic Spectrum Analyzer Winamp
  plug-in by Mike Lynch, as released by WACUP (MIT): where Webamp's FFT comes from, so ours too.
- **Nullsoft Winamp**, whose 2.x skin format (`.wsz`) and look this recreates. Winamp is a
  trademark of its owner; ytminamp is an unofficial fan project, not affiliated with or endorsed
  by Winamp or Nullsoft. The built-in default skin, `src-tauri/skins/base-2.91.wsz`, is
  Nullsoft's Winamp 2.91 base skin, the copy [Webamp ships](https://github.com/captbaritone/webamp/tree/master/packages/webamp/assets/skins)
  (taken from its repository at commit `3664324b`). It is not under an open licence: as Webamp's
  README puts it, the Winamp name and interface are surely property of Nullsoft; it is included
  in the same spirit as Webamp includes it.
- **[Butterchurn](https://github.com/jberg/butterchurn)** and
  **[butterchurn-presets](https://github.com/jberg/butterchurn-presets)** by Jordan Berg (MIT):
  the MilkDrop window. MilkDrop itself is Ryan Geiss's, and the presets are their authors'.
- **Skin authors.** The test skins in `fixtures/skins` are freely licensed (see its README):
  *Debian 1.0* by Jesper Schultz (Artistic License) and *Antarès 1a* by Jérôme Villette (GPL),
  from the XMMS skin collection.

<details>
<summary>MIT licence notices</summary>

Webamp — https://github.com/captbaritone/webamp

```
The MIT License (MIT)

Copyright (c) [2015] [Jordan Eldredge]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

vis_classic (WACUP) — https://github.com/WACUP/vis_classic — MIT, "Copyright (c) 1998-2018 Mike
Lynch (original plug-in author)" and "Copyright (c) 2018 WACUP - WinAmp Community Update Project",
with the same terms as above.

Butterchurn and butterchurn-presets — https://github.com/jberg/butterchurn — MIT, "Copyright (c)
2013-2018 Jordan Berg", with the same terms as above.

The app carries these notices itself (`ui/static/third-party-notices.txt`, on the About window's
*Third-party notices* tab), since the bundled code doesn't keep the packages' LICENSE files.

</details>
