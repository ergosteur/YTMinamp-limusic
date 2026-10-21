// UI-only interaction state for the Winamp canvas — hit-testing, drag, cosmetic-only balance.
// Backend-sourced fields (title/position/duration/volume/playing) are never duplicated here:
// WinampSkin.svelte reads those straight off the real `playback` store ($lib/player.svelte) each
// frame and merges them with this object into the plain `uiState`-shaped argument render/
// mainWindow.js expects. A plain mutable object, not a Svelte store — the render loop polls it
// every frame, so there's no need for a subscribe/notify mechanism on top of it.
/** @typedef {'left' | 'right' | 'stack' | 'float'} ArtDock */

export const uiState = {
	pressedButton: /** @type {string | null} */ (null),
	/** The clutterbar's A: every Winamp window kept above others (winamp.rs, remembered). */
	alwaysOnTop: false,
	/** The clutterbar's D: the Winamp window drawn at 2x (pixels.js `setScale`). */
	doubleSize: false,
	draggingSeek: false,
	/** Optimistic position while the seek-bar thumb is being dragged, before `seekTo` lands. */
	draggingPositionSecs: 0,
	draggingVolume: false,
	/** Optimistic volume while the slider is being dragged, before the `onVolume` event lands. */
	draggingVolumeValue: 0,
	/** Time display shows "-mm:ss" left instead of elapsed; toggled by clicking it. */
	timeRemaining: false,
	/** -100..100, cosmetic only — the `player` crate exposes no audio panning yet. */
	balance: 0,
	/** From mpv's decoded channel count (WinampSkin.svelte polls it); default stereo. */
	stereo: true,
	/** The playing stream's kbps / kHz as mpv decodes it; null until known. */
	kbps: /** @type {number | null} */ (null),
	khz: /** @type {number | null} */ (null),
	/** Clicking the visualizer cycles it, like Winamp (no oscilloscope yet). */
	visMode: /** @type {"analyzer" | "off"} */ ('analyzer'),
	/** Latest 75 analyzer columns from Rust's `winamp-viz` event (viz.rs). */
	vizColumns: /** @type {number[] | null} */ (null),
	/** Shown in place of the title until `marqueeMessageUntil` (performance.now() ms). */
	marqueeMessage: '',
	marqueeMessageUntil: 0,

	// Docked panels under the main window, top to bottom: search, then the playlist editor.
	// See layout.js.
	pl: panelState(),
	/** The equalizer: looks and moves like Winamp's, changes nothing you hear (no EQ filter yet). */
	eq: {
		open: false,
		dock: /** @type {'stack' | 'float'} */ ('stack'),
		on: true,
		auto: false,
		/** 0-100, 50 = 0 dB, like Webamp's sliders. */
		preamp: 50,
		bands: [50, 50, 50, 50, 50, 50, 50, 50, 50, 50],
		/** The slider being dragged ('preamp' or a band index), and the button held down. */
		dragging: /** @type {'preamp' | number | null} */ (null),
		pressed: /** @type {string | null} */ (null)
	},
	/** The lyrics panel: the playing track's, scrolled to the sung line when they're timed. */
	lyrics: {
		open: false,
		/** Docked to the right of the whole stack (layout.js), or floating. */
		dock: /** @type {'right' | 'float'} */ ('right'),
		/** Lines scrolled by hand (wheel) away from the sung one; reset on the next track. */
		nudge: 0,
		closePressed: false
	},
	/** The album art window: beside the main window (left/right), in the stack below, or floating
	 * in a window of its own (render/albumArt.js, AlbumArtWindow.svelte). */
	art: {
		open: false,
		/** Floating until moved: it isn't one of classic Winamp's docked windows. */
		dock: /** @type {import('./uiState.js').ArtDock} */ ('float'),
		/** Which frame the skin gets: gen.bmp, or the EQ-window fallback. Set on skin load. */
		frame: /** @type {import('./render/albumArt.js').ArtFrame} */ ('gen'),
		closePressed: false
	},
	search: {
		...panelState(),
		/** The query the current `results` are for; Enter re-runs only when the box differs. */
		searchedFor: '',
		results: /** @type {import('$lib/api').SongItem[]} */ ([]),
		/** "Searching...", "No results", an error; '' when the results speak for themselves. */
		status: ''
	}
};

/** View state of one list panel. */
function panelState() {
	return {
		open: false,
		/** Docked in the stack under the main window, or floating in a window of its own. */
		dock: /** @type {'stack' | 'float'} */ ('stack'),
		/** Index of the first visible row. */
		scroll: 0,
		selected: /** @type {number | null} */ (null),
		pressed: /** @type {string | null} */ (null),
		draggingScroll: false
	};
}
