// Thin adapter between the Winamp canvas renderer (render/*.js, input.js) and limusic's real
// Tauri command surface ($lib/api) — keeps the renderer decoupled from the rest of the app's API
// shape, and is the one place that would need to change if a command's name/signature does.

import { emitTo } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import * as api from '$lib/api';
import { playback } from '$lib/player.svelte';
import { uiState } from './uiState.js';
import { PL_H, PL_W, VISIBLE_ROWS, listRows, maxScroll } from './render/playlist.js';
import { dockedLayout } from './layout.js';
import { EQ_H, EQ_W } from './render/equalizer.js';
import { setScale } from './pixels.js';
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
	return api.togglePause();
}

/** @param {number} positionSecs */
export function seekTo(positionSecs) {
	return api.seek(positionSecs);
}

/** @param {number} volume 0-100 */
export function setVolume(volume) {
	return api.setVolume(volume);
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
	return playback.paused ? api.togglePause() : api.seek(0);
}

/** Winamp's Pause (C): pause, or carry on if paused. */
export function pause() {
	return api.togglePause();
}

/** Back or forward `secs` (the arrow keys). @param {number} secs */
export function seekBy(secs) {
	api.seek(Math.max(0, playback.position + secs)).catch(log('seek'));
}

/** Volume up or down by `step`%, shown in the title (the arrow keys, the wheel). @param {number} step */
export function nudgeVolume(step) {
	const volume = Math.max(0, Math.min(100, Math.round(playback.volume) + step));
	api.setVolume(volume).catch(log('volume'));
	flashMarquee(`Volume: ${volume}%`);
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
		api.openWinampPanel(kind, w, h).catch(log(`open ${kind} window`));
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
			uiState.pl.selected = null;
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
	// The right side belongs to docked lyrics while they're there.
	if (dock === 'right' && lyricsOnRight()) dock = 'float';
	const was = uiState.art.open && uiState.art.dock === 'float';
	uiState.art.open = open;
	uiState.art.dock = dock;
	syncFloating('art', was, open && dock === 'float', () => artSize(uiState.art.frame, { width: ART_FLOAT_WIDTH }));
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
	uiState.doubleSize = !uiState.doubleSize;
	savePref('doubleSize', uiState.doubleSize);
	await applyDoubleSize();
}

/** Zoom the page and size the window to match `uiState.doubleSize`. */
export async function applyDoubleSize() {
	await setScale(uiState.doubleSize ? 2 : 1).catch(log('double size'));
	resizeToLayout();
}

/** Remember the EQ's settings (for show: nothing filters the sound yet). */
export function saveEq() {
	const { on, auto, preamp, bands } = uiState.eq;
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
	Object.assign(uiState.eq, pref('eq', {}));
	uiState.doubleSize = pref('doubleSize', false);
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
	if (view.selected !== null && view.selected >= items.length) view.selected = null;

	const first = items[0]?.video_id;
	const replaced = first !== followed.first;
	if (!replaced && currentIndex === followed.current) return;
	followed = { first, current: currentIndex };
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

/** ADD → Open YouTube URL: the small dialog window (OpenUrlWindow.svelte). */
export function openUrlDialog() {
	api.openWinampPanel('url', 275, 70).catch((e) => console.error('open url dialog failed', e));
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
		s.selected = i;
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
	s.searchedFor = q;
	s.status = 'Searching...';
	s.results = [];
	s.scroll = 0;
	s.selected = null;
	try {
		const results = await api.search(q, true);
		if (s.searchedFor !== q) return; // a newer search started meanwhile
		s.results = results;
		s.selected = results.length ? 0 : null;
		s.status = results.length ? '' : 'No results';
	} catch (e) {
		if (s.searchedFor === q) s.status = `Search failed: ${e}`;
	}
}

/** Play a search result now; YouTube Music's radio carries on after it, as in Limusic. */
export function playResult(/** @type {number} */ i) {
	const item = uiState.search.results[i];
	return item ? api.play(item) : Promise.resolve();
}

/**
 * @param {number} i
 * @param {boolean} next "Play next" rather than "Add to queue"
 */
export async function queueResult(i, next) {
	const item = uiState.search.results[i];
	if (!item) return;
	await (next ? api.playNext([item]) : api.addToQueue([item]));
	flashMarquee(next ? 'Playing next' : 'Added to queue');
}
