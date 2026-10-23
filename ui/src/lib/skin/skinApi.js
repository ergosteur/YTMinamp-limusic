// Thin adapter between the Winamp canvas renderer (render/*.js, input.js) and limusic's real
// Tauri command surface ($lib/api) — keeps the renderer decoupled from the rest of the app's API
// shape, and is the one place that would need to change if a command's name/signature does.

import { emit, emitTo } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import * as api from '$lib/api';
import {
	commitVolume as limusicCommitVolume,
	dragVolume,
	nudgeVolume as limusicNudgeVolume,
	playback
} from '$lib/player.svelte';
import { uiState } from './uiState.js';
import { selectNone, selectOnly, trimSelection } from './selection.js';
import { activePart } from './focus.js';
import { playRow, searchRows, songsIn } from './searchKinds.js';
import { PL_H, PL_W, VISIBLE_ROWS, listRows, maxScroll } from './render/playlist.js';
import { LYRICS_W, dockedLayout } from './layout.js';
import { EQ_H, EQ_W } from './render/equalizer.js';
import { announceDoubleSize, doubleFactor, setScale } from './pixels.js';
import { loadPrefs, pref, savePref } from './prefs.js';
import { artSize } from './render/albumArt.js';

/** @typedef {import('$lib/api').SkinPayload} SkinPayload */

/** The remembered skin (or the one built into the binary). @returns {Promise<SkinPayload>} */
export function loadSkin() {
	return api.loadWszSkin();
}

/** Switch to `path` (null = built-in) and remember it. @returns {Promise<SkinPayload>} */
export function selectSkin(/** @type {string | null} */ path) {
	return api.selectWszSkin(path);
}

/**
 * Show `text` in the title marquee for a couple of seconds, like Winamp 5 does when a mode
 * changes ("Shuffle: On").
 * @param {string} text
 */
export function flashMarquee(text) {
	// A floating panel has no marquee of its own: the Winamp window shows it.
	if (getCurrentWindow().label !== 'winamp') {
		emitTo('winamp', 'winamp-marquee', text).catch(() => {});
		return;
	}
	uiState.marqueeMessage = text;
	uiState.marqueeMessageUntil = performance.now() + 2000;
}

const REPEAT_LABEL = { off: 'Off', all: 'All', one: 'Track' };

export function toggleShuffle() {
	flashMarquee(`Shuffle: ${playback.queue.shuffle ? 'Off' : 'On'}`);
	return api.toggleShuffle();
}

/**
 * Winamp's repeat button is on/off; limusic also has repeat-one, so the button cycles
 * off → all → one like limusic's own, and the marquee says which.
 */
export function cycleRepeat() {
	const r = playback.queue.repeat ?? 'off';
	return setRepeatMode(r === 'off' ? 'all' : r === 'all' ? 'one' : 'off');
}

/** @param {'off' | 'all' | 'one'} mode */
export function setRepeatMode(mode) {
	flashMarquee(`Repeat: ${REPEAT_LABEL[mode]}`);
	return api.setRepeat(mode);
}

export function togglePlayPause() {
	return afterStop() ?? api.togglePause();
}

/** @param {number} positionSecs */
export function seekTo(positionSecs) {
	return api.seek(positionSecs);
}

/** @param {number} volume 0-100 */
export function setVolume(volume) {
	// Limusic's own drag path: live, and saved once the gesture ends (commitVolume).
	dragVolume(volume);
	return Promise.resolve();
}

/**
 * Classic Winamp's Stop halts playback outright; limusic's queue model has no separate "stopped"
 * state, only playing/paused. Pausing is the closest real behavior — a no-op if already paused,
 * rather than toggling back to playing.
 */
export function stopPlayback() {
	return playback.paused ? Promise.resolve() : api.togglePause();
}

/** Winamp's Play (X): carry on if paused, back to the start if already playing. */
export function play() {
	return afterStop() ?? (playback.paused ? api.togglePause() : api.seek(0));
}

/** Winamp's Pause (C): pause, or carry on if paused. */
export function pause() {
	return afterStop() ?? api.togglePause();
}

/** Stopped by "Stop after current": Play goes on to the next track (this one is over), else null. */
function afterStop() {
	if (!uiState.stoppedAfterCurrent) return null;
	uiState.stoppedAfterCurrent = false;
	return api.nextTrack();
}

/**
 * Winamp's "Stop after current" (Ctrl+V): on, the playing track is the last before a stop. Kept in
 * Rust (winamp.rs), which sets it up in mpv; this window watches for the stop (`followStopAfter`),
 * so other windows hand the toggle over.
 */
export function toggleStopAfterCurrent() {
	if (getCurrentWindow().label !== 'winamp') {
		emitTo('winamp', 'winamp-key', 'stopAfter').catch(log('stop after current'));
		return;
	}
	const on = !uiState.stopAfter;
	api.setStopAfterCurrent(on).then(() => {
		uiState.stopAfter = on;
		flashMarquee(`Stop after current: ${on ? 'On' : 'Off'}`);
	}, log('stop after current'));
}

/** Per frame, in the Winamp window: the stop happened (mpv paused at the very end), so it's spent. */
export function followStopAfter() {
	if (uiState.stoppedAfterCurrent && (!playback.paused || playback.position < playback.duration - 1.5)) {
		uiState.stoppedAfterCurrent = false;
	}
	if (!uiState.stopAfter || !playback.paused || playback.duration <= 0 || playback.position < playback.duration - 1) return;
	uiState.stopAfter = false;
	uiState.stoppedAfterCurrent = true;
	api.setStopAfterCurrent(false).catch(log('stop after current'));
	flashMarquee('Stopped after current');
}

let fadingOut = false;
/** Winamp's "Stop w/ fadeout" (Shift+V): the volume down over a second and a half, then stop. */
export async function stopWithFadeout() {
	if (playback.paused || fadingOut) return;
	fadingOut = true;
	const from = playback.volume;
	try {
		for (let i = 1; i <= 15 && !playback.paused; i++) {
			// Whole steps: Rust's set_volume takes an integer, and quietly refuses anything else.
			dragVolume(Math.round(from * (1 - i / 15)));
			await new Promise((r) => setTimeout(r, 100));
		}
		if (!playback.paused) await api.togglePause();
	} finally {
		// Back where it was, live only: the saved level never moved (dragVolume doesn't save).
		dragVolume(from);
		fadingOut = false;
	}
}

/** Where the last arrow-key seek went, and when: a held key seeks on from there, since the
 *  position only comes back about 4 times a second. */
let seekTarget = { secs: 0, at: 0 };

/** Back or forward `secs` (the arrow keys), within the track. @param {number} secs */
export function seekBy(secs) {
	const now = performance.now();
	const from = now - seekTarget.at < 600 ? seekTarget.secs : playback.position;
	const end = playback.duration > 0 ? playback.duration - 1 : Infinity;
	const to = Math.max(0, Math.min(end, from + secs));
	seekTarget = { secs: to, at: now };
	api.seek(to).catch(log('seek'));
}

/** Volume up or down by `step`%, shown in the title (the arrow keys, the wheel). Limusic's own
 * nudge, so it's saved for next time once the steps stop. @param {number} step */
export function nudgeVolume(step) {
	limusicNudgeVolume(step);
	flashMarquee(`Volume: ${Math.round(playback.volume)}%`);
}

/** The end of a volume drag or click: the level to reopen at next time. @param {number} volume */
export function commitVolume(volume) {
	limusicCommitVolume(volume);
}

export function nextTrack() {
	return api.nextTrack();
}

export function prevTrack() {
	return api.prevTrack();
}

/** @param {number} index */
export function playIndex(index) {
	return api.playIndex(index);
}

/** The search panel's text box (WinampSkin.svelte). */
export const SEARCH_INPUT_ID = 'winamp-search';

const log = (/** @type {string} */ what) => (/** @type {unknown} */ e) => console.error(`${what} failed`, e);

/**
 * Bring a panel's floating window up or down to match a change in where it lives (winamp.rs
 * owns the window; this window owns whether there is one). A window opens at the size it was
 * last resized to.
 * @param {import('./layout.js').PanelKind} kind
 * @param {boolean} was floating before the change
 * @param {boolean} now floating after it
 * @param {() => { w: number, h: number }} size for a window that's opening, if none is remembered
 */
function syncFloating(kind, was, now, size) {
	if (now && !was) {
		const { w, h } = pref(`floatSize-${kind}`, size());
		api.openWinampPanel(kind, w * doubleFactor(), h * doubleFactor()).catch(log(`open ${kind} window`));
	} else if (was && !now) {
		api.closeWinampPanel(kind).catch(log(`close ${kind} window`));
	}
}

/** Each panel's state, by kind. @param {import('./layout.js').PanelKind} kind */
function viewOf(kind) {
	return { search: uiState.search, playlist: uiState.pl, art: uiState.art, eq: uiState.eq, lyrics: uiState.lyrics }[
		kind
	];
}

/** Remember where `kind` is (open, and docked where), for the next time Winamp mode opens.
 * @param {import('./layout.js').PanelKind} kind */
function savePlacement(kind) {
	const view = viewOf(kind);
	savePref(`panel-${kind}`, { open: view.open, dock: view.dock });
}

/** A floating panel's size when it first opens: what it's drawn at docked. */
const FLOAT_SIZE = {
	search: { w: PL_W, h: PL_H },
	playlist: { w: PL_W, h: PL_H },
	eq: { w: EQ_W, h: EQ_H },
	lyrics: { w: PL_W, h: PL_H }
};

/**
 * Show or hide a panel other than album art, optionally moving it: docked in the stack under
 * the main window, or floating in a window of its own. The Winamp window grows/shrinks to match.
 * Opening the docked playlist scrolls the current track into view, like Winamp; opening docked
 * search focuses its text box (a floating panel does both in its own window).
 * @param {'search' | 'playlist' | 'eq' | 'lyrics'} kind
 * @param {boolean} open
 * @param {'stack' | 'float' | 'right'} [dock] lyrics dock 'right', the others 'stack'
 */
export function setPanelOpen(kind, open, dock) {
	const view = viewOf(kind);
	const was = view.open && view.dock === 'float';
	view.open = open;
	view.dock = dock ?? view.dock;
	// Docked lyrics take the right side: album art there moves out to its own window.
	if (kind === 'lyrics' && open && view.dock === 'right' && uiState.art.open && uiState.art.dock === 'right') {
		setArt(true, 'float');
	}
	const floating = open && view.dock === 'float';
	syncFloating(kind, was, floating, () => FLOAT_SIZE[kind]);
	if (open && !floating) {
		if (kind === 'playlist') {
			const current = playback.queue.currentIndex;
			const centred = current - Math.floor(VISIBLE_ROWS / 2);
			uiState.pl.scroll = Math.max(0, Math.min(maxScroll(playback.queue.items.length), centred));
			selectNone(uiState.pl);
		} else if (kind === 'search') {
			// After the render loop has shown and placed the box.
			requestAnimationFrame(() => requestAnimationFrame(focusSearch));
		}
	}
	savePlacement(kind);
	resizeToLayout();
}

/**
 * The PL, EQ and eject buttons, the clutterbar's I, the Alt shortcuts: hide the panel if it's
 * showing (docked or floating), else show it where it was last.
 * @param {import('./layout.js').PanelKind} kind
 */
export function togglePanel(kind) {
	if (kind === 'art') return setArt(!uiState.art.open);
	setPanelOpen(kind, !viewOf(kind).open);
}

/** Grow or shrink the window to fit whatever is docked now (twice that in double size). */
export function resizeToLayout() {
	const { width, height } = dockedLayout();
	const f = uiState.doubleSize ? 2 : 1;
	api.resizeWinamp(width * f, height * f).catch((e) => console.error('resize failed', e));
}

/** The floating album art window's picture when it first opens (if no size is remembered). */
const ART_FLOAT_WIDTH = 220;

/**
 * Show or hide the album art window, optionally moving it: beside the main window (left/right,
 * at its height), into the stack below (as wide as it), or out into a window of its own.
 * @param {boolean} open
 * @param {import('./uiState.js').ArtDock} [dock]
 */
export function setArt(open, dock = uiState.art.dock) {
	// The right side belongs to docked lyrics while they're there: the stack instead (a floating
	// window's double-click asks for the right, and must still dock).
	if (dock === 'right' && lyricsOnRight()) dock = 'stack';
	const was = uiState.art.open && uiState.art.dock === 'float';
	uiState.art.open = open;
	uiState.art.dock = dock;
	syncFloating('art', was, open && dock === 'float', () => artSize(uiState.art.frame, { width: ART_FLOAT_WIDTH }, uiState.art.caption));
	savePlacement('art');
	resizeToLayout();
}

/** Lyrics are docked to the right of the stack (album art can't dock there then). */
export const lyricsOnRight = () => uiState.lyrics.open && uiState.lyrics.dock === 'right';

/** The clutterbar's A: keep every Winamp window above others. */
export function toggleAlwaysOnTop() {
	uiState.alwaysOnTop = !uiState.alwaysOnTop;
	api.setWinampAlwaysOnTop(uiState.alwaysOnTop).catch(log('always on top'));
}

/** The clutterbar's D: Winamp's double size, for the whole Winamp window. */
export async function toggleDoubleSize() {
	if (!uiState.doubleSize && !(await doubleFits())) {
		flashMarquee("Double size won't fit on this screen");
		return;
	}
	uiState.doubleSize = !uiState.doubleSize;
	savePref('doubleSize', uiState.doubleSize);
	await applyDoubleSize();
}

/** Whether everything that's open fits the screen at double size. */
async function doubleFits() {
	const { width, height } = dockedLayout();
	return api.winampFits(width * 2, height * 2).catch(() => true);
}

/** Zoom the page and size the window to match `uiState.doubleSize`. */
export async function applyDoubleSize() {
	await setScale(uiState.doubleSize ? 2 : 1).catch(log('double size'));
	resizeToLayout();
	// The floating windows (all but MilkDrop's) follow (pixels.js `followDoubleSize`).
	announceDoubleSize(uiState.doubleSize);
}

/** The lyrics' text sizes, smallest to largest; 1 is the playlist editor's 11 px. */
const LYRICS_ZOOM = [0.75, 0.9, 1, 1.25, 1.5, 1.75, 2, 2.5, 3];

/**
 * Lyrics text one size bigger (1), smaller (-1) or back to normal (0). Remembered, and sent to
 * every Winamp window: the lyrics may be floating in another one.
 * @param {-1 | 0 | 1} by
 */
export function zoomLyrics(by) {
	const at = LYRICS_ZOOM.reduce(
		(best, z, i) => (Math.abs(z - uiState.lyrics.zoom) < Math.abs(LYRICS_ZOOM[best] - uiState.lyrics.zoom) ? i : best),
		0
	);
	const zoom = by === 0 ? 1 : LYRICS_ZOOM[Math.max(0, Math.min(LYRICS_ZOOM.length - 1, at + by))];
	uiState.lyrics.zoom = zoom;
	savePref('lyricsZoom', zoom);
	emit(LYRICS_ZOOM_EVENT, zoom).catch(() => {});
	flashMarquee(`Lyrics size: ${Math.round(zoom * 100)}%`);
}

/** Tells every Winamp window the lyrics' new size (see `zoomLyrics`). */
export const LYRICS_ZOOM_EVENT = 'winamp-lyrics-zoom';

/** Apply the EQ's settings to what plays (viz.rs's `@eq` filter) and remember them. */
export function saveEq() {
	const { on, auto, preamp, bands } = uiState.eq;
	api.setWinampEq({ on, preamp, bands: [...bands] }).catch(log('eq'));
	savePref('eq', { on, auto, preamp, bands });
}

/**
 * Put back everything Winamp mode remembers (prefs.js): panels where they were, the EQ, double
 * size, the time display, the analyzer. For the Winamp window, once its skin has loaded.
 */
export async function restorePrefs() {
	await loadPrefs();
	uiState.alwaysOnTop = pref('alwaysOnTop', false);
	uiState.timeRemaining = pref('timeRemaining', false);
	uiState.visMode = pref('visMode', 'analyzer');
	uiState.vizLevels = pref('vizLevels', 'winamp');
	Object.assign(uiState.eq, pref('eq', {}));
	uiState.lyrics.zoom = pref('lyricsZoom', 1);
	uiState.startInWinamp = pref('startInWinamp', false);
	uiState.art.caption = pref('artCaption', false);
	uiState.search.kind = pref('searchKind', 'songs');
	uiState.marqueeScroll = pref('marqueeScroll', true);
	uiState.milkdropOnStart = pref('milkdropOnStart', false);
	if (uiState.milkdropOnStart && !uiState.milkdrop) toggleMilkdrop();
	uiState.lyrics.width = pref('lyricsWidth', LYRICS_W);
	// Remembered from a bigger screen, perhaps: only if it fits this one (not saved, so it's back
	// on the bigger screen).
	uiState.doubleSize = pref('doubleSize', false) && (await doubleFits());
	if (uiState.doubleSize) await applyDoubleSize();
	/** @typedef {{ open: boolean, dock: any } | null} Placement */
	for (const kind of /** @type {const} */ (['eq', 'search', 'playlist', 'lyrics'])) {
		const p = /** @type {Placement} */ (pref(`panel-${kind}`, null));
		if (p?.open) setPanelOpen(kind, true, p.dock);
		else if (p) viewOf(kind).dock = p.dock;
	}
	const art = /** @type {Placement} */ (pref('panel-art', null));
	if (art?.open) setArt(true, art.dock);
	else if (art) uiState.art.dock = art.dock;
	resizeToLayout();
}

/** The queue and current track the playlist view last followed (see `followQueue`). */
let followed = { first: /** @type {string | undefined} */ (undefined), current: -1 };

/**
 * Keep the playlist view on the queue it shows, once per frame: a new queue (playing a search
 * result replaces a 100-track one with a single song) would otherwise leave the old scroll offset
 * past its end, and a track change scrolls the playing row into view, like Winamp.
 */
export function followQueue(visible = VISIBLE_ROWS) {
	const view = uiState.pl;
	const { items, currentIndex } = playback.queue;
	const max = maxScroll(items.length, visible);
	if (view.scroll > max) view.scroll = max;
	trimSelection(view, items.length);

	const first = items[0]?.video_id;
	const replaced = first !== followed.first;
	if (!replaced && currentIndex === followed.current) return;
	followed = { first, current: currentIndex };
	// Marks are row numbers: on a new queue they'd pick out tracks nobody chose.
	if (replaced) selectNone(view);
	if (view.draggingScroll) return;
	const inView = currentIndex >= view.scroll && currentIndex < view.scroll + visible;
	if (replaced || !inView) {
		view.scroll = Math.max(0, Math.min(max, currentIndex - Math.floor(visible / 2)));
	}
}

export function focusSearch() {
	const input = /** @type {HTMLInputElement | null} */ (document.getElementById(SEARCH_INPUT_ID));
	input?.focus();
	input?.select();
}

/**
 * ADD (and the menu's Search): open search, or if it's open already, put the cursor in its box
 * and flash it, so it's obvious that's what the button did. A floating search box flashes in its
 * own window.
 */
export function openSearch() {
	const s = uiState.search;
	if (s.open && s.dock === 'float') {
		emitTo('winamp-search', 'winamp-search-focus').catch(() => {});
		return;
	}
	if (!s.open) setPanelOpen('search', true);
	// After the render loop has shown and placed the box.
	requestAnimationFrame(() => requestAnimationFrame(flashSearch));
}

/**
 * ADD → Search, from whichever window: this window's own search box if it is the floating
 * search panel, else the Winamp window opens or flashes search wherever it lives.
 */
export function requestSearch() {
	const label = getCurrentWindow().label;
	if (label === 'winamp') openSearch();
	else if (label === 'winamp-search') flashSearch();
	else emitTo('winamp', 'winamp-search-add').catch(() => {});
}

/** The analyzer's levels (its right-click menu): Rust maps the band levels (viz.rs), the choice is
 *  remembered. @param {'winamp' | 'linear'} levels */
export function setVizLevels(levels) {
	uiState.vizLevels = levels;
	savePref('vizLevels', levels);
	api.setVizLevels(levels).catch(log('analyzer levels'));
}

/** "Always start in Winamp mode": read by Rust's `show_main` at the next launch. */
export function toggleStartInWinamp() {
	uiState.startInWinamp = !uiState.startInWinamp;
	savePref('startInWinamp', uiState.startInWinamp);
	flashMarquee(`Start in Winamp mode: ${uiState.startInWinamp ? 'On' : 'Off'}`);
}

/** Open or close the MilkDrop window (MilkdropWindow.svelte), at the size it last had. */
export function toggleMilkdrop() {
	if (uiState.milkdrop) {
		uiState.milkdrop = false;
		api.closeWinampPanel('milkdrop').catch(log('close milkdrop'));
		return;
	}
	uiState.milkdrop = true;
	const { w, h } = pref('milkdropSize', { w: 400, h: 300 });
	api.openWinampPanel('milkdrop', w, h).catch((e) => {
		uiState.milkdrop = false;
		log('open milkdrop')(e);
	});
}

/** Where File info's track goes (FileInfoWindow.svelte reads it; localStorage is every window's). */
export const FILE_INFO_KEY = 'ytminamp-file-info';
export const FILE_INFO_SIZE = { w: 420, h: 200 };
/** The About window (AboutWindow.svelte). */
export const ABOUT_SIZE = { w: 420, h: 260 };

/** Show `item` in the File info window, opening it if it isn't. @param {import('$lib/api').SongItem} item */
export function showFileInfo(item) {
	try {
		localStorage.setItem(FILE_INFO_KEY, JSON.stringify(item));
	} catch (e) {
		return log('file info')(e);
	}
	const f = doubleFactor();
	api.openWinampPanel('fileinfo', FILE_INFO_SIZE.w * f, FILE_INFO_SIZE.h * f).catch(log('file info'));
}

/** File info for what's playing (the title's double-click and right-click menu). */
export function showNowFileInfo() {
	const item = nowAsItem();
	if (item) showFileInfo(item);
	else flashMarquee('Nothing playing');
}

/** Tells every Winamp window the art's caption went on or off (see `toggleArtCaption`). */
export const ART_CAPTION_EVENT = 'winamp-art-caption';

/** "Show album name" under the album art (its right-click menu), in every window. */
export function toggleArtCaption() {
	const on = !uiState.art.caption;
	savePref('artCaption', on);
	emit(ART_CAPTION_EVENT, on).catch(() => {});
}

/** The caption went on or off (from any window): this window's art follows. @param {boolean} on */
export function setArtCaption(on) {
	uiState.art.caption = on;
	if (getCurrentWindow().label === 'winamp') resizeToLayout();
}

/** Put the album art somewhere (null: hide it), from the Winamp window or a floating art one. */
export function placeArt(/** @type {import('./uiState.js').ArtDock | null} */ dock) {
	if (getCurrentWindow().label === 'winamp') setArt(dock !== null, dock ?? uiState.art.dock);
	else emitTo('winamp', 'winamp-panel-dock', { kind: 'art', dock }).catch(log('art placement'));
}

/** "Autoscroll songname" (the title's right-click menu). */
export function toggleMarqueeScroll() {
	uiState.marqueeScroll = !uiState.marqueeScroll;
	savePref('marqueeScroll', uiState.marqueeScroll);
}

/** "Run the plug-in on start-up" (the analyzer's right-click menu). */
export function toggleMilkdropOnStart() {
	uiState.milkdropOnStart = !uiState.milkdropOnStart;
	savePref('milkdropOnStart', uiState.milkdropOnStart);
}

/** The playing track, in a playlist row's shape. @returns {import('$lib/api').SongItem | null} */
export function nowAsItem() {
	const now = playback.now;
	if (!now) return null;
	// The queue's own row when it's this track: it carries more (the album's id, the play count).
	// Its title and artist from what's playing, though: Limusic fills a missing artist in there
	// once the track plays (a search for the artist leaves it out of the rows), not in the row.
	const row = playback.queue.items[playback.queue.currentIndex];
	if (row?.video_id === now.videoId) return { ...row, title: now.title || row.title, artists: now.artists || row.artists };
	return {
		video_id: now.videoId,
		title: now.title,
		artists: now.artists,
		album: now.album ?? undefined,
		duration: now.duration,
		thumbnail: now.thumbnail
	};
}

/**
 * Alt+3, Winamp's file info key: the selected row when the playlist or search panel is the active
 * window (focus.js, the titlebar that's lit) and has one, otherwise what's playing. Run in the
 * window the key was pressed in: each window has its own selection.
 */
export function fileInfoForSelection() {
	const part = activePart();
	const pl = uiState.pl.selected;
	const s = uiState.search.selected;
	const item =
		(part === 'playlist' && pl !== null ? playback.queue.items[pl] : null) ??
		(part === 'search' && s !== null ? uiState.search.results[s] : null) ??
		nowAsItem();
	if (item) showFileInfo(item);
	else flashMarquee('Nothing playing');
}

/** EQ PRESETS → Save current as preset...: the small naming dialog (EqPresetWindow.svelte). */
export function openEqPresetDialog() {
	api.openWinampPanel('eqsave', 275 * doubleFactor(), 70 * doubleFactor()).catch((e) => console.error('open eq preset dialog failed', e));
}

/** ADD → Open YouTube URL: the small dialog window (OpenUrlWindow.svelte). */
export function openUrlDialog() {
	api.openWinampPanel('url', 275 * doubleFactor(), 70 * doubleFactor()).catch((e) => console.error('open url dialog failed', e));
}

/** Focus the search box and pulse it three times. */
export function flashSearch() {
	focusSearch();
	document.getElementById(SEARCH_INPUT_ID)?.animate(
		[
			{ boxShadow: 'inset 0 0 0 2px #ffffff', filter: 'brightness(1.8)' },
			{ boxShadow: 'inset 0 0 0 0 transparent', filter: 'brightness(1)' }
		],
		{ duration: 250, iterations: 3 }
	);
}

/**
 * Keys in a search box: Enter searches (or plays the picked result once the query hasn't
 * changed; Shift+Enter queues it instead), arrows pick a result, Esc hides the panel.
 * @param {KeyboardEvent} e
 * @param {HTMLInputElement} input
 * @param {{ w: number, h: number } | undefined} size the panel's, if not docked
 * @param {() => void} close
 */
export function searchKeydown(e, input, size, close) {
	const s = uiState.search;
	const step = e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0;
	if (step && s.results.length) {
		e.preventDefault();
		const i = Math.max(0, Math.min(s.results.length - 1, (s.selected ?? -1) + step));
		selectOnly(s, i);
		const rows = listRows('search', size).rows;
		const max = maxScroll(s.results.length, rows);
		if (i < s.scroll) s.scroll = i;
		else if (i >= s.scroll + rows) s.scroll = Math.min(max, i - rows + 1);
	} else if (e.key === 'Enter') {
		e.preventDefault();
		const unchanged = input.value.trim() === s.searchedFor;
		if (unchanged && s.selected !== null) {
			const done = e.shiftKey ? queueResult(s.selected, false) : playResult(s.selected);
			done.catch(log('search result'));
		} else {
			runSearch(input.value);
		}
	} else if (e.key === 'Escape') {
		e.preventDefault();
		input.blur();
		close();
	}
}

/** @param {string} query */
export async function runSearch(query) {
	const q = query.trim();
	const s = uiState.search;
	if (!q) return;
	rememberSearch(q);
	s.searchedFor = q;
	s.status = 'Searching...';
	s.results = [];
	s.scroll = 0;
	selectNone(s);
	try {
		const kind = s.kind;
		const results = await searchRows(kind, q);
		if (s.searchedFor !== q || s.kind !== kind) return; // a newer search started meanwhile
		s.results = results;
		const first = results.findIndex((r) => r.rowKind !== 'header');
		if (first >= 0) selectOnly(s, first);
		s.status = results.length ? '' : 'No results';
	} catch (e) {
		if (s.searchedFor === q) s.status = `Search failed: ${e}`;
	}
}

/** How many recent searches LIST keeps. */
const SEARCH_HISTORY = 10;

/** Put `q` at the top of the recent searches (LIST), once. @param {string} q */
function rememberSearch(q) {
	const recent = /** @type {string[]} */ (pref('searchHistory', []));
	savePref('searchHistory', [q, ...recent.filter((r) => r.toLowerCase() !== q.toLowerCase())].slice(0, SEARCH_HISTORY));
}

/** Run `q` again from the recent searches, showing it in the box. @param {string} q */
export function searchAgain(q) {
	const input = /** @type {HTMLInputElement | null} */ (document.getElementById(SEARCH_INPUT_ID));
	if (input) input.value = q;
	runSearch(q).catch(log('search'));
}

/** REM: empty the results list. */
export function clearResults() {
	const s = uiState.search;
	s.results = [];
	s.searchedFor = '';
	s.status = '';
	s.scroll = 0;
	selectNone(s);
}

/** REM: empty the search box, and put the cursor in it. */
export function clearSearchBox() {
	const input = /** @type {HTMLInputElement | null} */ (document.getElementById(SEARCH_INPUT_ID));
	if (input) input.value = '';
	focusSearch();
}

/** "3:24" → 204; unknown sorts last. @param {string | undefined} d */
function seconds(d) {
	if (!d) return Infinity;
	const parts = d.split(':').map(Number);
	return parts.some(Number.isNaN) ? Infinity : parts.reduce((a, b) => a * 60 + b, 0);
}

/**
 * MISC: put the results in a new order. The selection goes: its rows would point elsewhere.
 * @param {'title' | 'artist' | 'length' | 'reverse'} by
 */
export function sortResults(by) {
	const s = uiState.search;
	// "All" comes in sections; sorting would scatter them under the wrong headers.
	if (s.results.some((r) => r.rowKind === 'header')) return flashMarquee("Can't sort sections");
	const items = [...s.results];
	if (by === 'reverse') items.reverse();
	else if (by === 'length') items.sort((a, b) => seconds(a.duration) - seconds(b.duration));
	else {
		const text = (/** @type {import('$lib/api').SongItem} */ r) => (by === 'title' ? r.title : (r.artists ?? ''));
		items.sort((a, b) => text(a).localeCompare(text(b)));
	}
	s.results = items;
	s.scroll = 0;
	selectNone(s);
	flashMarquee(by === 'reverse' ? 'Reversed' : `Sorted by ${by}`);
}

/** Play a search result now; YouTube Music's radio carries on after it, as in Limusic. */
export function playResult(/** @type {number} */ i) {
	return playRow(uiState.search.results[i]);
}

/** The button in the search box: search for `kind` now, and from now on. @param {import('./searchKinds.js').SearchKind} kind */
export function setSearchKind(kind) {
	const s = uiState.search;
	s.kind = kind;
	savePref('searchKind', kind);
	const input = /** @type {HTMLInputElement | null} */ (document.getElementById(SEARCH_INPUT_ID));
	const q = input?.value.trim() || s.searchedFor;
	if (q) runSearch(q).catch(log('search'));
	focusSearch();
}

/**
 * @param {number} i
 * @param {boolean} next "Play next" rather than "Add to queue"
 */
export function queueResult(i, next) {
	return queueResults([i], next);
}

/**
 * Several results at once (the selection), in list order.
 * @param {number[]} rows @param {boolean} next "Play next" rather than "Add to queue"
 */
export async function queueResults(rows, next) {
	// Albums and playlists bring all their tracks; artists and headers nothing.
	const items = await songsIn(rows.map((i) => uiState.search.results[i]).filter(Boolean));
	if (!items.length) return flashMarquee('Nothing to queue');
	await (next ? api.playNext(items) : api.addToQueue(items));
	const what = items.length > 1 ? `${items.length} tracks` : '';
	flashMarquee(next ? `Playing next${what && `: ${what}`}` : `Added to queue${what && `: ${what}`}`);
}

/** Play the first of several results now and the rest straight after it. @param {number[]} rows */
export async function playResults(rows) {
	const [first, ...rest] = rows.filter((i) => uiState.search.results[i]?.rowKind !== 'header');
	if (first === undefined) return;
	await playResult(first);
	if (rest.length) await queueResults(rest, true);
}
